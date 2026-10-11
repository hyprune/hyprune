"""The try path: pinned manifest, check.sh report, try.sh dry run, prepare.py rendering."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'try'))
sys.path.insert(0, str(ROOT / 'runtime'))
import prepare  # noqa: E402
import install  # noqa: E402
import session  # noqa: E402

MANIFEST = json.loads((ROOT / 'try/manifest.json').read_text())
HEX = re.compile(r'[0-9a-f]{64}')


class ManifestTests(unittest.TestCase):
    def test_one_flat_key_per_line_for_the_bash_reader(self):
        # check.sh reads `"key": value` lines without jq or python; keep the file flat.
        line = re.compile(r'^  "(\w+)": "?([^",]*)"?,?$')
        lines = (ROOT / 'try/manifest.json').read_text().splitlines()[1:-1]
        parsed = {m[1]: m[2] for m in map(line.match, lines) if m}
        self.assertEqual(len(parsed), len(lines))
        self.assertEqual(parsed, {k: str(v) for k, v in MANIFEST.items()})

    def test_pins_agree(self):
        self.assertEqual(MANIFEST['hyprland'], install.TARGET)
        self.assertEqual(MANIFEST['hyprland'], session.TARGET)
        self.assertRegex(MANIFEST['hyprlandAbi'], r'^[0-9a-f]{40}_aq_\d+\.\d+_hu_\d+\.\d+_hg_\d+\.\d+_hc_\d+\.\d+_hlg_\d+\.\d+$')
        self.assertIn(MANIFEST['hyprland'], MANIFEST['hyprlandArchPackage'])
        pins = json.loads((ROOT / 'component-pins.json').read_text())
        self.assertEqual(MANIFEST['shellRev'], pins['shell']['rev'])
        self.assertIn(MANIFEST['shellRev'], MANIFEST['shellUrl'])
        self.assertEqual(MANIFEST['coreRev'], pins['core']['rev'])
        self.assertIn(MANIFEST['coreRev'], MANIFEST['coreSourceUrl'])
        for key in ['shellSha256', 'coreSourceSha256']:
            self.assertRegex(MANIFEST[key], HEX)
        if MANIFEST['corePrebuiltUrl']:
            self.assertRegex(MANIFEST['corePrebuiltSha256'], HEX)
            self.assertTrue(MANIFEST['coreVersion'])
            self.assertIn(f"-hyprland-{MANIFEST['hyprland']}-", MANIFEST['corePrebuiltUrl'])

    def test_world_is_a_published_release_with_a_kit(self):
        releases = json.loads((ROOT / 'worlds/releases.json').read_text())
        record = releases[MANIFEST['world']]
        self.assertTrue(record['published'])
        self.assertTrue((ROOT / 'kits' / MANIFEST['world'] / 'kit.toml').is_file())


class ScriptTests(unittest.TestCase):
    def test_check_json_report(self):
        env = {**os.environ, 'HOME': tempfile.mkdtemp()}
        out = subprocess.run(['bash', str(ROOT / 'try/check.sh'), '--json', '--manifest', str(ROOT / 'try/manifest.json')],
                             capture_output=True, text=True, env=env, timeout=60)
        report = json.loads(out.stdout)
        self.assertIn(report['verdict'], ['ready', 'notes', 'nix', 'not-yet'])
        self.assertEqual(out.returncode, 1 if report['verdict'] == 'not-yet' else 0)
        ids = {c['id'] for c in report['checks']}
        self.assertTrue({'os', 'session', 'gpu', 'python', 'quickshell', 'tools', 'disk', 'ram'} <= ids)
        for check in report['checks']:
            if check['status'] == 'fail':
                self.assertTrue(check['fix'], check)

    def test_try_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, 'HOME': home, 'HYPRUNE_BASE': 'file://' + str(ROOT)}
            env.pop('WAYLAND_DISPLAY', None)  # also covers the stop-before-download path
            subprocess.run(['bash', str(ROOT / 'try/try.sh'), '--dry-run', '--dir', home + '/try'],
                           capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(list(Path(home).iterdir()), [])


class PrepareTests(unittest.TestCase):
    def test_alt_binds_stay_inside_their_block(self):
        lua = 'if hl.plugin.hyprune then\n  hl.bind("SUPER + F12", hl.plugin.hyprune.toggle)\nend\nhl.bind("SUPER + 1", x)\n'
        self.assertEqual(prepare.alt_binds(lua).splitlines(), [
            'if hl.plugin.hyprune then', '  hl.bind("SUPER + F12", hl.plugin.hyprune.toggle)',
            '  hl.bind("ALT + F12", hl.plugin.hyprune.toggle)', 'end', 'hl.bind("SUPER + 1", x)', 'hl.bind("ALT + 1", x)'])

    def test_alt_input_twins_respect_the_three_binding_limit(self):
        keymap = json.loads((ROOT.parent / 'core/config/input.default.json').read_text()) if \
            (ROOT.parent / 'core/config/input.default.json').is_file() else \
            {'modes': {'world': {'carry': ['Super+LMB'], 'exit': ['Super+Tab', 'Back'], 'forward': ['k', 'w', 'Up']}}}
        result = prepare.alt_input(keymap)
        world = result['modes']['world']
        self.assertEqual(world['carry'][:2], ['Super+LMB', 'Alt+LMB'])
        self.assertIn('Alt+Tab', world['exit'])
        self.assertTrue(all(len(b) <= 3 for mode in result['modes'].values() for b in mode.values()))

    def test_apps_need_their_programs(self):
        self.assertTrue(prepare.available({'argv': ['sh', '-c', 'true']}))
        self.assertFalse(prepare.available({'argv': ['hyprune-no-such-program']}))


if __name__ == '__main__':
    unittest.main()
