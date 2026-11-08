"""CLIPTORA: offline batch analysis and human-reviewed highlights.

Source files are read-only. Working files, metadata and renders reside outside the source folder.
No cloud calls: optional Ollama only at 127.0.0.1, optional Whisper downloads a model on first use.
"""
import array
import datetime
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from scanner_bridge import discover, locate_scanner

EXTS = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.ts'}
KEYWORDS = ('ахах', 'хаха', 'лол', 'смешно', 'подожди', 'смотри', 'че за', 'что за',
            'что происходит', 'пизд', 'бля', 'сука', 'охрен', 'офиг', 'капец', 'еба',
            'убил', 'баг', 'чит', 'помог', 'не может', 'попал', 'промах', 'ха-ха',
            'заткнись', 'серьёзно', 'ты видел', 'случилось', 'wtf', 'lol')


def process(command, *, capture=True, timeout=None):
    return subprocess.run(command, stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE, timeout=timeout, check=False,
                          creationflags=(0x08000000 if os.name == 'nt' else 0))


def locate_ffmpeg(binary):
    # System PATH is preferred. A portable copy may be placed in the tools folder.
    path = shutil.which(binary)
    if path:
        return path
    here = Path(__file__).resolve().parent
    for candidate in (here / 'tools' / f'{binary}.exe', here / 'tools' / binary):
        if candidate.is_file():
            return str(candidate)
    return None


def probe(path):
    ffprobe = locate_ffmpeg('ffprobe')
    if not ffprobe:
        raise RuntimeError('Не найден ffprobe. Установите FFmpeg и добавьте его в PATH.')
    command = [ffprobe, '-v', 'error', '-show_entries',
               'format=duration,size:stream=codec_type,width,height,avg_frame_rate',
               '-of', 'json', str(path)]
    p = process(command, timeout=90)
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8', 'replace')[-300:])
    obj = json.loads(p.stdout)
    fmt = obj.get('format', {})
    streams = obj.get('streams', [])
    video = next((x for x in streams if x.get('codec_type') == 'video'), {})
    return {
        'duration': float(fmt.get('duration') or 0),
        'size': int(fmt.get('size') or Path(path).stat().st_size),
        'width': int(video.get('width') or 0),
        'height': int(video.get('height') or 0),
        'audio': any(x.get('codec_type') == 'audio' for x in streams),
    }


def _safe_float(x, default=0):
    try:
        return float(x)
    except (ValueError, TypeError):
        return default


def _percentile(a, percentile):
    if not a:
        return 0.
    s = sorted(a)
    index = int((len(s) - 1) * percentile)
    return s[index]


def _mean(values):
    return sum(values) / len(values) if values else 0


