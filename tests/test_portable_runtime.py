"""Executable packaging must preserve bundled resources and user-supplied tools."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine
import scanner_bridge
import server
from runtime_paths import resource_root, tool_directories


class PortableRuntimeTests(unittest.TestCase):
    def test_source_mode_resolves_repo_assets(self):
        self.assertTrue((resource_root() / 'web' / 'index.html').is_file())
        self.assertTrue((resource_root() / 'assets' / 'cliptora-icon.svg').is_file())
        self.assertEqual(server.HERE, resource_root())

    def test_frozen_mode_uses_pyinstaller_bundle_for_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / '_internal'
            bundle.mkdir()
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', str(bundle), create=True):
                self.assertEqual(resource_root(), bundle.resolve())
                self.assertEqual(tool_directories()[-1], bundle.resolve() / 'tools')

    def test_portable_external_tools_take_precedence_over_bundled_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = root / '_internal'
            bundled = bundle / 'tools'
            external = root / 'tools'
            bundled.mkdir(parents=True)
            external.mkdir()
            (bundled / 'ffprobe.exe').write_bytes(b'bundled')
            (external / 'ffprobe.exe').write_bytes(b'external')
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', str(bundle), create=True), patch.object(sys, 'executable', str(root / 'CLIPTORA.exe')):
                with patch.object(engine.shutil, 'which', return_value=None):
                    self.assertEqual(Path(engine.locate_ffmpeg('ffprobe')).resolve(), (external / 'ffprobe.exe').resolve())

    def test_scanner_uses_bundled_native_binary_when_frozen(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = root / '_internal'
            scanner = bundle / 'tools' / ('cliptora-scanner.exe' if os.name == 'nt' else 'cliptora-scanner')
            scanner.parent.mkdir(parents=True)
            scanner.write_bytes(b'fake executable for discovery')
            with patch.dict(os.environ, {'CLIPTORA_SCANNER': ''}):
                with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', str(bundle), create=True), patch.object(sys, 'executable', str(root / 'CLIPTORA.exe')):
                    self.assertEqual(Path(scanner_bridge.locate_scanner()).resolve(), scanner.resolve())


if __name__ == '__main__':
    unittest.main()
