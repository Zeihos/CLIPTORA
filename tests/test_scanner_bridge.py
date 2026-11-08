"""Rust accelerator regression tests: fallback must never endanger saved projects."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import Studio
import scanner_bridge


class ScannerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'recordings'
        self.root.mkdir()
        self.stop = threading.Event()
        self.a = self.root / 'игра.mp4'
        self.a.write_bytes(b'a' * 32)
        nested = self.root / 'obs'
        nested.mkdir()
        self.b = nested / 'SESSION.MKV'
        self.b.write_bytes(b'b' * 43)
        hidden = self.root / '.cache'
        hidden.mkdir()
        (hidden / 'ignore.mp4').write_bytes(b'x' * 7)
        (self.root / 'empty.mp4').touch()
        (self.root / 'notes.txt').write_text('none', encoding='utf8')

    def test_python_fallback_discovers_unicode_nested_files_and_skips_hidden(self):
        with patch('scanner_bridge.locate_scanner', return_value=None):
            files, backend = scanner_bridge.discover(self.root, self.stop)
        self.assertEqual(backend, 'python')
        self.assertEqual({x['path'] for x in files}, {str(self.a.resolve()), str(self.b.resolve())})
        for item in files:
            st = Path(item['path']).stat()
            self.assertEqual(item['size'], st.st_size)
            self.assertEqual(item['mtime_ns'], st.st_mtime_ns)

    def test_rust_failure_falls_back_without_losing_files(self):
        events = []
        with patch('scanner_bridge.locate_scanner', return_value='scanner.exe'), \
             patch('scanner_bridge._scan_rust', side_effect=RuntimeError('broken scanner')):
            files, backend = scanner_bridge.discover(self.root, self.stop, events.append)
        self.assertEqual(backend, 'python')
        self.assertEqual({x['path'] for x in files}, {str(self.a.resolve()), str(self.b.resolve())})
        self.assertTrue(any('Rust' in x and 'Python' in x for x in events))

    def test_rust_success_is_selected(self):
        item = {'path': str(self.a), 'size': self.a.stat().st_size, 'mtime_ns': self.a.stat().st_mtime_ns}
        with patch('scanner_bridge.locate_scanner', return_value='scanner.exe'), \
             patch('scanner_bridge._scan_rust', return_value=[item]):
            files, backend = scanner_bridge.discover(self.root, self.stop)
        self.assertEqual(backend, 'rust')
        self.assertEqual(files, [item])

    def test_cancelled_scan_must_not_fall_back(self):
        self.stop.set()
        with self.assertRaises(InterruptedError):
            scanner_bridge.discover(self.root, self.stop)

    def test_rust_and_python_have_same_inventory_when_built(self):
        binary = scanner_bridge.locate_scanner()
        if not binary:
            self.skipTest('Rust scanner not built on this machine')
        rust, backend = scanner_bridge.discover(self.root, self.stop)
        self.assertEqual(backend, 'rust')
        with patch('scanner_bridge.locate_scanner', return_value=None):
            python, py_backend = scanner_bridge.discover(self.root, self.stop)
        self.assertEqual(py_backend, 'python')
        self.assertEqual(sorted(rust, key=lambda x:x['path']), sorted(python, key=lambda x:x['path']))


class StudioRustIntegrationTests(unittest.TestCase):
    def test_scan_keeps_old_clips_when_rust_metadata_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'videos'
            source.mkdir()
            video = source / 'gameplay.mp4'
            video.write_bytes(b'oldfile')
            app = Studio(root / 'state')
            app.configure(str(source), {'whisper': False, 'vision': False})
            fake_info = {'duration': 120, 'width': 1920, 'height': 1080, 'audio': True}
            with patch('engine.probe', return_value=fake_info):
                app.scan()
            initial = app.project['files'][0]
            clip = app.add_clip(initial['id'], 1, 8)
            stat = video.stat()
            metadata = {'path': str(video.resolve()), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
            with patch('engine.discover', return_value=([metadata], 'rust')), \
                 patch('engine.probe', side_effect=AssertionError('unchanged file probed')):
                app.scan()
            self.assertEqual(app.project['files'][0]['id'], initial['id'])
            self.assertEqual(app.project['clips'][0]['id'], clip['id'])
            self.assertEqual(app.status()['scan_backend'], 'rust')

    def test_legacy_014_float_mtime_maintains_same_id_on_rust_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'videos'
            source.mkdir()
            media = source / 'original.mp4'
            media.write_bytes(b'x' * 40)
            # 0.1.4 stored Python's float stat.mtime, which can differ by
            # one ULP from st_mtime_ns / 1e9 on Windows and Linux.
            import os
            ns = 1_794_150_052_878_389_410
            os.utime(media, ns=(ns, ns))
            app = Studio(root / 'state')
            app.configure(str(source), {'whisper': False})
            with patch('engine.probe', return_value={'duration': 30, 'width': 1280, 'height': 720, 'audio': True}):
                app.scan()
            old = app.project['files'][0]
            old_id = old['id']
            old['mtime'] = media.stat().st_mtime  # exactly the prior release
            old.pop('mtime_ns', None)
            clip = app.add_clip(old_id, 1, 4)
            metadata = {'path': str(media.resolve()), 'size': media.stat().st_size, 'mtime_ns': media.stat().st_mtime_ns}
            with patch('engine.discover', return_value=([metadata], 'rust')), \
                 patch('engine.probe', side_effect=AssertionError('must not probe unchanged legacy file')):
                app.scan()
            self.assertEqual(app.project['files'][0]['id'], old_id)
            self.assertEqual(app.project['clips'][0]['id'], clip['id'])

if __name__ == '__main__':
    unittest.main()
