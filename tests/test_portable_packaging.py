"""Regression test: spec paths resolve from SPECPATH (not its parent)."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SPEC = Path(__file__).resolve().parents[1] / 'packaging' / 'cliptora.spec'


class PortableSpecTests(unittest.TestCase):
    def _exec_spec(self, root):
        calls = {}
        def analysis(scripts, **options):
            calls['scripts'] = scripts
            calls['options'] = options
            return SimpleNamespace(scripts=scripts, pure=[], binaries=options['binaries'], datas=options['datas'])
        def exe(*args, **kwargs):
            calls['exe'] = kwargs
            return object()
        def collect(*args, **kwargs):
            calls['collect'] = kwargs
        globals_ = {
            'SPECPATH': str(root / 'packaging'),
            'Analysis': analysis, 'PYZ': lambda *_: object(),
            'EXE': exe, 'COLLECT': collect,
        }
        exec(compile(SPEC.read_text(encoding='utf-8-sig'), str(SPEC), 'exec'), globals_)
        return calls

    def test_spec_bundles_existing_scanner_ui_and_branding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'packaging').mkdir()
            scanner = root / 'rust/scanner/target/release/cliptora-scanner.exe'
            scanner.parent.mkdir(parents=True)
            scanner.write_bytes(b'binary')
            calls = self._exec_spec(root)
            self.assertEqual([Path(x).resolve() for x in calls['scripts']], [(root / 'server.py').resolve()])
            self.assertEqual([(Path(x).resolve(), y) for x, y in calls['options']['binaries']], [(scanner.resolve(), 'tools')])
            self.assertIn(((root / 'web/index.html').resolve(), 'web'), [(Path(x).resolve(), y) for x, y in calls['options']['datas']])
            self.assertEqual(Path(calls['exe']['icon']).resolve(), (root / 'assets/cliptora.ico').resolve())

    def test_spec_rejects_build_without_native_scanner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'packaging').mkdir()
            with self.assertRaises(FileNotFoundError):
                self._exec_spec(root)


if __name__ == '__main__':
    unittest.main()