def audio_envelope(path, duration, stop, on_progress=None, threads=2):
    """Stream mono 8 kHz PCM; retain 0.5-second RMS, not the full sound."""
    ffmpeg = locate_ffmpeg('ffmpeg')
    cmd = [ffmpeg, '-v', 'error', '-nostdin', '-threads', str(threads), '-i', str(path), '-vn',
           '-ac', '1', '-ar', '8000', '-f', 's16le', 'pipe:1']
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, creationflags=(0x08000000 if os.name == 'nt' else 0))
    levels = []
    try:
        step_bytes = 8000  # 4000 16-bit samples = 0.5 seconds
        while not stop.is_set():
            block = p.stdout.read(step_bytes)
            if not block:
                break
            # FFmpeg writes aligned audio; pad odd trailing byte if needed.
            arr = array.array('h')
            arr.frombytes(block[:len(block) // 2 * 2])
            if not arr:
                break
            samples = arr[::4]
            rms = math.sqrt(sum(v*v for v in samples) / len(samples)) / 32768
            levels.append(round(rms, 5))
            if on_progress and len(levels) % 120 == 0:
                on_progress(min(1, (len(levels) / 2) / max(1, duration)))
        if stop.is_set():
            p.terminate()
            raise InterruptedError('Анализ остановлен пользователем')
        p.wait(timeout=20)
        if p.returncode:
            error = p.stderr.read().decode('utf-8', 'replace')[-400:]
            raise RuntimeError('Ошибка анализа аудио: ' + error)
    finally:
        if p.poll() is None:
            p.kill()
        if p.stdout:
            p.stdout.close()
        if p.stderr:
            p.stderr.close()
    return levels


def motion_envelope(path, stop, on_progress=None, threads=2):
    """Slow optional motion pass (0.5 FPS, 96x54 gray); no video kept in memory."""
    ffmpeg = locate_ffmpeg('ffmpeg')
    size = 96 * 54
    cmd = [ffmpeg, '-v', 'error', '-nostdin', '-threads', str(threads), '-i', str(path), '-an',
           '-filter_threads', str(threads), '-vf', 'fps=1/2,scale=96:54,format=gray', '-f', 'rawvideo', 'pipe:1']
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, creationflags=(0x08000000 if os.name == 'nt' else 0))
    values, previous = [], None
    try:
        while not stop.is_set():
            frame = p.stdout.read(size)
            if not frame or len(frame) != size:
                break
            if previous is not None:
                delta = sum(abs(a-b) for a, b in zip(frame[::4], previous[::4])) / (len(frame[::4]) * 255)
                values.append(round(delta, 4))
            else:
                values.append(0)
            previous = frame
        if stop.is_set():
            p.terminate()
            raise InterruptedError('Анализ остановлен пользователем')
        p.wait(timeout=20)
        if p.returncode:
            raise RuntimeError(p.stderr.read().decode('utf-8', 'replace')[-300:])
    finally:
        if p.poll() is None:
            p.kill()
        if p.stdout:
            p.stdout.close()
        if p.stderr:
            p.stderr.close()
    return values


def transcribe(path, model, stop, language='ru'):
    segments, info = model.transcribe(str(path), language=language, vad_filter=True,
                                      beam_size=3, condition_on_previous_text=False)
    out = []
    for s in segments:
        if stop.is_set():
            raise InterruptedError('Распознавание остановлено')
        t = (s.text or '').strip()
        if t:
            out.append({'start': round(s.start, 2), 'end': round(s.end, 2), 'text': t,
                        'humor': 0})
    return out


def ollama_rank(segments, model, stop):
    """Local LLM optional. Only segment indices are accepted from JSON output."""
    if not model:
        return
    for b in range(0, len(segments), 35):
        if stop.is_set():
            raise InterruptedError('Остановлено')
        batch = segments[b:b+35]
        question = ('Оцени сегменты транскрипта игрового видео для динамичного юмористического монтажа. '
                    'Сохраняй подводки к шуткам и их развязки. Не считай мат сам по себе шуткой. '
                    'Выведи ТОЛЬКО JSON вида {"scores":{"0":0,"1":3,...}}; баллы 0..5. '
                    '0 — неинтересно; 5 — самостоятельная яркая реакция, фейл, панчлайн или неожиданность. '
                    'Только переданные ID.\n' + '\n'.join(f'{i}: {s["text"]}' for i,s in enumerate(batch)))
        data = json.dumps({'model': model, 'prompt': question, 'stream': False,
                           'format': 'json', 'options': {'temperature': 0.1}}).encode('utf-8')
        request = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=data,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=300) as response:
            answer = json.loads(response.read())
        ranks = json.loads(answer.get('response', '{}')).get('scores', {})
        if isinstance(ranks, dict):
            for i, s in enumerate(batch):
                s['humor'] = min(5, max(0, _safe_float(ranks.get(str(i), 0))))


def _slice(values, rate, start, end):
    if not values:
        return []
    a, b = max(0, int(start*rate)), max(1, int(end*rate))
    return values[a:min(len(values), b)]


def clip_score(start, end, levels, motion, text='', humor=0):
    l = _slice(levels, 2, start, end)
    m = _slice(motion, 0.5, start, end)
    base = _percentile(levels, 0.5) if levels else 0.01
    loud = _percentile(l, 0.88) if l else 0
    signal = min(1, loud / max(0.012, base * 3))
    activity = min(1, (_mean(m) / max(0.008, _percentile(motion, 0.6) * 1.3))) if m else 0
    t = text.lower()
    phrase = sum(1 for k in KEYWORDS if k in t)
    bonuses = min(1, phrase * 0.20 + t.count('!') * .08 + t.count('?') * .08)
    semantics = min(1, humor / 5)
    return round(min(100, 16 + signal*25 + activity*12 + bonuses*20 + semantics*35), 1)


