"""Regression checks for real offline speech inference diagnostics."""
import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import sys

import server


class WhisperInferenceTests(unittest.TestCase):
    def fake_package(self, segments, calls):
        package = ModuleType('faster_whisper')

        class WhisperModel:
            def __init__(self, name, **settings):
                calls['model'] = name
                calls['settings'] = settings

            def transcribe(self, source, **settings):
                calls['source'] = source
                calls['transcribe_settings'] = settings
                return iter(segments), SimpleNamespace(language=settings.get('language'))

        package.WhisperModel = WhisperModel
        return package

    def test_transcribes_real_input_path_using_cpu_int8_without_exposing_text(self):
        calls = {}
        segments = [SimpleNamespace(start=0.2, end=1.7, text='Secret spoken words')]
        with tempfile.TemporaryDirectory() as temp:
            media = Path(temp) / 'speech.wav'
            media.write_bytes(b'RIFFfake wav content')
            with patch.dict(sys.modules, {'faster_whisper': self.fake_package(segments, calls)}):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    code = server.check_whisper_transcription(media, 'tiny.en', 'en')
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result['segments'], 1)
            self.assertEqual(result['recognized_chars'], len('Secret spoken words'))
            self.assertNotIn('Secret', out.getvalue())
            self.assertTrue(result['ok'])
        self.assertEqual(calls['model'], 'tiny.en')
        self.assertEqual(calls['settings']['device'], 'cpu')
        self.assertEqual(calls['settings']['compute_type'], 'int8')
        self.assertEqual(calls['transcribe_settings']['language'], 'en')
        self.assertTrue(calls['transcribe_settings']['vad_filter'])

    def test_missing_audio_does_not_load_whisper_or_download_model(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertNotEqual(server.check_whisper_transcription('not-a-real-file.mp4', 'tiny.en', 'en'), 0)
        self.assertIn('файл', err.getvalue().lower())

    def test_silent_audio_reports_failure_instead_of_false_success(self):
        with tempfile.TemporaryDirectory() as temp:
            media = Path(temp) / 'empty.flac'
            media.write_bytes(b'not empty')
            with patch.dict(sys.modules, {'faster_whisper': self.fake_package([], {})}):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    code = server.check_whisper_transcription(media, 'tiny.en', 'en')
            self.assertNotEqual(code, 0)
            self.assertIn('реч', err.getvalue().lower())

    def test_cli_invokes_transcription_test_instead_of_starting_server(self):
        with patch.object(server, 'check_whisper_transcription', return_value=0) as check:
            with patch.object(sys, 'argv', ['CLIPTORA.exe', '--test-whisper', 'speech.mp4',
                                            '--whisper-test-model', 'tiny.en',
                                            '--whisper-test-language', 'en']):
                self.assertEqual(server.main(), 0)
            check.assert_called_once_with('speech.mp4', 'tiny.en', 'en')


if __name__ == '__main__':
    unittest.main()
