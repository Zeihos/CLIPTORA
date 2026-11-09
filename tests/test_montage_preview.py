"""Regression checks for non-destructive composed montage preview."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from engine import Studio
from montage_preview import preview_segments, preview_signature


class MontagePreviewPlanningTests(unittest.TestCase):
    def test_preview_keeps_editor_order_and_trims_at_two_minutes(self):
        source = [
            {'id':'first','media_id':'a','start':1,'end':71,'enabled':True},
            {'id':'hidden','media_id':'a','start':0,'end':50,'enabled':False},
            {'id':'second','media_id':'b','start':6,'end':86,'enabled':True},
        ]
        clips, truncated, seconds = preview_segments(source)
        self.assertEqual([c['id'] for c in clips], ['first', 'second'])
        self.assertEqual([(c['start'], c['end']) for c in clips], [(1, 71), (6, 56)])
        self.assertTrue(truncated)
        self.assertEqual(seconds, 120)
        self.assertEqual(source[2]['end'], 86, 'Must not mutate saved edits')

    def test_preview_only_includes_enabled_clips_and_rejects_empty(self):
        with self.assertRaisesRegex(ValueError, 'фрагмент'):
            preview_segments([{'start':0,'end':5,'enabled':False}])
        clips, shortened, seconds = preview_segments([
            {'media_id':'a','start':0,'end':1.5,'enabled':True},
        ])
        self.assertFalse(shortened)
        self.assertEqual(seconds, 1.5)
        self.assertEqual(clips[0]['end'], 1.5)

    def test_invalid_time_boundaries_fail_before_encoding(self):
        for start, end in [(3,2),(2,2),(-1,3),(float('nan'),5)]:
            with self.subTest(start=start,end=end):
                with self.assertRaises(ValueError):
                    preview_segments([{'enabled':True,'start':start,'end':end}])

    def test_fingerprint_changes_on_edits_or_export_settings_not_draft_name(self):
        clips=[{'id':'a','media_id':'src','start':0,'end':3,'zoom':False,'enabled':True}]
        files=[{'id':'src','path':'C:/video.mp4','size':42,'mtime_ns':7}]
        base=preview_signature(clips,files,False,0)
        self.assertEqual(base, preview_signature(clips,files,False,0))
        self.assertNotEqual(base, preview_signature(clips,files,True,0))
        self.assertNotEqual(base, preview_signature(clips,files,False,150))
        self.assertNotEqual(base, preview_signature([dict(clips[0],zoom=True)],files,False,0))
        self.assertNotEqual(base, preview_signature([dict(clips[0],end=4)],files,False,0))
        self.assertNotEqual(base, preview_signature(clips,[dict(files[0],mtime_ns=8)],False,0))


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/ffprobe required')
class MontagePreviewRealVideoTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        self.source=root/'source.mp4'
        p=subprocess.run(['ffmpeg','-y','-v','error','-nostdin',
                          '-f','lavfi','-i','testsrc2=size=320x180:rate=30:duration=3',
                          '-f','lavfi','-i','sine=frequency=500:sample_rate=48000:duration=3',
                          '-c:v','libx264','-threads','2','-pix_fmt','yuv420p',
                          '-c:a','aac','-shortest',str(self.source)],capture_output=True,timeout=60)
        self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'))
        self.app=Studio(root/'work')
        self.app.project['source_dir']=str(root)
        self.app.project['files']=[{'id':'source','path':str(self.source),'name':'source.mp4',
                                    'duration':3,'size':self.source.stat().st_size,
                                    'mtime_ns':self.source.stat().st_mtime_ns,'audio':True}]
        self.app.project['clips']=[
            {'id':'one','media_id':'source','start':0.1,'end':1.1,'enabled':True,'zoom':False},
            {'id':'two','media_id':'source','start':1.4,'end':2.7,'enabled':True,'zoom':True},
        ]
        self.app.project['last_output']='previous-final-render.mp4'
        self.app._save()

    def test_composed_preview_includes_audio_and_never_replaces_last_export(self):
        output=self.app.render_preview(normalize_audio=False,fade_ms=150)
        self.assertTrue(output.is_file())
        self.assertTrue(output.resolve().is_relative_to((self.app.work_dir/'previews').resolve()))
        probe=subprocess.run(['ffprobe','-v','error','-show_entries',
                              'format=duration:stream=codec_type,width,height','-of','json',str(output)],
                             capture_output=True,text=True,timeout=30)
        self.assertEqual(probe.returncode,0,probe.stderr)
        data=json.loads(probe.stdout)
        self.assertEqual({s['codec_type'] for s in data['streams']},{'video','audio'})
        self.assertEqual(next(x['height'] for x in data['streams'] if x['codec_type']=='video'),480)
        self.assertAlmostEqual(float(data['format']['duration']),2.3,delta=.25)
        self.assertEqual(self.app.project['last_output'],'previous-final-render.mp4')
        self.assertTrue(self.app.status()['montage_preview']['available'])
        self.assertEqual(self.app.status()['montage_preview']['duration_seconds'],2.3)

    def test_edit_invalidates_old_preview_and_restart_does_not_make_it_current(self):
        previous=self.app.render_preview()
        self.assertTrue(self.app.status()['montage_preview']['available'])
        self.app.edit_clip('one',end=1.0)
        self.assertFalse(self.app.status()['montage_preview']['available'])
        reopened=Studio(self.app.work_dir)
        self.assertFalse(reopened.status()['montage_preview']['available'])
        self.assertTrue(previous.exists(), 'Preview file must not be deleted by editing')

    def test_http_preview_stream_supports_ranges_and_rejects_stale_edit(self):
        import threading
        from http.server import ThreadingHTTPServer
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen
        import server as studio_server

        self.app.render_preview()
        previous = studio_server.studio
        studio_server.studio = self.app
        http = ThreadingHTTPServer(('127.0.0.1', 0), studio_server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{http.server_port}/api/montage-preview/video'
            with urlopen(Request(base, headers={'Range':'bytes=0-63'}), timeout=5) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(len(response.read()), 64)
                self.assertEqual(response.getheader('Content-Type'), 'video/mp4')
                self.assertTrue(response.getheader('Content-Range').startswith('bytes 0-63/'))
            self.app.edit_clip('one',end=1.0)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base, headers={'Range':'bytes=0-63'}),timeout=5)
            self.assertIn(error.exception.code, (404, 409))
        finally:
            http.shutdown()
            http.server_close()
            thread.join(timeout=4)
            studio_server.studio = previous

    def test_failed_render_does_not_replace_old_preview_or_final_export(self):
        good=self.app.render_preview()
        before=self.app.project['montage_preview'].copy()
        self.app.project['files'][0]['path']=str(self.source.parent/'missing.mp4')
        with self.assertRaises(RuntimeError):
            self.app.render_preview()
        self.assertEqual(before,self.app.project['montage_preview'])
        self.assertTrue(good.exists())
        self.assertEqual(self.app.project['last_output'],'previous-final-render.mp4')


if __name__=='__main__':
    unittest.main()
