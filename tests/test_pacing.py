"""Regressions: pacing must not lose speech/action or alter saved manual clips."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pacing import plan_pacing, validate_pacing
from engine import Studio
from montage_preview import preview_signature


def fixture(duration=10, *, gap=(2, 7), motion=None):
    audio = [0.002] * (duration * 2)
    for a, b in ((1, 2), (7, 8)):
        for i in range(a * 2, b * 2):
            audio[i] = 0.18
    transcript = [
        {'start': 1.0, 'end': float(gap[0]), 'text': 'Смотри, сейчас!'},
        {'start': float(gap[1]), 'end': 8.0, 'text': 'АА, получилось!'},
    ]
    media = {'m': {'id': 'm', 'duration': duration,
                    'analysis': {'audio_levels': audio, 'transcript': transcript,
                                 'motion_levels': motion if motion is not None else []}}}
    clips = [{'id': 'c1', 'media_id': 'm', 'start': 0.0, 'end': float(duration),
              'enabled': True, 'zoom': True, 'label': 'ручной клип'}]
    return clips, media


class PacingTests(unittest.TestCase):
    def test_bad_modes_rejected_without_coercion(self):
        for value in ('wrong', True, 1, None, ' FAST '):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_pacing(value)
        for mode in ('normal', 'dynamic', 'fast'):
            self.assertEqual(validate_pacing(mode), mode)

    def test_default_mode_does_not_change_manual_timing(self):
        clips, media = fixture()
        old = copy.deepcopy(clips)
        result, stats = plan_pacing(clips, media, 'normal')
        self.assertEqual(result, old)
        self.assertEqual(stats['cuts'], 0)
        self.assertEqual(stats['removed_seconds'], 0)

    def test_dynamic_shortens_only_long_quiet_between_speech(self):
        clips, media = fixture()
        old = copy.deepcopy(clips)
        result, stats = plan_pacing(clips, media, 'dynamic')
        self.assertEqual([(r['start'],r['end']) for r in result], [(0.,2.4),(6.6,10.)])
        self.assertEqual(stats['cuts'], 1)
        self.assertAlmostEqual(stats['removed_seconds'],4.2)
        self.assertTrue(all(r['zoom'] for r in result))
        self.assertEqual(clips, old, 'Original draft must not be edited')

    def test_gameplay_sound_in_gap_prevents_cut(self):
        clips, media = fixture()
        media['m']['analysis']['audio_levels'][9] = .12
        segments, stats = plan_pacing(clips, media, 'fast')
        self.assertEqual(len(segments), 1)
        self.assertEqual(stats['cuts'],0)

    def test_gameplay_motion_in_gap_prevents_cut(self):
        motion = [0.001] * 6
        motion[2] = .15
        clips, media = fixture(motion=motion)
        segments, stats = plan_pacing(clips, media, 'dynamic')
        self.assertEqual(len(segments),1)
        self.assertEqual(stats['cuts'],0)

    def test_no_transcript_or_audio_leaves_clip_untouched(self):
        clips, media = fixture()
        for key in ('transcript','audio_levels'):
            updated = copy.deepcopy(media)
            updated['m']['analysis'][key] = []
            segments, stats = plan_pacing(clips,updated,'fast')
            self.assertEqual(segments, clips)
            self.assertEqual(stats['removed_seconds'], 0)

    def test_fast_trims_short_gap_but_dynamic_preserves_it(self):
        clips, media = fixture(duration=10, gap=(2,3.5))
        d, ds = plan_pacing(clips, media, 'dynamic')
        f, fs = plan_pacing(clips, media, 'fast')
        self.assertEqual(ds['cuts'],0)
        self.assertEqual(fs['cuts'],1)
        self.assertEqual([(x['start'],x['end']) for x in f], [(0.,2.25),(3.25,10.)])

    def test_one_clip_cannot_exceed_safe_cut_count(self):
        # A noisy 20-hour transcript should not spawn hundreds of tiny encode tasks.
        clips = [
            {'id': 'first','media_id': 'm','start':0.,'end':165.,'enabled':True},
            {'id': 'second','media_id':'m','start':165.,'end':169.,'enabled':True},
        ]
        transcript=[{'start':1.+4*i,'end':1.6+4*i,'text':'Реплика'} for i in range(40)]
        media={'m':{'analysis':{'audio_levels':[0.001]*338,'transcript':transcript}}}
        result, stats = plan_pacing(clips, media, 'fast')
        self.assertLessEqual(len([x for x in result if x['id']=='first']), 25)
        self.assertEqual(len([x for x in result if x['id']=='second']), 1)
        self.assertLessEqual(stats['cuts'],24)

    def test_preview_invalidation_depends_on_pacing_setting(self):
        clips, media = fixture()
        files = list(media.values())
        base = preview_signature(clips,files,False,0,'normal')
        self.assertNotEqual(base, preview_signature(clips,files,False,0,'fast'))


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and ffprobe required')
class PacingExportTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root=Path(td.name)
        self.source=root/'game.mp4'
        cmd=['ffmpeg','-y','-v','error','-nostdin', '-f','lavfi','-i','testsrc2=s=320x180:r=30:d=10',
             '-f','lavfi','-i','sine=frequency=600:sample_rate=48000:duration=10',
             '-shortest','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',str(self.source)]
        p=subprocess.run(cmd,capture_output=True,timeout=60)
        self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'))
        self.app=Studio(root/'project')
        clips, media=fixture()
        media['m'].update({'path':str(self.source),'name':'game.mp4', 'audio':True,
                           'size':self.source.stat().st_size,'mtime_ns':self.source.stat().st_mtime_ns})
        self.app.project['source_dir']=str(root)
        self.app.project['files']=[media['m']]
        self.app.project['clips']=clips
        self.app.project['last_output']='old-good.mp4'
        self.app._save()

    def duration(self,path):
        cmd=['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)]
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stderr)
        return float(p.stdout)

    def test_preview_and_export_use_same_tempo_without_mutating_draft(self):
        original=copy.deepcopy(self.app.project['clips'])
        preview=self.app.render_preview(False,0,'dynamic')
        self.assertAlmostEqual(self.duration(preview),5.8,delta=.4)
        info=self.app.status()['montage_preview']
        self.assertEqual(info['pacing'],'dynamic')
        self.assertAlmostEqual(info['removed_seconds'],4.2)
        self.assertEqual(self.app.project['last_output'],'old-good.mp4')
        final=self.app.render(480,False,False,0,pacing='dynamic')
        self.assertAlmostEqual(self.duration(final),5.8,delta=.4)
        self.assertEqual(original,self.app.project['clips'])
        meta=json.loads(final.with_suffix('.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['pacing']['mode'],'dynamic')
        self.assertEqual(meta['pacing']['cuts'],1)
        self.assertEqual(len(meta['clips']),2)
        self.assertIn('Смотри',final.with_suffix('.srt').read_text(encoding='utf-8-sig'))
        self.assertIn('получилось',final.with_suffix('.srt').read_text(encoding='utf-8-sig'))

    def test_http_rejects_unrecognized_pacing_and_advertises_modes(self):
        import threading
        from http.server import ThreadingHTTPServer
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        import server as studio_server

        previous = studio_server.studio
        studio_server.studio = self.app
        http = ThreadingHTTPServer(('127.0.0.1', 0), studio_server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{http.server_port}'
            with urlopen(base + '/', timeout=5) as response:
                html = response.read().decode('utf-8')
            self.assertIn('id="pacingMode"', html)
            for mode in ('normal','dynamic','fast'):
                self.assertIn(f'value="{mode}"', html)
            data = json.dumps({'pacing':'fast-but-malformed'}).encode('utf-8')
            req = Request(base + '/api/montage-preview', data=data, method='POST',
                          headers={'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as error:
                urlopen(req, timeout=5)
            self.assertEqual(error.exception.code, 400)
            self.assertFalse(self.app.worker and self.app.worker.is_alive())
        finally:
            http.shutdown()
            http.server_close()
            thread.join(timeout=5)
            studio_server.studio = previous

    def test_invalid_pacing_never_erases_last_final(self):
        with self.assertRaises(ValueError):
            self.app.render(480,False,False,0,pacing='untrusted')
        self.assertEqual(self.app.project['last_output'],'old-good.mp4')


if __name__=='__main__':
    unittest.main()
