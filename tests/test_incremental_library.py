"""Regression coverage for scanning and resuming large footage libraries."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import Studio

INFO = {'duration': 42.0, 'width': 1920, 'height': 1080, 'audio': False}


class IncrementalLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / 'recordings'
        self.source.mkdir()
        self.app = Studio(root / 'state')
        self.app.configure(str(self.source), {'whisper': False, 'vision': False})
        self.a = self.source / 'a.mp4'
        self.a.write_bytes(b'a' * 20)

    def scan(self):
        with patch('engine.probe', return_value=dict(INFO)) as probe:
            self.app.scan()
        return probe

    def test_rescan_keeps_existing_ids_analysis_and_edits_when_new_file_added(self):
        self.scan()
        original = self.app.project['files'][0]
        original['analysis'] = {'audio_levels': [0.1], 'motion_levels': [], 'transcript': []}
        original['analyzed'] = True
        original['analysis_signature'] = self.app.analysis_signature()
        chosen = self.app.add_clip(original['id'], 2, 11)
        added = self.source / 'b.mp4'
        added.write_bytes(b'b' * 100)
        probe = self.scan()
        self.assertEqual(probe.call_count, 1, 'unchanged video must not be probed again')
        self.assertEqual(len(self.app.project['files']), 2)
        retained = next(x for x in self.app.project['files'] if Path(x['path']).resolve() == self.a.resolve())
        self.assertEqual(retained['id'], original['id'])
        self.assertTrue(retained['analyzed'])
        self.assertEqual(retained['analysis'], original['analysis'])
        self.assertEqual(self.app.project['clips'][0]['id'], chosen['id'])
        self.assertEqual(self.app.project['clips'][0]['media_id'], original['id'])
        self.assertNotEqual(next(x for x in self.app.project['files'] if x['path'] == str(added))['id'], original['id'])

    def test_changed_source_invalidates_only_its_old_clips(self):
        b = self.source / 'b.mp4'
        b.write_bytes(b'b' * 33)
        self.scan()
        files = {x['name']: x for x in self.app.project['files']}
        self.app.add_clip(files['a.mp4']['id'], 1, 5)
        self.app.add_clip(files['b.mp4']['id'], 10, 14)
        before_b_id = files['b.mp4']['id']
        self.a.write_bytes(b'a' * 55)
        self.scan()
        updated = {x['name']: x for x in self.app.project['files']}
        self.assertNotEqual(updated['a.mp4']['id'], files['a.mp4']['id'])
        self.assertEqual(updated['b.mp4']['id'], before_b_id)
        self.assertEqual(len(self.app.project['clips']), 1)
        self.assertEqual(self.app.project['clips'][0]['media_id'], before_b_id)

    def test_changing_analysis_settings_marks_cached_analysis_stale(self):
        self.scan()
        entry = self.app.project['files'][0]
        entry['analyzed'] = True
        entry['analysis'] = {'audio_levels': [0.2], 'motion_levels': [], 'transcript': []}
        entry['analysis_signature'] = self.app.analysis_signature()
        self.app.configure(str(self.source), {'vision': False})
        self.assertTrue(entry['analyzed'])
        self.app.configure(str(self.source), {'vision': True})
        self.assertFalse(entry['analyzed'])
        self.assertFalse(self.app.status()['files'][0]['analyzed'])
        with self.assertRaises(ValueError):
            self.app.plan()

    def test_reanalysis_uses_current_signature_and_resume_skips_done_files(self):
        self.scan()
        self.app.configure(str(self.source), {'vision': True})
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.motion_envelope', return_value=[.1, .4]) as motion:
            self.app.analyze()
            self.assertEqual(motion.call_count, 1)
            self.app.analyze()
            self.assertEqual(motion.call_count, 1, 'second pass should use persisted work')
        entry = self.app.project['files'][0]
        self.assertEqual(entry['analysis_signature'], self.app.analysis_signature())
        self.assertTrue(entry['analyzed'])


if __name__ == '__main__':
    unittest.main()
