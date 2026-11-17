"""Localhost-only UI/API for CLIPTORA, Python standard library."""
import argparse
import json
import os
import re
import subprocess
import sys
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from engine import Studio
from export_quality import validate_export_quality
from pacing import validate_pacing
from runtime_paths import resource_root

HERE=resource_root()
studio=None


class Handler(BaseHTTPRequestHandler):
    server_version='CLIPTORA/0.1.15'

    def log_message(self, fmt, *args):
        if not self.path.startswith('/api/status'):
            print(f'[{self.address_string()}] {fmt % args}',flush=True)

    def send_blob(self, data, content_type='application/json', code=200):
        if isinstance(data,(dict,list)):
            data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        elif isinstance(data,str):
            data=data.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type',content_type + ('; charset=utf-8' if content_type.startswith('text/') or content_type=='application/json' else ''))
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(data)

    def _allow_local_host(self):
        # Binding to 127.0.0.1 alone does not prevent DNS-rebinding through
        # a malicious Host header. Only the editor's own loopback URL is valid.
        allowed = {f'127.0.0.1:{self.server.server_port}',
                   f'localhost:{self.server.server_port}'}
        if self.headers.get('Host', '').lower() not in allowed:
            self.send_blob({'error': 'Некорректный адрес локального сервера'}, code=403)
            return False
        return True

    def do_GET(self):
        try:
            if not self._allow_local_host():
                return
            parsed=urlparse(self.path)
            if parsed.path in ('/','/index.html'):
                return self.send_blob((HERE/'web'/'index.html').read_bytes(),'text/html')
            if parsed.path=='/assets/cliptora-icon.svg':
                return self.send_blob((HERE/'assets'/'cliptora-icon.svg').read_bytes(),'image/svg+xml')
            if parsed.path=='/api/status':
                return self.send_blob(studio.status())
            if parsed.path=='/api/quality-report':
                return self.send_blob(studio.quality_report())
            if parsed.path=='/media':
                return self.stream_media(parse_qs(parsed.query).get('id',[''])[0])
            if parsed.path=='/api/montage-preview/video':
                return self.stream_montage_preview()
            return self.send_blob({'error':'Not found'},code=404)
        except (BrokenPipeError,ConnectionResetError):
            return
        except Exception as e:
            return self.send_blob({'error':str(e)},code=500)

    def stream_montage_preview(self):
        info=studio.preview_info()
        if not info['available']:
            return self.send_blob({'error':'Предпросмотр устарел. Создайте новый.'},code=409)
        path=Path(studio.project['montage_preview']['path']).resolve()
        return self.stream_file(path, 'video/mp4')

    def stream_media(self, media_id):
        f=next((x for x in studio.project['files'] if x['id']==media_id),None)
        if not f:
            return self.send_blob({'error':'No media'},code=404)
        path=Path(f['path'])
        root=Path(studio.project['source_dir'])
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            return self.send_blob({'error':'Media unavailable'},code=404)
        return self.stream_file(path, 'video/mp4' if path.suffix.lower()=='.mp4' else 'application/octet-stream')

    def stream_file(self, path, content_type):
        size=path.stat().st_size
        r=self.headers.get('Range','')
        match=re.fullmatch(r'bytes=(\d+)-(\d*)',r.strip())
        start = int(match.group(1)) if match else 0
        requested_end = int(match.group(2)) if match and match.group(2) else None
        if start >= size or (requested_end is not None and requested_end < start):
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        # 200 means the complete representation. For byte-range requests,
        # deliberately cap a single response at 4 MiB to support seeking.
        end = min(size - 1, start + 4 * 1024 * 1024 - 1) if match else size - 1
        if requested_end is not None:
            end = min(end, requested_end)
        self.send_response(206 if match else 200)
        self.send_header('Content-Type',content_type)
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Cache-Control','no-store')
        if match:
            self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(end-start+1))
        self.end_headers()
        with path.open('rb') as stream:
            stream.seek(start)
            remaining=end-start+1
            while remaining>0:
                chunk=stream.read(min(512*1024,remaining))
                if not chunk: break
                self.wfile.write(chunk)
                remaining-=len(chunk)

    def do_POST(self):
        try:
            if not self._allow_local_host():
                return
            origin=self.headers.get('Origin','')
            if origin:
                host=self.headers.get('Host','')
                if origin not in ('http://'+host,'http://127.0.0.1:'+str(self.server.server_port),
                                  'http://localhost:'+str(self.server.server_port)):
                    return self.send_blob({'error':'Origin blocked'},code=403)
            if 'application/json' not in self.headers.get('Content-Type',''):
                return self.send_blob({'error':'Expected JSON'},code=415)
            raw_length = self.headers.get('Content-Length', '')
            if not raw_length.isascii() or not raw_length.isdecimal():
                return self.send_blob({'error': 'Некорректный Content-Length'}, code=400)
            length = int(raw_length)
            if length>1024*1024:
                return self.send_blob({'error':'Request too large'},code=413)
            payload=json.loads(self.rfile.read(length) or b'{}')
            path=urlparse(self.path).path
            if path=='/api/config':
                studio.configure(payload.get('source_dir',''),payload.get('settings',{}))
            elif path=='/api/scan':
                studio.schedule('Сканирование библиотеки',studio.scan)
            elif path=='/api/analyze':
                studio.schedule('Анализ записей',studio.analyze)
            elif path=='/api/reset-analysis':
                studio.reset_analysis()
            elif path=='/api/plan':
                studio.plan(payload.get('target_minutes',12))
            elif path=='/api/plan-preview':
                return self.send_blob(studio.preview_plans(payload.get('target_minutes',12)))
            elif path=='/api/plan-apply':
                return self.send_blob(studio.apply_plan_variant(payload.get('token',''),payload.get('variant','')))
            elif path=='/api/plan-undo':
                studio.undo_plan()
            elif path=='/api/quality-reference-add':
                return self.send_blob(studio.add_quality_reference(
                    payload['media_id'],payload['start'],payload['end'],payload.get('label','')))
            elif path=='/api/quality-reference-remove':
                studio.remove_quality_reference(payload['id'])
            elif path=='/api/clip-add':
                studio.add_clip(payload['media_id'],payload['start'],payload['end'])
            elif path=='/api/clip':
                studio.edit_clip(payload.pop('id'),**payload)
            elif path=='/api/montage-preview':
                normalize_audio, fade_ms = validate_export_quality(payload.get('normalize_audio',False),payload.get('fade_ms',0))
                pacing=validate_pacing(payload.get('pacing','normal'))
                studio.schedule('Предпросмотр монтажа',studio.render_preview,normalize_audio,fade_ms,pacing)
            elif path=='/api/render':
                normalize_audio, fade_ms = validate_export_quality(payload.get('normalize_audio',False),payload.get('fade_ms',0))
                pacing=validate_pacing(payload.get('pacing','normal'))
                studio.schedule('Экспорт MP4',studio.render,payload.get('height',720),payload.get('captions',False),
                                normalize_audio, fade_ms, pacing=pacing)
            elif path=='/api/stop':
                studio.stop.set()
            elif path=='/api/output':
                filepath=studio.project.get('last_output','')
                if not filepath or not Path(filepath).is_file():
                    raise RuntimeError('Готовый файл ещё не создан')
                if os.name=='nt':
                    subprocess.Popen(['explorer',f'/select,{filepath}'])
                else:
                    self.send_blob({'ok':True,'path':filepath})
                    return
            else:
                return self.send_blob({'error':'Not found'},code=404)
            return self.send_blob({'ok':True})
        except (ValueError,KeyError,RuntimeError) as e:
            return self.send_blob({'error':str(e)},code=400)
        except Exception as e:
            return self.send_blob({'error':str(e)},code=500)


def main():
    global studio
    parser=argparse.ArgumentParser()
    parser.add_argument('--work-dir',default=None)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    studio=Studio(args.work_dir)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'CLIPTORA: http://127.0.0.1:{args.port}',flush=True)
    print('Для остановки нажмите Ctrl+C. Все исходники остаются неизменными.',flush=True)
    if not args.no_browser:
        import threading
        threading.Timer(1,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        print('\nСервер остановлен')
    finally:
        studio.stop.set()
        server.server_close()

if __name__=='__main__':
    main()
