"""libraries/releases.json: the pinned official object libraries (RFC-0011)."""
import base64
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = json.loads((ROOT / 'libraries/releases.json').read_text())
KEYS = {'id', 'version', 'formatVersion', 'url', 'sha256', 'nixHash', 'published'}


class LibraryReleases(unittest.TestCase):
    def test_records(self):
        self.assertTrue(RELEASES)
        for name, record in RELEASES.items():
            with self.subTest(name):
                self.assertEqual(set(record), KEYS)
                self.assertRegex(record['id'], r'^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$')
                self.assertRegex(record['version'], r'^\d+\.\d+\.\d+$')
                self.assertRegex(record['formatVersion'], r'^\d+\.\d+$')
                # Published like worlds: a GitHub Release <library>-v<version> with a .tar.zst.
                self.assertEqual(record['url'], 'https://github.com/hyprune/worlds/releases/download/'
                                 f"{name}-v{record['version']}/{record['id']}-{record['version']}.tar.zst")
                self.assertRegex(record['sha256'], r'^[0-9a-f]{64}$')
                self.assertEqual(record['nixHash'], 'sha256-' + base64.b64encode(bytes.fromhex(record['sha256'])).decode())
                self.assertIsInstance(record['published'], bool)


if __name__ == '__main__':
    unittest.main()