def generate_candidates(file):
    d = file.get('duration', 0)
    a = file.get('analysis', {})
    levels, motion, segs = a.get('audio_levels', []), a.get('motion_levels', []), a.get('transcript', [])
    candidates = []
    if segs:
        # Groups preserve setup -> punchline rather than splitting every silence.
        group = []
        groups = []
        for s in segs:
            if group and (s['start'] - group[-1]['end'] > 5.5 or s['end'] - group[0]['start'] > 33):
                groups.append(group)
                group = []
            group.append(s)
        if group:
            groups.append(group)
        for group in groups:
            start, end = max(0, group[0]['start'] - 3.0), min(d, group[-1]['end'] + 3.0)
            if end-start < 3:
                end = min(d, start+3)
            label = ' '.join(s['text'] for s in group)
            bonus = max(s.get('humor', 0) for s in group)
            score = clip_score(start,end,levels,motion,label,bonus)
            candidates.append({'start': round(start,2), 'end':round(end,2), 'score':score,
                               'label':label[:160], 'type':'dialogue'})
    # Acoustic peaks produce additional candidates for wordless gameplay highlights.
    if levels:
        floor = _percentile(levels, 0.65)
        threshold = max(0.022, _percentile(levels, 0.9), floor * 2.2)
        scored = []
        for i in range(4, len(levels)-4):
            if levels[i] > threshold and levels[i] >= max(levels[i-4:i+5]):
                scored.append((levels[i], i*.5))
        scored.sort(reverse=True)
        chosen = []
        for peak, mid in scored:
            if all(abs(mid-prev)>8 for prev in chosen):
                chosen.append(mid)
            if len(chosen) >= max(12, int(d//35)):
                break
        for mid in chosen:
            start, end = max(0, mid-4.5), min(d, mid+6.5)
            if any(max(0, min(end,c['end'])-max(start,c['start'])) > 0.45*(end-start) for c in candidates):
                continue
            candidates.append({'start':round(start,2), 'end':round(end,2),
                               'score':clip_score(start,end,levels,motion),
                               'label':'Активный игровой момент (проверь вручную)', 'type':'action'})
    # Wordless reactions/actions: optional visual activity peaks.
    if motion:
        limit=max(0.022, _percentile(motion, 0.88))
        ranked=sorted([(v, i*2.0) for i,v in enumerate(motion) if v>=limit],reverse=True)
        hits=[]
        for val, t in ranked:
            if all(abs(t-x)>10 for x in hits):
                hits.append(t)
            if len(hits)>=max(10,int(d//60)):
                break
        for t in hits:
            start, end=max(0,t-4),min(d,t+8)
            if end-start<3 or any(max(0,min(end,c['end'])-max(start,c['start'])) > .45*(end-start) for c in candidates):
                continue
            candidates.append({'start':round(start,2), 'end':round(end,2),
                               'score':clip_score(start,end,levels,motion),
                               'label':'Визуально активный игровой момент (проверь)', 'type':'motion'})
    return candidates


class Studio:
    def __init__(self, work_dir=None):
        # Reuse existing Alpha data without moving potentially large render/cache files.
        legacy_dir = Path.home() / 'Zeihos AI Montage Studio'
        branded_dir = Path.home() / 'CLIPTORA'
        default_dir = (legacy_dir if legacy_dir.joinpath('project.json').exists() and
                       not branded_dir.joinpath('project.json').exists() else branded_dir)
        self.work_dir = Path(work_dir or default_dir).expanduser().resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.meta = self.work_dir/'project.json'
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.worker = None
        self.task = ''
        self.progress = 0
        self.message = ''
        self.error = ''
        self.events = []
        self.scan_backend = 'not scanned'
        if self.meta.exists():
            try:
                self.project = json.loads(self.meta.read_text(encoding='utf-8'))
            except Exception:
                self.project = self._blank()
        else:
            self.project = self._blank()
        self.project['version'] = '0.1.6'
        self._sync_analysis_jobs(recover_running=True)
        self._save()

    def _blank(self):
        return {'version':'0.1.6','source_dir':'','files':[],'clips':[], 'analysis_jobs':{},
                'target_minutes':12, 'settings':{'vision':False, 'whisper':True,
                'whisper_model':'small', 'ollama_model':'', 'cpu_threads':2},'last_output':''}

    def _save(self):
        with self.lock:
            tmp = self.meta.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(self.project,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(tmp,self.meta)

    def log(self, msg):
        with self.lock:
            self.message = msg
            self.events.append(f'[{datetime.datetime.now():%H:%M:%S}] {msg}')
            self.events = self.events[-160:]

    def analysis_signature(self):
        """Fingerprint settings to avoid accidentally reusing stale AI results.

        When Whisper is installed later, its availability changes the signature
        so an audio-only fallback is not mistaken for a completed transcript.
        """
        s = self.project.get('settings', {})
        use_whisper = bool(s.get('whisper'))
        return json.dumps({
            'vision': bool(s.get('vision')),
            'whisper': use_whisper,
            'whisper_ready': self.whisper_available() if use_whisper else False,
            'whisper_model': str(s.get('whisper_model', 'small')) if use_whisper else '',
            'ollama_model': str(s.get('ollama_model', '')) if use_whisper else '',
        }, sort_keys=True, ensure_ascii=False)

    def _current_analysis(self, file):
        return bool(file.get('analyzed') and
                    file.get('analysis_signature') == self.analysis_signature())

    def _sync_analysis_jobs(self, recover_running=False):
        """Keep per-video queue state durable across scan, restart and settings changes."""
        with self.lock:
            old = self.project.get('analysis_jobs', {})
            if not isinstance(old, dict):
                old = {}
            signature = self.analysis_signature()
            jobs = {}
            for file in self.project.get('files', []):
                mid = file['id']
                done = bool(file.get('analyzed') and file.get('analysis_signature') == signature)
                previous = old.get(mid, {})
                if not isinstance(previous, dict) or previous.get('signature') != signature:
                    previous = {}
                state = 'complete' if done else previous.get('state', 'pending')
                if state == 'complete' and not done:
                    state = 'pending'
                if recover_running and state == 'running':
                    state = 'pending'
                if state not in ('pending', 'running', 'complete', 'failed'):
                    state = 'pending'
                jobs[mid] = {'state': state, 'signature': signature,
                             'attempts': int(previous.get('attempts', 0)),
                             'error': str(previous.get('error', ''))[:300] if state == 'failed' else ''}
            self.project['analysis_jobs'] = jobs
            return jobs

    def status(self):
        with self.lock:
            signature = self.analysis_signature()
            files = [{**{k:v for k,v in f.items() if k != 'analysis'},
                      'analyzed':bool(f.get('analyzed') and f.get('analysis_signature') == signature),
                      'analysis_state': self.project.get('analysis_jobs', {}).get(f['id'], {}).get('state', 'pending'),
                      'analysis_error': self.project.get('analysis_jobs', {}).get(f['id'], {}).get('error', '')}
                     for f in self.project['files']]
            clips = self.project['clips']
            jobs = self.project.get('analysis_jobs', {})
            counts = {state: sum(1 for j in jobs.values() if j.get('state') == state)
                      for state in ('pending', 'running', 'complete', 'failed')}
            counts['total'] = len(files)
            return {'analysis_queue': counts, 'busy':bool(self.worker and self.worker.is_alive()),'task':self.task,
                    'progress':round(self.progress,2),'message':self.message,'error':self.error,
                    'events':self.events[-70:],'source_dir':self.project.get('source_dir',''),
                    'work_dir':str(self.work_dir), 'files':files,'clips':clips,
                    'target_minutes':self.project.get('target_minutes',12),
                    'settings':self.project.get('settings',{}),
                    'last_output':self.project.get('last_output',''),
                    'ffmpeg':bool(locate_ffmpeg('ffmpeg')),'ffprobe':bool(locate_ffmpeg('ffprobe')),
                    'whisper_installed':self.whisper_available(),
                    'rust_scanner_available':bool(locate_scanner()),
                    'scan_backend':self.scan_backend,
                    'total_bytes':sum(f.get('size',0) for f in files),
                    'total_seconds':sum(f.get('duration',0) for f in files)}

    @staticmethod
    def whisper_available():
        try:
            import importlib.util
            return importlib.util.find_spec('faster_whisper') is not None
        except ImportError:
            return False

    def schedule(self, name, func, *args, **kwargs):
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise RuntimeError('Уже идёт задача. Дождитесь окончания или остановите её.')
            self.stop.clear()
            self.progress=0
            self.task=name
            self.error=''
            def run():
                try:
                    self.log('Начато: '+name)
                    func(*args,**kwargs)
                    self.progress=1
                    if not self.error:
                        self.log('Завершено: '+name)
                except InterruptedError as e:
                    self.log(str(e))
                except Exception as e:
                    self.error=str(e)
                    self.log('ОШИБКА: '+str(e))
                finally:
                    self._save()
            self.worker=threading.Thread(target=run,daemon=True)
            self.worker.start()

    def configure(self, source_dir, settings=None):
        if self.worker and self.worker.is_alive():
            raise RuntimeError('Нельзя менять папку во время обработки')
        folder = Path(source_dir).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError(f'Папка не найдена: {folder}')
        # Prevent scanning output renders as sources on later runs.
        if folder == self.work_dir or self.work_dir.is_relative_to(folder):
            raise ValueError('Папка проекта должна находиться вне папки исходников.')
        if settings and 'cpu_threads' in settings:
            count = settings['cpu_threads']
            if type(count) is not int or not 1 <= count <= 8:
                raise ValueError('Потоки CPU: выберите целое число от 1 до 8.')
        with self.lock:
            changed = str(folder) != self.project.get('source_dir')
            self.project['source_dir'] = str(folder)
            if changed:
                self.project['files']=[]
                self.project['clips']=[]
                self.project['analysis_jobs']={}
            before_signature = self.analysis_signature()
            if settings:
                self.project['settings'].update({k:v for k,v in settings.items()
                                                  if k in ('vision','whisper','whisper_model','ollama_model','cpu_threads')})
            if before_signature != self.analysis_signature():
                for f in self.project['files']:
                    f['analyzed'] = False
            self._sync_analysis_jobs()
            self._save()

    def reset_analysis(self):
        if self.worker and self.worker.is_alive():
            raise RuntimeError('Сначала остановите текущую задачу')
        for f in self.project['files']:
            f.pop('analysis', None)
            f['analyzed']=False
        self.project['clips']=[]
        self.project['analysis_jobs'] = {}
        self._sync_analysis_jobs()
        self._save()
        self.log('Анализ сброшен. Исходные файлы не затронуты.')

    def scan(self):
        configured = self.project.get('source_dir','')
        if not configured:
            raise RuntimeError('Сначала укажите папку с видео.')
        root = Path(configured)
        if not root.is_dir():
            raise RuntimeError('Сначала укажите папку с видео.')
        metadata, backend = discover(root, self.stop, self.log)
        items=[]
        old = {f['path']:f for f in self.project['files']}
        # Never recycle IDs: reviewed clips depend on stable media IDs.
        known_numbers = [int(f['id'][1:]) for f in old.values()
                         if re.fullmatch(r'm[0-9]+', str(f.get('id', '')))]
        next_id = max(known_numbers, default=-1) + 1
        count=0
        for entry in metadata:
            if self.stop.is_set():
                raise InterruptedError('Сканирование остановлено')
            path = Path(entry['path'])
            try:
                size = entry['size']
                mtime_ns = entry['mtime_ns']
                # Old 0.1.4 project files have floating-point mtime but no mtime_ns.
                # Dividing nanoseconds by 1e9 mirrors Python's st_mtime conversion.
                mtime = mtime_ns / 1e9
                prev = old.get(str(path))
                same_time = (prev.get('mtime_ns') == mtime_ns if 'mtime_ns' in prev
                             else abs(float(prev.get('mtime', 0)) - mtime) <= 1e-6) if prev else False
                if prev and prev.get('size') == size and same_time:
                    item = prev.copy()
                    item['mtime_ns'] = mtime_ns
                else:
                    details=probe(path)
                    if details['width'] <= 0 or details['duration'] <= 0:
                        continue
                    item={'id':f'm{next_id:06d}','name':path.name,'path':str(path),
                          'relative':str(path.relative_to(root)),**details,
                          'size':size, 'mtime':mtime, 'mtime_ns':mtime_ns,
                          'analyzed':False}
                    next_id += 1
                items.append(item)
                count+=1
                if count % 20==0:
                    self.log(f'Обнаружено файлов: {count}')
            except Exception as exc:
                self.log(f'Пропущено {path.name}: {exc}')
        items.sort(key=lambda x: (x.get('mtime',0),x['path']))
        with self.lock:
            valid_ids={f['id'] for f in items}
            before_clips=len(self.project['clips'])
            self.project['files']=items
            self.scan_backend=backend
            # Preserve user review/edit decisions for unchanged source recordings.
            self.project['clips']=[c for c in self.project['clips'] if c['media_id'] in valid_ids]
            removed_clips=before_clips-len(self.project['clips'])
            self._sync_analysis_jobs()
            self._save()
        self.log(f'Найдено {len(items)} видео, {sum(x.get("size",0) for x in items)/1024**3:.1f} ГБ; '
                 f'сохранено {len(self.project["clips"])} фрагментов, удалено ссылок на изменённые/исчезнувшие: {removed_clips}')

    def analyze(self):
        """Process the on-disk per-video queue; a crashed run resumes unfinished files."""
        with self.lock:
            self.error = ''
            if not self.project['files']:
                raise RuntimeError('Сначала запустите сканирование')
            jobs = self._sync_analysis_jobs()
            signature = self.analysis_signature()
            files = list(self.project['files'])
            todo = [f for f in files if jobs[f['id']]['state'] != 'complete']
            if not todo:
                self.progress=1
                self.log('Все записи уже проанализированы с текущими настройками.')
                return
            if not locate_ffmpeg('ffmpeg'):
                raise RuntimeError('Не найден FFmpeg. См. УСТАНОВКА.txt')
            threads = int(self.project['settings'].get('cpu_threads', 2))
            settings = self.project['settings'].copy()
        model = None
        if settings.get('whisper') and self.whisper_available():
            self.log('Загрузка модели Whisper (при первом запуске может потребоваться Интернет)...')
            from faster_whisper import WhisperModel
            model = WhisperModel(settings.get('whisper_model', 'small'), device='cpu',
                                 compute_type='int8', cpu_threads=threads, num_workers=1)
        elif settings.get('whisper'):
            self.log('Whisper не установлен: распознавание речи пропущено. Смотрите УСТАНОВКА.txt')

        failed = 0
        total = len(todo)
        for i, file in enumerate(todo):
            if self.stop.is_set():
                raise InterruptedError('Обработка остановлена; очередь сохранена')
            mid = file['id']
            job = jobs[mid]
            with self.lock:
                job['state'] = 'running'
                job['attempts'] += 1
                job['error'] = ''
                self._save()
            self.log(f'Анализ {i+1}/{total}: {file["relative"]} (CPU: {threads} потоков)')
            try:
                stat = Path(file['path']).stat()
                if stat.st_size != file['size'] or ('mtime_ns' in file and stat.st_mtime_ns != file['mtime_ns']):
                    raise RuntimeError('Исходный файл изменился. Повторно просканируйте библиотеку.')
                audio = audio_envelope(file['path'], file['duration'], self.stop, threads=threads) if file.get('audio') else []
                segments = []
                if model and file.get('audio'):
                    self.log('Распознаю речь: '+file['name'])
                    segments = transcribe(file['path'], model, self.stop)
                motion = []
                if settings.get('vision'):
                    self.log('Анализ движения кадров: '+file['name'])
                    motion = motion_envelope(file['path'], self.stop, threads=threads)
                if segments and settings.get('ollama_model'):
                    self.log('Контекстная оценка диалогов локальным Ollama')
                    try:
                        ollama_rank(segments, settings['ollama_model'], self.stop)
                    except InterruptedError:
                        raise
                    except Exception as exc:
                        self.log('Ollama недоступна (использую эвристику): '+str(exc)[:180])
                if self.stop.is_set():
                    raise InterruptedError('Обработка остановлена; очередь сохранена')
                with self.lock:
                    file['analysis'] = {'audio_levels': audio, 'motion_levels': motion, 'transcript': segments}
                    file['analyzed'] = True
                    file['analysis_signature'] = signature
                    job['state'] = 'complete'
                    job['error'] = ''
                    self._save()
                self.log(f'Готово: {file["name"]}; реплик {len(segments)}; аудио-окон {len(audio)}')
            except InterruptedError:
                with self.lock:
                    job['state'] = 'pending'
                    self._save()
                raise
            except Exception as exc:
                failed += 1
                with self.lock:
                    job['state'] = 'failed'
                    job['error'] = str(exc)[:300]
                    self._save()
                self.log(f'Не удалось обработать {file["name"]}: {str(exc)[:200]}')
            finally:
                self.progress = (i+1)/total
        if failed:
            self.error = f'Не удалось обработать {failed} из {total} записей. Нажмите «Продолжить анализ» для повторной попытки.'
            self.log(self.error)
        else:
            self.log(f'Очередь обработана: {total} записей. Прогресс сохранён.')

    def plan(self,target_minutes=12):
        files=self.project['files']
        if not files or not any(self._current_analysis(f) for f in files):
            raise ValueError('Сначала выполните анализ видео с текущими настройками')
        target_seconds=max(30,min(2*3600,int(float(target_minutes)*60)))
        all_candidates=[]
        for f in files:
            if not self._current_analysis(f):
                continue
            for c in generate_candidates(f):
                c['media_id']=f['id']
                c['source_name']=f['name']
                all_candidates.append(c)
        all_candidates.sort(key=lambda x: x['score'],reverse=True)
        selected=[]
        used=0
        counts={}
        # Greedy, with a modest file diversity penalty.
        while all_candidates and used<target_seconds and len(selected)<240:
            all_candidates.sort(key=lambda x: x['score']-min(18,counts.get(x['media_id'],0)*1.1),reverse=True)
            c=all_candidates.pop(0)
            if any(x['media_id']==c['media_id'] and max(0,min(x['end'],c['end'])-max(x['start'],c['start']))>0.3 for x in selected):
                continue
            if used+(c['end']-c['start'])>target_seconds+8 and used>target_seconds*.65:
                continue
            selected.append(c)
            used+=c['end']-c['start']
            counts[c['media_id']]=counts.get(c['media_id'],0)+1
        # Each file stays chronological; shots from different recording sessions are grouped.
        order={f['id']:i for i,f in enumerate(files)}
        selected.sort(key=lambda x:(order[x['media_id']],x['start']))
        for i,c in enumerate(selected):
            c.update({'id':f'c{i:05d}','enabled':True,'zoom':c['score']>=68})
        self.project['clips']=selected
        self.project['target_minutes']=float(target_minutes)
        self._save()
        self.log(f'Собран черновой план: {len(selected)} фрагментов, {used/60:.1f} минут. Проверьте список перед экспортом!')
        return selected

    def add_clip(self, media_id, start, end):
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise RuntimeError('Не изменяйте монтаж во время экспорта/анализа')
            f=next((f for f in self.project['files'] if f['id']==media_id),None)
            if f is None:
                raise ValueError('Запись не найдена')
            a,b=_safe_float(start,-1),_safe_float(end,-1)
            if not (0 <= a < b <= f['duration']):
                raise ValueError('Неверные границы')
            nums=[int(c['id'][1:]) for c in self.project['clips'] if c['id'].startswith('c') and c['id'][1:].isdigit()]
            next_id=max(nums,default=-1)+1
            c={'id':f'c{next_id:05d}','media_id':f['id'],'source_name':f['name'],
               'start':round(a,2),'end':round(b,2),'score':100,'label':'Выбран вручную',
               'type':'manual','enabled':True,'zoom':False}
            self.project['clips'].append(c)
            order={f['id']:i for i,f in enumerate(self.project['files'])}
            self.project['clips'].sort(key=lambda x:(order.get(x['media_id'],0),x['start']))
            self._save()
            self.log('Добавлен вручную фрагмент: '+f['name'])
            return c

    def edit_clip(self, clip_id, **data):
        with self.lock:
            for c in self.project['clips']:
                if c['id']==clip_id:
                    f=next((x for x in self.project['files'] if x['id']==c['media_id']),None)
                    if not f:
                        raise RuntimeError('Исходник не найден')
                    a=_safe_float(data.get('start',c['start']),c['start'])
                    b=_safe_float(data.get('end',c['end']),c['end'])
                    if not(0<=a<b<=f['duration']):
                        raise ValueError('Неверные границы фрагмента')
                    c['start']=round(a,2)
                    c['end']=round(b,2)
                    if 'enabled' in data:
                        c['enabled']=bool(data['enabled'])
                    if 'zoom' in data:
                        c['zoom']=bool(data['zoom'])
                    if 'label' in data:
                        c['label']=str(data['label'])[:220]
                    self._save()
                    return c
        raise KeyError(clip_id)

    def srt_content(self, selected):
        result=[]
        video_by_id={f['id']:f for f in self.project['files']}
        timeline=0.0
        for clip in selected:
            audio=video_by_id[clip['media_id']].get('analysis',{})
            for seg in audio.get('transcript',[]):
                if seg['end'] <= clip['start'] or seg['start'] >= clip['end']:
                    continue
                a=max(0,seg['start']-clip['start'])+timeline
                b=min(clip['end'],seg['end'])-clip['start']+timeline
                if b-a>0.20:
                    result.append((a,b,seg['text']))
            timeline+=clip['end']-clip['start']
        def stamp(t):
            ms=round(t*1000)
            return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
        return ''.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n' for i,(a,b,text) in enumerate(result,1))

    def render(self, height=720, burn_subtitles=False):
        # Freeze edits during export so UI changes cannot alter an in-flight render.
        selected=[dict(c) for c in self.project['clips'] if c.get('enabled')]
        if not selected:
            raise RuntimeError('Все фрагменты исключены. Нечего экспортировать')
        ffmpeg=locate_ffmpeg('ffmpeg')
        if not ffmpeg:
            raise RuntimeError('Не найден FFmpeg')
        height=int(height)
        if height not in (480,720,1080):
            raise ValueError('Разрешение: 480, 720 или 1080')
        width=int(height*16/9)//2*2
        runs=self.work_dir/'renders'
        runs.mkdir(exist_ok=True)
        now=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output=runs/f'CLIPTORA_{now}_{height}p.mp4'
        tmp_dir=self.work_dir/'cache'/now
        tmp_dir.mkdir(parents=True,exist_ok=True)
        map_files={f['id']:f for f in self.project['files']}
        joined=[]
        try:
            for i,c in enumerate(selected):
                if self.stop.is_set():
                    raise InterruptedError('Экспорт остановлен')
                media=map_files[c['media_id']]
                outfile=tmp_dir/f'part_{i:04}.mp4'
                dur=c['end']-c['start']
                vfilter=(f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                         f'crop={width}:{height},setsar=1,fps=30')
                if c.get('zoom'):
                    scale_w=int(width*1.08)//2*2
                    scale_h=int(height*1.08)//2*2
                    vfilter=(f'scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,'
                             f'crop={width}:{height},setsar=1,fps=30')
                cmd=[ffmpeg,'-y','-v','error','-nostdin','-ss',str(c['start']),
                     '-i',media['path']]
                if not media.get('audio'):
                    cmd+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
                cmd+=['-t',str(dur),'-map','0:v:0','-map',('0:a:0' if media.get('audio') else '1:a:0'),
                      '-vf',vfilter,'-af','aresample=48000',
                      '-c:v','libx264','-preset','veryfast','-crf','22',
                      '-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','160k',
                      '-ar','48000','-ac','2','-movflags','+faststart',str(outfile)]
                p=process(cmd,timeout=3600)
                if p.returncode:
                    raise RuntimeError(f'Ошибка кодирования клипа {i+1}: '+p.stderr.decode('utf-8','replace')[-500:])
                joined.append(outfile)
                self.progress=(i+1)/(len(selected)+1)
                self.log(f'Клип {i+1}/{len(selected)}: {media["name"]}')
            # Concat demuxer avoids holding all originals or frames in RAM.
            concat=tmp_dir/'concat.txt'
            def ffconcat_path(x):
                return str(x.resolve()).replace('\\','/').replace("'", "'\\''")
            concat.write_text(''.join(f"file '{ffconcat_path(x)}'\n" for x in joined),encoding='utf-8')
            p=process([ffmpeg,'-y','-v','error','-nostdin','-f','concat','-safe','0',
                       '-i',str(concat),'-c','copy','-movflags','+faststart',str(output)],timeout=3600)
            if p.returncode:
                raise RuntimeError('Ошибка объединения: '+p.stderr.decode('utf-8','replace')[-500:])
            srt=output.with_suffix('.srt')
            srt.write_text(self.srt_content(selected),encoding='utf-8-sig')
            manifest=output.with_suffix('.json')
            manifest.write_text(json.dumps({'source_dir':self.project['source_dir'],
                         'clips':selected,'rendered_to':str(output)},ensure_ascii=False,indent=2),encoding='utf-8')
            # Burn only if there are ASR subtitles and user explicitly requested it.
            if burn_subtitles and srt.stat().st_size>10:
                subbed=output.with_name(output.stem+'_captions.mp4')
                escaped=str(srt).replace('\\','/').replace(':','\\:').replace("'", "\\'")
                p=process([ffmpeg,'-y','-v','error','-nostdin','-i',str(output),
                           '-vf',f"subtitles='{escaped}'",'-c:v','libx264','-preset','veryfast',
                           '-crf','22','-c:a','copy',str(subbed)],timeout=3600)
                if not p.returncode:
                    output=subbed
                else:
                    self.log('Не удалось встроить субтитры; отдельный SRT сохранён')
            self.project['last_output']=str(output)
            self._save()
            self.log('Файл готов: '+str(output))
            return output
        finally:
            # Cache cleanup is best-effort and never touches sources.
            shutil.rmtree(tmp_dir,ignore_errors=True)
