"""Export controls must preserve cuts, audio/video sync and prior finished renders."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from engine import Studio
from export_quality import make_export_filters, validate_export_quality


class ExportFilterTests(unittest.TestCase):
    def test_default_is_backward_compatible(self):
        video, audio = make_export_filters(4.0, 640, 360)
        self.assertEqual(video, 'scale=640:360:force_original_aspect_ratio=increase,crop=640:360,setsar=1,fps=30')
        self.assertEqual(audio, 'aresample=48000')

    def test_loudness_and_short_scene_fades_are_bounded(self):
        video, audio = make_export_filters(.4, 640, 360, normalize_audio=True, fade_ms=300)
        self.assertIn('fade=t=in:st=0:d=0.1', video)
        self.assertIn('fade=t=out:st=0.3:d=0.1', video)
        self.assertIn('loudnorm=I=-16:TP=-1.5:LRA=11', audio)
        self.assertIn('afade=t=in:st=0:d=0.1', audio)
        self.assertIn('afade=t=out:st=0.3:d=0.1', audio)
        self.assertTrue(audio.endswith('aresample=48000'))

    def test_zoom_kept_for_new_export(self):
        video, _ = make_export_filters(3.0, 640, 360, zoom=True, fade_ms=150)
        self.assertIn('crop=640:360', video)
        self.assertIn('fade=t=in:st=0:d=0.15', video)
        self.assertIn('fade=t=out:st=2.85:d=0.15', video)

    def test_bad_options_rejected_instead_of_implicitly_enabled(self):
        for normalize, fade in [(1,0),('true',0),(False,-1),(False,999), (False,True),(False,150.0)]:
            with self.subTest(normalize=normalize,fade=fade):
                with self.assertRaises(ValueError):
                    validate_export_quality(normalize,fade)

    def test_zero_or_negative_duration_rejected(self):
        for duration in (0,-1,float('nan'),float('inf')):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    make_export_filters(duration,640,360)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and FFprobe required')
class ExportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.video = root/'source.mp4'
        # Real audio and video, without external footage.
        cmd = ['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-y',
               '-f','lavfi','-i','color=c=navy:s=320x180:r=30:d=2.4',
               '-f','lavfi','-i','sine=frequency=700:sample_rate=48000:duration=2.4',
               '-shortest','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(self.video)]
        p = subprocess.run(cmd,capture_output=True,timeout=60)
        if p.returncode:
            self.fail(p.stderr.decode('utf-8','replace')[-1000:])
        self.app = Studio(root/'work')
        self.app.project['source_dir'] = str(root)
        self.app.project['files'] = [{'id':'src','path':str(self.video),'name':'source.mp4',
                                      'duration':2.4,'audio':True, 'size':self.video.stat().st_size}]
        self.app.project['clips'] = [
            {'id':'a','media_id':'src','source_name':'source.mp4','start':0,'end':1.1, 'enabled':True},
            {'id':'b','media_id':'src','source_name':'source.mp4','start':1.1,'end':2.3,'enabled':True},
        ]
        self.app._save()

    def test_export_with_normalization_and_soft_cuts_has_av_streams(self):
        out = self.app.render(480, False, True, 150)
        self.assertTrue(out.exists())
        result = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type',
                                 '-of','json',str(out)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(set(x['codec_type'] for x in data['streams']),{'video','audio'})
        self.assertAlmostEqual(float(data['format']['duration']),2.3,delta=.25)
        manifest=json.loads(out.with_suffix('.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['export_quality'],{'normalize_audio':True,'fade_ms':150})
        self.assertEqual(self.app.project['last_output'],str(out))

    def test_failed_export_does_not_leave_partial_output_or_change_last_output(self):
        self.app.project['last_output']='older_success.mp4'
        self.app.project['files'][0]['path']=str(Path(self.tmp.name)/'deleted.mp4')
        with self.assertRaises(RuntimeError):
            self.app.render(480,False,True,150)
        self.assertEqual(self.app.project['last_output'],'older_success.mp4')
        self.assertFalse(list((self.app.work_dir/'renders').glob('*.partial.mp4')))
        self.assertFalse(list((self.app.work_dir/'renders').glob('CLIPTORA_*.mp4')))

if __name__ == '__main__':
    unittest.main()
