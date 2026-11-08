"""Regression checks for the CLIPTORA identity and update compatibility."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import Studio


class BrandingTests(unittest.TestCase):
    def test_visible_branding(self):
        page = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<title>CLIPTORA', page)
        self.assertIn('CLIPTORA', page)
        self.assertNotIn('ZEIHOS', page)
        self.assertNotIn('AI Montage Studio', page)

    def test_windows_start_and_ai_choose_python_312(self):
        for filename in ('START_WINDOWS.bat', 'INSTALL_AI_WINDOWS.bat', 'SETUP_WINDOWS.bat'):
            data = (ROOT / filename).read_bytes()
            self.assertEqual(data.count(b'\n'), data.count(b'\r\n'), filename)
            self.assertIn(b'CLIPTORA', data, filename)
            self.assertNotIn(b'ZEIHOS', data, filename)
        selector=(ROOT/'SELECT_PYTHON_WINDOWS.bat').read_text(encoding='ascii')
        self.assertIn('py -3.12', selector)
        self.assertNotIn("('py -3 -c", selector)

    def test_new_user_gets_new_brand_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pathlib.Path.home', return_value=Path(tmp)):
            app=Studio()
            self.assertEqual(app.work_dir, Path(tmp)/'CLIPTORA')

    def test_legacy_data_kept_accessible(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pathlib.Path.home', return_value=Path(tmp)):
            legacy=Path(tmp)/'Zeihos AI Montage Studio'
            legacy.mkdir()
            (legacy/'project.json').write_text('{"version":"0.1.0","source_dir":"","files":[],"clips":[],"settings":{},"last_output":""}',encoding='utf-8')
            app=Studio()
            self.assertEqual(app.work_dir, legacy)
            self.assertTrue((legacy/'project.json').exists())

    def test_static_icon_is_served(self):
        source = (ROOT/'server.py').read_text(encoding='utf-8')
        self.assertIn('/assets/cliptora-icon.svg', source)
        self.assertTrue((ROOT/'assets'/'cliptora-icon.svg').exists())


if __name__=='__main__':
    unittest.main()
