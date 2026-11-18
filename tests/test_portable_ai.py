"""AI Portable must include speech dependencies without affecting Core builds."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import server
from scripts import smoke_portable


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'packaging' / 'cliptora.spec'


class PortableAISettingsTests(unittest.TestCase):
    def spec_options(self, enabled):
        seen = {'collected': []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'packaging').mkdir()
            scanner = root / 'rust/scanner/target/release/cliptora-scanner.exe'
            scanner.parent.mkdir(parents=True)
            scanner.write_bytes(b'native')
            def collect_all(name):
                seen['collected'].append(name)
                return [(f'{name}/data', f'{name}/data')], [(f'{name}.dll', '.')], [name + '.hidden']
            def analysis(scripts, **options):
                seen['options'] = options
                return SimpleNamespace(scripts=scripts, pure=[], binaries=options['binaries'], datas=options['datas'])
            hooks = ModuleType('PyInstaller.utils.hooks')
            hooks.collect_all = collect_all
            globals_ = {'SPECPATH': str(root / 'packaging'), 'Analysis': analysis,
                        'PYZ': lambda *_: object(), 'EXE': lambda *_a, **_kw: object(),
                        'COLLECT': lambda *_a, **_kw: None, 'collect_all': collect_all}
            with patch.dict(os.environ, {'CLIPTORA_WITH_AI': '1' if enabled else '0'}), \
                 patch.dict(sys.modules, {'PyInstaller.utils.hooks': hooks}):
                exec(compile(SPEC.read_text(encoding='utf-8-sig'), str(SPEC), 'exec'), globals_)
        return seen

    def test_core_does_not_collect_whisper_packages(self):
        self.assertEqual(self.spec_options(False)['collected'], [])

    def test_ai_edition_bundles_native_and_python_whisper_dependencies(self):
        data = self.spec_options(True)
        for package in ('faster_whisper', 'ctranslate2', 'av', 'tokenizers', 'huggingface_hub'):
            self.assertIn(package, data['collected'])
            self.assertIn(package + '.hidden', data['options']['hiddenimports'])
            self.assertIn((package + '.dll', '.'), data['options']['binaries'])

    def test_whisper_check_fails_cleanly_when_module_missing(self):
        with patch.dict(sys.modules, {'faster_whisper': None}):
            self.assertEqual(server.check_whisper_runtime(), 1)

    def test_smoke_checks_edition_status(self):
        smoke_portable.verify_status({'whisper_installed': False}, expect_whisper=False)
        smoke_portable.verify_status({'whisper_installed': True}, expect_whisper=True)
        with self.assertRaises(AssertionError):
            smoke_portable.verify_status({'whisper_installed': False}, expect_whisper=True)


if __name__ == '__main__':
    unittest.main()
