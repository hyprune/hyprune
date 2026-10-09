import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / 'brand'
sys.path.insert(0, str(ROOT / 'runtime'))
import icons
import install

spec = importlib.util.spec_from_file_location('brand_export', BRAND / 'export.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def png_size(path):
    data = Path(path).read_bytes()[:24]
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    return struct.unpack('>II', data[16:24])


class BrandTests(unittest.TestCase):
    def test_sha256sums_cover_every_file(self):
        listed = {}
        for line in (BRAND / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            listed[name] = digest
        files = {str(p.relative_to(BRAND)) for p in BRAND.rglob('*')
                 if p.is_file() and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts}
        self.assertEqual(set(listed), files)
        for name, digest in listed.items():
            self.assertEqual(hashlib.sha256((BRAND / name).read_bytes()).hexdigest(), digest, name)

    def test_svgs_are_self_contained(self):
        for svg in BRAND.rglob('*.svg'):
            text = svg.read_text()
            self.assertIsNone(re.search(r'<image|href=|<text|@import|url\(', text), svg)

    def test_mono_and_bold_masters_use_current_color(self):
        for svg in [*BRAND.glob('svg/*-mono.svg'), *BRAND.glob('svg/bold/*.svg')]:
            colours = set(re.findall(r'(?:fill|stroke)="([^"]+)"', svg.read_text())) - {'none'}
            self.assertEqual(colours, {'currentColor'}, svg)

    def test_app_icon_drawing_follows_size_rule(self):
        expected = {16: 'favicon-16-dark', 24: 'favicon-32-dark', 32: 'favicon-32-dark',
                    48: 'app-optical-dark', 64: 'app-optical-dark', 96: 'app-primary-dark',
                    128: 'app-primary-dark', 256: 'app-primary-dark', 512: 'app-primary-dark',
                    1024: 'app-primary-dark'}
        self.assertEqual({s: export.app_source(s).stem for s in export.APP_SIZES}, expected)
        for size in range(16, 1025):
            stem = export.app_source(size).stem
            self.assertTrue(stem.startswith('favicon') if size < 48 else
                            stem == 'app-optical-dark' if size < 96 else stem == 'app-primary-dark', size)

    def test_exports_have_their_sizes(self):
        for size in export.APP_SIZES:
            self.assertEqual(png_size(BRAND / f'png/hyprune-app-{size}.png'), (size, size))
        self.assertEqual(png_size(BRAND / 'web/apple-touch-icon.png'), (180, 180))
        data = (BRAND / 'web/favicon.ico').read_bytes()
        reserved, kind, count = struct.unpack('<HHH', data[:6])
        self.assertEqual((reserved, kind, count), (0, 1, 3))
        sizes = [struct.unpack('<B', data[6 + 16 * i:7 + 16 * i])[0] for i in range(count)]
        self.assertEqual(sizes, [16, 32, 48])

    @unittest.skipUnless(shutil.which('resvg') and importlib.util.find_spec('PIL'), 'needs resvg and Pillow')
    def test_exports_match_svg_masters(self):
        result = subprocess.run([sys.executable, str(BRAND / 'export.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hicolor_set(self):
        files = icons.hicolor_files()
        self.assertEqual([str(r) for _, r in files],
                         [f'hicolor/{s}x{s}/apps/hyprune.png' for s in [16, 24, 32, 48, 64, 128, 256, 512]]
                         + ['hicolor/scalable/apps/hyprune.svg'])
        for source, relative in files:
            if source.suffix == '.png':
                size = int(relative.parts[1].split('x')[0])
                self.assertEqual(png_size(source), (size, size))
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run([sys.executable, str(ROOT / 'runtime/icons.py'), temp], check=True)
            self.assertEqual(sorted(str(p.relative_to(temp)) for p in Path(temp).rglob('*') if p.is_file()),
                             sorted(str(r) for _, r in files))

    def test_installer_icons_are_managed_and_removed_when_unchanged(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            base = Path(temp); receipt = {}
            install.install_icons(base / 'icons', receipt)
            install.install_icons(base / 'icons', receipt)
            self.assertEqual(len(receipt), len(icons.hicolor_files()))
            scalable = base / 'icons/hicolor/scalable/apps/hyprune.svg'
            self.assertEqual(scalable.stat().st_mode & 0o777, 0o644)
            edited = base / 'icons/hicolor/16x16/apps/hyprune.png'
            edited.write_bytes(b'user icon')
            prefix = base / 'install'; prefix.mkdir()
            (prefix / 'receipt.json').write_text(install.json.dumps({'wrappers': {}, 'icons': receipt}))
            import argparse
            install.uninstall(argparse.Namespace(dry_run=False), prefix, base / 'config')
            self.assertFalse(scalable.exists())
            self.assertEqual(edited.read_bytes(), b'user icon')

    def test_session_entries_reference_the_icon(self):
        entry = install.session_entry('/home/u/.local/bin/hyprune-session')
        self.assertIn('Icon=hyprune\n', entry)
        self.assertIn('Exec="/home/u/.local/bin/hyprune-session"\n', entry)
        self.assertIn('Icon=hyprune', (ROOT / 'modules/session.nix').read_text())
        self.assertIn('runtime/icons.py $out/share/icons', (ROOT / 'nix/packages.nix').read_text())


if __name__ == '__main__':
    unittest.main()
