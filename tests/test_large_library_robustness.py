"""Checks for large-library scanner, diagnostic pipe, and stable-ID regressions."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import Studio, audio_envelope, motion_envelope
from scanner_bridge import _scan_rust

INFO = {'duration': 12.0, 'width': 1920, 'height': 1080, 'audio': True}


class LargeLibraryRobustnessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.sources = self.base / 'recordings'
        self.sources.mkdir()
        self.app = Studio(self.base / 'state')
        self.app.configure(str(self.sources), {'whisper': False, 'vision': False})

    def scan(self):
        with patch('engine.probe', return_value=dict(INFO)):
            self.app.scan()

    def test_media_id_never_reused_after_source_disappears(self):
        a = self.sources / 'a.mp4'
        a.write_bytes(b'a')
        self.scan()
        old_id = self.app.project['files'][0]['id']
        a.unlink()
        self.scan()
        self.assertEqual(self.app.project['files'], [])
        fresh = Studio(self.base / 'state')
        b = self.sources / 'b.mp4'
        b.write_bytes(b'b')
        with patch('engine.probe', return_value=dict(INFO)):
            fresh.scan()
        self.assertNotEqual(fresh.project['files'][0]['id'], old_id)

    def test_media_id_not_reused_after_switching_source_folders(self):
        a = self.sources / 'a.mp4'
        a.write_bytes(b'a')
        self.scan()
        original = self.app.project['files'][0]['id']
        other = self.base / 'different-folder'
        other.mkdir()
        (other / 'b.mp4').write_bytes(b'b')
        self.app.configure(str(other), {'whisper': False})
        with patch('engine.probe', return_value=dict(INFO)):
            self.app.scan()
        self.assertNotEqual(original, self.app.project['files'][0]['id'])

    def test_ffmpeg_audio_decoder_never_uses_stderr_pipe(self):
        def inspect(*args, **kwargs):
            self.assertIsNot(kwargs['stderr'], subprocess.PIPE, 'FFmpeg stderr pipe can deadlock on corrupt footage')
            raise RuntimeError('inspected')
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.subprocess.Popen', side_effect=inspect):
            with self.assertRaisesRegex(RuntimeError, 'inspected'):
                audio_envelope('clip.mp4', 10, threading.Event())

    def test_ffmpeg_motion_decoder_never_uses_stderr_pipe(self):
        def inspect(*args, **kwargs):
            self.assertIsNot(kwargs['stderr'], subprocess.PIPE, 'FFmpeg stderr pipe can deadlock on corrupt footage')
            raise RuntimeError('inspected')
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.subprocess.Popen', side_effect=inspect):
            with self.assertRaisesRegex(RuntimeError, 'inspected'):
                motion_envelope('clip.mp4', threading.Event())

    def test_rust_inventory_never_uses_stderr_pipe(self):
        def inspect(*args, **kwargs):
            self.assertIsNot(kwargs['stderr'], subprocess.PIPE, 'Rust stderr pipe can deadlock on massive inventories')
            raise RuntimeError('inspected')
        with patch('scanner_bridge.subprocess.Popen', side_effect=inspect):
            with self.assertRaisesRegex(RuntimeError, 'inspected'):
                _scan_rust(self.sources.resolve(), threading.Event(), 'scanner')

    def test_large_ffmpeg_diagnostics_can_complete_without_blocking(self):
        # Replace only the process executable with Python; exercise real OS pipes,
        # including 300 KiB of diagnostic output preceding a small PCM payload.
        spawn = subprocess.Popen
        script = "import sys; sys.stderr.write('x'*300000); sys.stderr.flush(); sys.stdout.buffer.write(bytes(8000)); sys.stdout.flush()"
        def simulated(*_args, **kwargs):
            return spawn([sys.executable, '-c', script], **kwargs)
        with patch('engine.locate_ffmpeg', return_value='ffmpeg'), patch('engine.subprocess.Popen', side_effect=simulated):
            result = audio_envelope('clip.mp4', .5, threading.Event())
        self.assertEqual(result, [0.0])

    def test_rust_failure_diagnostics_are_bounded(self):
        spawn = subprocess.Popen
        script = "import sys; sys.stderr.write('q'*300000+'SCAN FAILURE');sys.exit(3)"
        def simulated(*_args, **kwargs):
            return spawn([sys.executable, '-c', script], **kwargs)
        with patch('scanner_bridge.subprocess.Popen', side_effect=simulated):
            with self.assertRaisesRegex(RuntimeError, r'SCAN FAILURE') as err:
                _scan_rust(self.sources.resolve(), threading.Event(), 'scanner')
        self.assertLess(len(str(err.exception)), 450)

if __name__ == '__main__':
    unittest.main()
