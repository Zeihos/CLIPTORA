"""Checks for subprocess streaming cancellation, timeouts, and bounded buffering."""
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys
import threading
import time
import unittest

from process_diagnostics import iter_child_blocks


class StreamWatchdogTests(unittest.TestCase):
    def start(self, script):
        child = subprocess.Popen([sys.executable, '-c', script],
                                 stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
        self.addCleanup(self.cleanup_child, child)
        return child

    @staticmethod
    def cleanup_child(child):
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        if child.stdout:
            child.stdout.close()

    def test_stream_preserves_all_bytes_including_last_partial_block(self):
        child = self.start('import os; os.write(1, b"123456789ABCDEF")')
        data = b''.join(iter_child_blocks(child, threading.Event(), 4,
                                          idle_timeout=3, poll_interval=0.03))
        self.assertEqual(data, b'123456789ABCDEF')
        self.assertEqual(child.wait(timeout=3), 0)

    def test_stopped_decode_interrupts_blocked_read_and_kills_child(self):
        child = self.start('import time; time.sleep(30)')
        stopped = threading.Event()
        timer = threading.Timer(0.18, stopped.set)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with self.assertRaises(InterruptedError):
            list(iter_child_blocks(child, stopped, 4096,
                                   idle_timeout=3, poll_interval=0.03))
        self.assertLess(time.monotonic() - started, 1.8)
        self.assertIsNotNone(child.poll(), 'blocked ffmpeg child must be terminated')

    def test_idle_decoder_times_out_and_is_terminated(self):
        child = self.start('import time; time.sleep(30)')
        start = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, 'FFmpeg'):
            list(iter_child_blocks(child, threading.Event(), 4096,
                                   idle_timeout=0.25, poll_interval=0.03))
        self.assertLess(time.monotonic() - start, 2)
        self.assertIsNotNone(child.poll())

    def test_bounded_buffer_keeps_large_output_complete(self):
        # Reads a 4 MiB stream without materializing the whole output in Python.
        child = self.start('import os; block=b"A"*4096; [os.write(1, block) for _ in range(1024)]')
        total = 0
        for chunk in iter_child_blocks(child, threading.Event(), 8192,
                                       max_pending=2, idle_timeout=4, poll_interval=0.03):
            self.assertLessEqual(len(chunk), 8192)
            total += len(chunk)
        self.assertEqual(total, 4 * 1024 * 1024)
        self.assertEqual(child.wait(timeout=3), 0)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg not installed')
    def test_real_ffmpeg_audio_and_motion_analysis(self):
        from engine import audio_envelope, motion_envelope
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'two_seconds.mp4'
            command = [shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-y',
                       '-f', 'lavfi', '-i', 'color=c=blue:s=96x54:r=4:d=2',
                       '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                       '-shortest', '-c:v', 'mpeg4', '-c:a', 'aac', str(video)]
            subprocess.run(command, check=True, capture_output=True, timeout=20)
            stop = threading.Event()
            audio = audio_envelope(video, 2, stop)
            motion = motion_envelope(video, stop)
            self.assertGreaterEqual(len(audio), 3)
            self.assertTrue(all(level >= 0 for level in audio))
            self.assertGreaterEqual(len(motion), 1)
            self.assertTrue(all(level >= 0 for level in motion))

    def test_early_consumer_close_terminates_blocked_producer(self):
        child = self.start('import os,time; os.write(1,b"test"); time.sleep(30)')
        reader = iter_child_blocks(child, threading.Event(), 4,
                                   idle_timeout=3, poll_interval=0.03)
        self.assertEqual(next(reader), b'test')
        reader.close()
        self.assertIsNotNone(child.poll())


if __name__ == '__main__':
    unittest.main()
