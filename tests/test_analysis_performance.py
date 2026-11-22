"""Durable and bounded per-recording performance measurements."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import Studio
from analysis_metrics import AnalysisProfile, summarize_performance


class MetricUnitTests(unittest.TestCase):
    def test_stage_measurements_track_time_without_file_data(self):
        ticks=iter([0.0,1.0,2.5,4.0,5.5,6.5])
        timer=AnalysisProfile(24.0, clock=lambda:next(ticks))
        with timer.stage('audio'):
            pass
        with timer.stage('motion'):
            pass
        result=timer.snapshot(audio_windows=14, motion_windows=4, transcript_segments=0)
        self.assertEqual(result['stages_seconds'], {'audio':1.5,'motion':1.5})
        self.assertEqual(result['total_seconds'],6.5)
        self.assertEqual(result['audio_windows'],14)
        self.assertEqual(result['motion_windows'],4)
        self.assertEqual(result['source_seconds'],24.0)

    def test_summary_filters_old_signatures_and_limits_slowest(self):
        jobs={f'm{i}':{'state':'complete','signature':'v1','metrics':{'total_seconds':i+1, 'source_seconds':20}} for i in range(5)}
        jobs['stale']={'state':'complete','signature':'v0','metrics':{'total_seconds':900,'source_seconds':20}}
        jobs['failed']={'state':'failed','signature':'v1','metrics':{'total_seconds':100,'source_seconds':10}}
        files=[{'id':i,'name':i+'.mp4'} for i in jobs]
        s=summarize_performance(jobs,files,signature='v1')
        self.assertEqual(s['completed'],5)
        self.assertEqual(s['failed'],1)
        self.assertEqual(s['total_completed_seconds'],15.0)
        self.assertEqual(s['slowest'][0]['id'],'m4')
        self.assertEqual(len(s['slowest']),3)
        self.assertNotIn('stale',str(s))
        self.assertNotIn('failed',str(s['slowest']))


class PerformancePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        source=self.base/'videos'
        source.mkdir()
        (source/'first.mp4').write_bytes(b'first')
        (source/'second.mp4').write_bytes(b'second')
        self.state=self.base/'state'
        self.app=Studio(self.state)
        self.app.configure(str(source),{'vision':True,'whisper':False})
        with patch('engine.probe',return_value={'duration':20,'audio':False,'width':1280,'height':720}):
            self.app.scan()

    def test_successful_file_metrics_survive_restart_and_are_visible_in_status(self):
        with patch('engine.locate_ffmpeg',return_value='ffmpeg'),patch('engine.motion_envelope',return_value=[0.1,0.2]):
            self.app.analyze()
        status=self.app.status()
        self.assertEqual(status['analysis_performance']['completed'],2)
        for row in status['files']:
            metrics=row['analysis_metrics']
            self.assertGreaterEqual(metrics['total_seconds'],0)
            self.assertIn('motion',metrics['stages_seconds'])
            self.assertEqual(metrics['motion_windows'],2)
        restored=Studio(self.state).status()
        self.assertEqual(restored['analysis_performance']['completed'],2)
        self.assertEqual(restored['analysis_performance'],status['analysis_performance'])

    def test_failed_file_has_last_attempt_diagnostic_and_other_files_complete(self):
        def motion(path,stop,threads=2,on_progress=None):
            if Path(path).name=='first.mp4':
                raise RuntimeError('corrupt video')
            return [0.3]
        with patch('engine.locate_ffmpeg',return_value='ffmpeg'),patch('engine.motion_envelope',side_effect=motion):
            self.app.analyze()
        status=self.app.status()
        rows={f['name']:f for f in status['files']}
        self.assertEqual(rows['first.mp4']['analysis_state'],'failed')
        self.assertIn('motion',rows['first.mp4']['analysis_metrics']['stages_seconds'])
        self.assertEqual(rows['second.mp4']['analysis_state'],'complete')
        self.assertEqual(status['analysis_performance']['failed'],1)
        self.assertEqual(status['analysis_performance']['completed'],1)

    def test_rescanning_changed_source_does_not_attach_old_stats_to_new_media(self):
        with patch('engine.locate_ffmpeg',return_value='ffmpeg'),patch('engine.motion_envelope',return_value=[0.1]):
            self.app.analyze()
        source=self.base/'videos'/'first.mp4'
        source.write_bytes(b'brand-new-content')
        with patch('engine.probe',return_value={'duration':20,'audio':False,'width':1280,'height':720}):
            self.app.scan()
        row=next(x for x in self.app.status()['files'] if x['name']=='first.mp4')
        self.assertEqual(row['analysis_metrics'],{})

    def test_reset_analysis_clears_metrics(self):
        with patch('engine.locate_ffmpeg',return_value='ffmpeg'),patch('engine.motion_envelope',return_value=[0.1]):
            self.app.analyze()
        self.app.reset_analysis()
        self.assertEqual(self.app.status()['analysis_performance']['completed'],0)
        self.assertTrue(all(f['analysis_metrics']=={} for f in self.app.status()['files']))

if __name__=='__main__':
    unittest.main()
