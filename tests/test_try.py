"""The try path: pinned manifest, check.sh report, try.sh dry run, prepare.py rendering."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'try'))
sys.path.insert(0, str(ROOT / 'runtime'))
sys.path.insert(0, str(ROOT / 'tests'))
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
        # The hyprune CLI (the Director's Library page runs it) is the pinned SDK.
        self.assertEqual(MANIFEST['sdkRev'], pins['sdk']['rev'])
        self.assertEqual(MANIFEST['sdkUrl'], f"https://github.com/hyprune/sdk/archive/{pins['sdk']['rev']}.tar.gz")
        self.assertRegex(MANIFEST['node'], r'^\d+\.\d+$')
        for key in ['shellSha256', 'coreSourceSha256', 'sdkSha256']:
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

    def test_try_fetches_the_session_runtime(self):
        # session.py renews the source helper's grant only through runtime/session-daemon.
        script = (ROOT / 'try/try.sh').read_text()
        listed = re.search(r'for f in (.*?); do', script, re.S)[1].split()
        for f in ['runtime/session.py', 'runtime/session-daemon', 'runtime/setup.py', 'runtime/install.py']:
            self.assertIn(f, listed)
            self.assertTrue((ROOT / f).is_file(), f)
        self.assertEqual(session.DAEMON_WRAPPER.name, 'session-daemon')
        self.assertIn('chmod 755 "$dir/meta/runtime/session-daemon"', script)

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

    def test_check_reads_the_gles_version(self):
        # eglinfo's line is "OpenGL ES profile version: OpenGL ES 3.2 ..."; the version is the second match.
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as bin_dir:
            fake = Path(bin_dir) / 'eglinfo'
            fake.write_text('#!/bin/sh\necho "OpenGL ES profile renderer: Test GPU"\n'
                            'echo "OpenGL ES profile version: OpenGL ES 3.2 Test 1.0"\n')
            fake.chmod(0o755)
            env = {**os.environ, 'HOME': home, 'PATH': f"{bin_dir}:{os.environ['PATH']}"}
            out = subprocess.run(['bash', str(ROOT / 'try/check.sh'), '--json', '--manifest', str(ROOT / 'try/manifest.json')],
                                 capture_output=True, text=True, env=env, timeout=60)
        egl = next(c for c in json.loads(out.stdout)['checks'] if c['id'] == 'egl')
        self.assertEqual((egl['status'], egl['detail']), ('ok', 'OpenGL ES 3.2, Test GPU'))

    def test_try_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, 'HOME': home, 'HYPRUNE_BASE': 'file://' + str(ROOT)}
            env.pop('WAYLAND_DISPLAY', None)  # also covers the stop-before-download path
            subprocess.run(['bash', str(ROOT / 'try/try.sh'), '--dry-run', '--dir', home + '/try'],
                           capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(list(Path(home).iterdir()), [])

    @unittest.skipUnless(shutil.which('zstd') and shutil.which('curl'), 'zstd and curl needed')
    def test_try_installs_libraries_into_the_folder_data_dir(self):
        import test_content
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            release = temp / 'releases/download/street-v1.2.0'
            release.mkdir(parents=True)
            archive = release / f'{test_content.LIB}-1.2.0.tar.zst'
            sha = test_content.pack(archive, test_content.library_members())
            folder = temp / 'try'
            (folder / 'venv/bin').mkdir(parents=True)
            (folder / 'venv/bin/python').symlink_to(sys.executable)
            (folder / 'meta/runtime').mkdir(parents=True)
            shutil.copy(ROOT / 'runtime/content.py', folder / 'meta/runtime/content.py')
            (folder / 'downloads').mkdir()
            # try.sh's own helpers and get_libraries, without running main.
            script = (ROOT / 'try/try.sh').read_text()
            helpers = '\n'.join(l for l in script.splitlines() if l.startswith(('step()', 'die()', 'fetch()', 'verify()')))
            body = script[script.index('get_libraries() {'):]
            body = body[:body.index('\n}\n') + 3]
            pins = f'{test_content.LIB} 1.2.0 file://{archive} {sha}'
            run = lambda pin: subprocess.run(['bash', '-euo', 'pipefail', '-c', f'{helpers}\n{body}\nget_libraries "$1" "$2"',
                                              'try', str(folder), pin], capture_output=True, text=True, timeout=60)
            done = run(pins)
            self.assertEqual(done.returncode, 0, done.stderr)
            library = folder / f'data/hyprune/libraries/{test_content.LIB}@1.2.0'
            self.assertTrue((library / 'library.json').is_file())
            record, = json.loads((folder / 'state/hyprune/content.json').read_text())['installs']
            self.assertEqual((record['id'], record['source'], record['current']['tag']),
                             (test_content.LIB, 'official', 'street-v1.2.0'))
            self.assertEqual(run(pins).stdout, '')  # rerun: kept, nothing downloaded
            shutil.rmtree(library)
            bad = run(pins.replace(sha, '0' * 64))
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('sha256 mismatch', bad.stderr)
            self.assertFalse(library.exists())

    @unittest.skipUnless(shutil.which('curl'), 'curl needed')
    def test_try_cli_is_built_from_the_pinned_sdk_and_optional(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source = temp / 'src/sdk-rev'
            (source / 'scripts').mkdir(parents=True)
            (source / 'package.json').write_text('{}')
            archive = temp / 'sdk.tar.gz'
            subprocess.run(['tar', '-C', str(temp / 'src'), '-czf', str(archive), 'sdk-rev'], check=True)
            sha = subprocess.run(['sha256sum', str(archive)], capture_output=True, text=True).stdout.split()[0]
            fake = temp / 'fake-bin'; fake.mkdir()
            (fake / 'node').write_text('#!/bin/sh\n[ "$1" = --version ] && echo v22.12.0 && exit 0\necho "node $*"\n')
            # npm ci must keep its cache in the folder; build writes the CLI entry point.
            (fake / 'npm').write_text('#!/bin/sh\necho "npm $* cache=$npm_config_cache" >> "$NPM_LOG"\n'
                                      '[ -n "$NPM_FAIL" ] && exit 1\n'
                                      '[ "$1" = run ] && mkdir -p dist/src && echo cli > dist/src/cli.js\nexit 0\n')
            for tool in ['node', 'npm']:
                (fake / tool).chmod(0o755)
            folder = temp / 'try'
            for sub in ['bin', 'downloads']:
                (folder / sub).mkdir(parents=True)
            script = (ROOT / 'try/try.sh').read_text()
            helpers = '\n'.join(l for l in script.splitlines() if l.startswith(('step()', 'die()', 'fetch()', 'verify()')))
            body = script[script.index('get_cli() {'):]
            body = body[:body.index('\n}\n') + 3]
            manifest = '\n'.join(['{', f'  "sdkRev": "{"a" * 40}",', f'  "sdkUrl": "file://{archive}",',
                                   f'  "sdkSha256": "{sha}",', '  "node": "22.12"', '}'])
            log = temp / 'npm.log'
            run = lambda **env: subprocess.run(
                ['bash', '-euo', 'pipefail', '-c', f'HYPRUNE_CHECK_LIB=1 source {ROOT}/try/check.sh\n{helpers}\n{body}\n'
                 'MANIFEST_TEXT=$(<"$2"); get_cli "$1"', 'try', str(folder), str(temp / 'manifest.json')],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, 'PATH': f"{fake}:{os.environ['PATH']}", 'NPM_LOG': str(log), **env})
            (temp / 'manifest.json').write_text(manifest)
            done = run()
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((folder / 'bin/hyprune').read_text(), f'#!/bin/sh\nexec node "{folder}/sdk/dist/src/cli.js" "$@"\n')
            self.assertEqual(log.read_text().splitlines(), [
                f'npm ci --ignore-scripts --no-audit --no-fund cache={folder}/downloads/npm',
                f'npm run build cache={folder}/downloads/npm'])
            failed = run(NPM_FAIL='1')
            self.assertEqual(failed.returncode, 0, failed.stderr)
            self.assertIn('the hyprune CLI did not build', failed.stdout)
            self.assertFalse((folder / 'bin/hyprune').exists())
            self.assertFalse((folder / 'sdk').exists())
            (temp / 'manifest.json').write_text(manifest.replace('"22.12"', '"99.0"'))
            skipped = run()
            self.assertEqual((skipped.returncode, skipped.stdout), (0, ''))

    @unittest.skipUnless(shutil.which('curl'), 'curl needed')
    def test_try_plan_lists_the_published_libraries(self):
        # A copy of the repository whose check.sh always reports "ready", so the plan is printed.
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as base:
            for name in ['try', 'kits', 'worlds', 'libraries']:
                shutil.copytree(ROOT / name, Path(base) / name)
            with (Path(base) / 'try/check.sh').open('a') as check:
                check.write('collect_checks() { MANIFEST_TEXT=$(curl -fsSL --proto "=https,file" "$MANIFEST"); '
                            'VERDICT=ready CORE=prebuilt; }\nreport_text() { :; }\n')
            env = {**os.environ, 'HOME': home, 'HYPRUNE_BASE': 'file://' + base}
            run = lambda *extra: subprocess.run(['bash', str(ROOT / 'try/try.sh'), '--dry-run', '--dir', home + '/try', *extra],
                                                capture_output=True, text=True, env=env, timeout=120)
            plan = run()
            self.assertEqual(plan.returncode, 0, plan.stderr)
            pins = [r for r in json.loads((ROOT / 'libraries/releases.json').read_text()).values() if r['published']]
            self.assertTrue(pins)
            for pin in pins:
                self.assertRegex(plan.stdout, rf"\n  library {re.escape(pin['id'])} {re.escape(pin['version'])}\n")
            self.assertIn('Dry run: nothing was downloaded or written.', plan.stdout)
            self.assertRegex(plan.stdout, r'\n  cli     (hyprune/sdk@[0-9a-f]{7}: the hyprune command|skipped: needs Node\.js)')
            skipped = run('--no-libraries')
            self.assertIn('  library none (--no-libraries)\n', skipped.stdout)
            self.assertNotIn(f"library {pins[0]['id']}", skipped.stdout)
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
