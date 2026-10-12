"""libraries/releases.json: the pinned official object libraries (RFC-0011).

Keyed by id@version, as the schema's library-releases record (v0.9/library-releases.schema.json)
that `hyprune library install id@version --releases` and the worlds repository's library-pack use."""
import base64
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = json.loads((ROOT / 'libraries/releases.json').read_text())
KEYS = {'id', 'version', 'formatVersion', 'url', 'sha256', 'nixHash', 'published'}


class LibraryReleases(unittest.TestCase):
    def test_records(self):
        self.assertTrue(RELEASES)
        for key, record in RELEASES.items():
            with self.subTest(key):
                self.assertEqual(set(record), KEYS)
                self.assertEqual(key, f"{record['id']}@{record['version']}")
                self.assertRegex(record['id'], r'^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$')
                self.assertRegex(record['version'], r'^\d+\.\d+\.\d+$')
                self.assertRegex(record['formatVersion'], r'^\d+\.\d+$')
                # Published like worlds: a GitHub Release <library>-v<version> with a .tar.zst.
                match = re.fullmatch(r'https://github\.com/hyprune/worlds/releases/download/([a-z0-9-]+)-v([^/]+)/(.+)',
                                     record['url'])
                self.assertTrue(match, record['url'])
                self.assertEqual(match[2], record['version'])
                self.assertEqual(match[3], f"{record['id']}-{record['version']}.tar.zst")
                self.assertRegex(record['sha256'], r'^[0-9a-f]{64}$')
                self.assertEqual(record['nixHash'], 'sha256-' + base64.b64encode(bytes.fromhex(record['sha256'])).decode())
                self.assertIsInstance(record['published'], bool)


if __name__ == '__main__':
    unittest.main()
