"""Stop accidental breakage of the public documentation and project assets."""
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r'!?\[[^\]]*\]\(([^)]+)\)')
HTML_LOCAL_LINK = re.compile(r'(?:href|src)="([^"]+)"')


class RepositoryHealthTests(unittest.TestCase):
    def test_all_local_markdown_and_html_links_exist(self):
        markdown = [ROOT / name for name in ('README.md', 'CHANGELOG.md',
                                             'CONTRIBUTING.md', 'SECURITY.md')]
        markdown += sorted((ROOT / 'docs').rglob('*.md'))
        markdown += sorted((ROOT / '.github').rglob('*.md'))
        self.assertTrue(markdown)
        missing = []
        for document in markdown:
            content = document.read_text(encoding='utf-8')
            targets = MARKDOWN_LINK.findall(content) + HTML_LOCAL_LINK.findall(content)
            for raw in targets:
                target = raw.strip().split(' ', 1)[0]
                parsed = urlsplit(target)
                if not target or target.startswith('#') or parsed.scheme or target.startswith('//'):
                    continue
                local = document.parent / unquote(parsed.path)
                if not local.exists():
                    missing.append(f'{document.relative_to(ROOT)} -> {target}')
        self.assertEqual(missing, [], 'Ссылки ведут к отсутствующим файлам')

    def test_brand_assets_are_valid_svg(self):
        for relative in ('assets/cliptora-banner.svg', 'assets/cliptora-icon.svg'):
            with self.subTest(path=relative):
                root = ElementTree.parse(ROOT / relative).getroot()
                self.assertTrue(root.tag.endswith('svg'))

    def test_main_readme_mentions_current_version(self):
        version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').splitlines()[1].split(' ', 1)[0]
        self.assertIn(version.replace('-alpha', ' Alpha'), (ROOT / 'README.md').read_text(encoding='utf-8'))

    def test_displayed_version_and_new_project_version_match_release(self):
        import tempfile
        from engine import Studio
        release = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').splitlines()[1].split('-alpha')[0]
        with tempfile.TemporaryDirectory() as temp:
            app = Studio(temp)
            self.assertEqual(app.project['version'], release)
        html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
        self.assertIn('ALPHA ' + release, html)
        self.assertIn('Версия ' + release, html)

    def test_windows_launch_files_still_exist(self):
        for name in ('SETUP_WINDOWS.bat', 'SELECT_PYTHON_WINDOWS.bat',
                     'START_WINDOWS.bat', 'INSTALL_AI_WINDOWS.bat', 'BUILD_RUST_WINDOWS.bat'):
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file(), name)


if __name__ == '__main__':
    unittest.main()
