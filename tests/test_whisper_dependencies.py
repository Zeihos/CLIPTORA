"""Prevent the PyAV 19 regression that broke actual packaged inference."""
import unittest
from pathlib import Path

from whisper_compat import assert_pyav_compatible

ROOT = Path(__file__).resolve().parents[1]


class WhisperDependencyTests(unittest.TestCase):
    def test_pyav_18_is_compatible_and_pyav_19_is_rejected(self):
        assert_pyav_compatible('18.1.0')
        assert_pyav_compatible('16.1.0')
        with self.assertRaisesRegex(RuntimeError, 'av==18.1.0'):
            assert_pyav_compatible('19.0.2')

    def test_ai_portable_dependencies_pin_compatible_pyav(self):
        requirements = (ROOT/'packaging/requirements-portable-ai.txt').read_text(encoding='utf-8')
        self.assertIn('faster-whisper==1.2.1', requirements)
        self.assertIn('av==18.1.0', requirements)

    def test_source_windows_installer_replaces_incompatible_pyav(self):
        launcher = (ROOT/'INSTALL_AI_WINDOWS.bat').read_bytes()
        self.assertIn(b'"av==18.1.0"', launcher)
        self.assertIn(b'"faster-whisper==1.2.1"', launcher)
        self.assertEqual(launcher.count(b'\n'), launcher.count(b'\r\n'))


if __name__ == '__main__':
    unittest.main()
