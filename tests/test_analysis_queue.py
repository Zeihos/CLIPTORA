"""Regression tests for resumable video queue."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import Studio

DETAILS = {'duration': 60, 'width': 1920, 'height': 1080, 'audio': False}

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root/'videos'
        self.source.mkdir()
        self.a = self.source/'a.mp4'
        self.b = self.source/'b.mp4'
        self.a.write_bytes(b'a')
        self.b.write_bytes(b'b')
        self.state = root/'state'
        self.app = Studio(self.state)
        self.app.configure(str(self.source), {'whisper': False, 'vision': True})
        with patch('engine.probe', return_value=dict(DETAILS)):
            self.app.scan()

    def test_failed_file_does_not_abort_queue_and_retry_only_failed(self):
        calls = []
        def motion(path, stop, on_progress=None, threads=2):
            name = Path(path).name
            calls.append(name)
            if name == 'b.mp4' and calls.count(name) == 1:
                raise ValueError('corrupt frames')
            return [.2, .3]
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.motion_envelope', side_effect=motion):
            self.app.analyze()
            self.assertEqual(self.app.status()['analysis_queue']['failed'], 1)
            restarted = Studio(self.state)
            self.assertEqual(restarted.status()['analysis_queue']['complete'], 1)
            restarted.analyze()
            self.assertEqual(restarted.status()['analysis_queue']['complete'], 2)
        self.assertEqual(calls.count('a.mp4'), 1)
        self.assertEqual(calls.count('b.mp4'), 2)

    def test_restart_recovers_running_job(self):
        mid = self.app.project['files'][0]['id']
        self.app.project['analysis_jobs'] = {mid: {'state':'running', 'signature':self.app.analysis_signature(), 'attempts':1}}
        self.app._save()
        restored = Studio(self.state)
        self.assertEqual(restored.project['analysis_jobs'][mid]['state'], 'pending')

    def test_stop_keeps_unfinished_job_pending(self):
        def stop_now(path, stop, on_progress=None, threads=2):
            stop.set()
            raise InterruptedError('stop')
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.motion_envelope', side_effect=stop_now):
            with self.assertRaises(InterruptedError):
                self.app.analyze()
        self.assertEqual(self.app.status()['analysis_queue']['pending'], 2)

    def test_cpu_limit_does_not_invalidate_finished_analysis(self):
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.motion_envelope', return_value=[.1]):
            self.app.analyze()
        signature = self.app.analysis_signature()
        self.app.configure(str(self.source), {'cpu_threads': 4})
        self.assertEqual(self.app.analysis_signature(), signature)
        self.assertEqual(self.app.status()['analysis_queue']['complete'], 2)
        with self.assertRaises(ValueError):
            self.app.configure(str(self.source), {'cpu_threads': 9})

    def test_changed_media_does_not_run_without_rescan(self):
        self.a.write_bytes(b'replaced')
        calls = []
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.motion_envelope', side_effect=lambda *a, **k: calls.append(a[0]) or [.2]):
            self.app.analyze()
        files = {f['name']:f for f in self.app.status()['files']}
        self.assertEqual(files['a.mp4']['analysis_state'], 'failed')
        self.assertIn('просканируйте',files['a.mp4']['analysis_error'])
        self.assertEqual(calls, [str(self.b)])

if __name__ == '__main__':
    unittest.main()
