import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
import setup
import install
import session


class KitTests(unittest.TestCase):
    def test_real_world_mounts_and_home_contracts(self):
        for name in ['minimal', 'lumen-reach', 'dev']:
            kit = setup.load_kit(ROOT / f'kits/{name}/kit.toml')
            files = setup.compile_kit(kit, '/plugin.so', ['/worlds'], {})
            self.assertEqual(len(files['locations.json']), len(kit.get('homes', [])))
            self.assertEqual(files['layout.json']['version'], 1)
            for app in kit['apps']:
                # The world defines area homes (room 20, workspace_base 20 + slot); explicit kit
                # homes are only cross-world destinations outside the 20-29 group.
                self.assertTrue(21 <= app['workspace'] <= 29 or app['workspace'] in
                                [h['workspace'] for h in kit.get('homes', [])], app)
            for home in kit.get('homes', []):
                self.assertNotIn(home['workspace'], range(20, 30))
                self.assertNotIn('area', home)
            self.assertEqual(files['layout.json']['bindings'], [])
            mounted = [a for a in kit['apps'] if 'mount' in a]
            self.assertEqual([(p['worldId'], p['areaId'], p['anchorId']) for p in files['layout.json']['placements']],
                             [(a['world'], a['area'], a['mount']) for a in mounted])
            self.assertIn(f'workspace = "{kit["initial_workspace"]}", default = true', files['hyprune.lua'])
            self.assertIn('hl.bind("SUPER + 2", hl.dsp.focus({ workspace = "22" }))', files['hyprune.lua'])
            self.assertIn('hl.plugin.load(os.getenv("HYPRUNE_PLUGIN") or "/plugin.so")', files['hyprune.lua'])
            self.assertIn('hl.plugin.hyprune.config', files['hyprune.lua'])
        minimal = json.loads((ROOT / 'worlds/minimal/world.json').read_text())
        kit = setup.load_kit(ROOT / 'kits/minimal/kit.toml')
        area = minimal['areas'][0]
        self.assertEqual((kit['apps'][0]['world'], kit['apps'][0]['area']), (minimal['id'], area['id']))
        self.assertEqual(kit['apps'][0]['workspace'], 20 + int(area['workspaceSlot']))
        self.assertEqual(kit['initial_workspace'], 20 + int(area['workspaceSlot']))
        self.assertIn(kit['apps'][0]['mount'], area['toolAnchors'])
        self.assertEqual(setup.compile_kit(kit, '/p.so', [], {})['session.json']['start'],
                         dict(worldId=minimal['id'], spawnId='arrival'))
        dev = setup.compile_kit(setup.load_kit(ROOT / 'kits/dev/kit.toml'), '/p.so', [], {})
        self.assertEqual(dev['session.json']['start'], dict(worldId='com.hyprune.switchyard', spawnId='arrival'))
        self.assertIn('hl.bind("SUPER + 0", hl.dsp.focus({ workspace = "30" }))', dev['hyprune.lua'])

    def kit(self, **fields):
        base = dict(version=1, name='Test', worlds=['minimal'], keymap='core-default-v2', shell_theme='hyprune-dark',
                    initial_workspace=21, initial_world='com.hyprune.minimal',
                    apps=[dict(workspace=21, world='com.hyprune.minimal', area='quiet-desk', class_='T', title='T',
                               argv=['kitty'], mount='quiet-desk-operator-desk')])
        base.update(fields)
        for app in base['apps']:
            if 'class_' in app:
                app['class'] = app.pop('class_')
        return base

    def test_world_defined_homes_validation(self):
        quiet = dict(world='com.hyprune.minimal', area='quiet-desk', spawn='arrival')
        app = dict(workspace=21, class_='T', title='T', argv=['kitty'])
        mounted = dict(app, mount='quiet-desk-operator-desk')
        invalid = [
            dict(apps=[dict(app, workspace=5)]),                       # neither a kit home nor a default home
            dict(apps=[dict(app, workspace=20)]),                      # the room is not an area home
            dict(apps=[mounted]),                                      # a mount needs world and area
            dict(apps=[dict(mounted, world='com.hyprune.minimal')]),   # world without area
            dict(initial_world=None, apps=[]),                         # default start needs its world
            dict(initial_workspace=7, apps=[]),                        # not room, default home or kit home
            dict(homes=[dict(quiet, workspace=20, label='Q')], apps=[]),   # the room cannot be a kit home
            dict(homes=[dict(quiet, workspace=31, label='Q')]),        # explicit home wins: no default for its area
            dict(apps=[dict(mounted, world='com.hyprune.minimal', area='quiet-desk'),
                       dict(mounted, workspace=22, world='com.hyprune.minimal', area='quiet-desk')]),
            dict(apps=[dict(mounted, world='com.hyprune.minimal', area='quiet-desk'),
                       dict(mounted, world='com.hyprune.minimal', area='other')]),
            dict(settings=dict(windows=dict(workspace_base=0))),       # defaults disabled
        ]
        for fields in invalid:
            kit = self.kit(**fields)
            if kit.get('initial_world', '') is None:
                del kit['initial_world']
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                setup.compile_kit(kit, '/p.so', [], {})
        # Module settings can move the bases; the kit is checked against the merged config.
        with self.assertRaises(ValueError):
            setup.compile_kit(self.kit(), '/p.so', [], dict(windows=dict(workspace_base=30)))
        moved = setup.compile_kit(self.kit(initial_workspace=31, apps=[dict(self.kit()['apps'][0], workspace=31)]),
                                  '/p.so', [], dict(windows=dict(workspace_base=30)))
        self.assertIn('hl.bind("SUPER + 1", hl.dsp.focus({ workspace = "31" }))', moved['hyprune.lua'])
        room = setup.compile_kit(self.kit(initial_workspace=20, initial_spawn='arrival'), '/p.so', [], {})
        self.assertEqual(room['session.json']['start'], dict(worldId='com.hyprune.minimal', spawnId='arrival'))

    def test_explicit_homes_still_win(self):
        homes = [dict(workspace=n, label=a, world='com.hyprune.lumen-reach', area=a, spawn=a)
                 for n, a in [(1, 'sun-court'), (2, 'array-hall')]]
        homes.append(dict(workspace=30, label='Switchyard', world='com.hyprune.switchyard', spawn='arrival'))
        apps = [dict(workspace=1, class_='T', title='T', argv=['kitty'], mount='sun-court-slot-01-operator-desk-01')]
        files = setup.compile_kit(self.kit(homes=homes, initial_workspace=1, initial_world='com.hyprune.lumen-reach',
                                           apps=apps), '/p.so', [], {})
        self.assertEqual(files['layout.json']['bindings'],
                         [dict(id=1, worldId='com.hyprune.lumen-reach', areaId='sun-court'),
                          dict(id=2, worldId='com.hyprune.lumen-reach', areaId='array-hall')])
        self.assertEqual(len(files['locations.json']), 3)
        self.assertEqual(files['layout.json']['placements'][0]['areaId'], 'sun-court')
        self.assertEqual(files['session.json']['start'], dict(worldId='com.hyprune.lumen-reach', spawnId='sun-court'))
        lua = files['hyprune.lua']
        for key, workspace in [(1, 1), (2, 2), (3, 23), (0, 30)]:
            self.assertIn(f'hl.bind("SUPER + {key}", hl.dsp.focus({{ workspace = "{workspace}" }}))', lua)
        self.assertNotIn('workspace = "21" }', lua)
        with self.assertRaises(ValueError):  # the explicit start home names another world
            setup.compile_kit(self.kit(homes=homes, initial_workspace=1, apps=apps), '/p.so', [], {})

    def test_home_manager_uses_native_plugin_option(self):
        files = setup.compile_kit(setup.load_kit(ROOT / 'kits/minimal/kit.toml'), '/p.so', [], {}, True)
        self.assertNotIn('hl.plugin.load', files['hyprune.lua'])
        self.assertIn('quality', files['hyprune.lua'])

    def test_user_owned_generation_preserves_config_and_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            seed = base / 'seed'; seed.mkdir()
            (seed / 'hyprune.lua').write_text('first')
            (seed / 'layout.json').write_text('{"version":1}')
            with patch.dict(os.environ, XDG_CONFIG_HOME=str(base / 'config'), XDG_STATE_HOME=str(base / 'state')):
                config = setup.init(seed)
                (config / 'hyprune.lua').write_text('user edit')
                layout = base / 'state/hyprune/layout.json'; layout.write_text('user layout')
                (seed / 'hyprune.lua').write_text('new defaults')
                setup.init(seed)
                self.assertEqual((config / 'hyprune.lua').read_text(), 'user edit')
                self.assertEqual(layout.read_text(), 'user layout')
                self.assertEqual(layout.stat().st_mode & 0o777, 0o600)

    def test_lua_escaping_is_data(self):
        self.assertEqual(setup.lua('a"\\\n'), '"a\\"\\\\\\n"')
        self.assertEqual(setup.lua(True), 'true')
        self.assertIn('é', setup.lua('é'))


class InstallTests(unittest.TestCase):
    def test_local_source_fingerprint_ignores_builds_and_tracks_working_edits(self):
        if not __import__('shutil').which('git'):
            self.skipTest('git unavailable')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for repo in ['core', 'shell', 'sdk']:
                path = root / repo; path.mkdir()
                subprocess.run(['git', 'init', '-q', str(path)], check=True)
                (path / '.gitignore').write_text('build/\n')
                (path / 'source.txt').write_text('working source')
                subprocess.run(['git', '-C', str(path), 'add', '.'], check=True)
            before = install.local_fingerprint(root)
            generated = root / 'core/build'; generated.mkdir(); (generated / 'temporary-token').write_text('not source')
            self.assertEqual(before, install.local_fingerprint(root))
            (root / 'core/source.txt').write_text('uncommitted source edit')
            self.assertNotEqual(before, install.local_fingerprint(root))
            copy = root / 'copy'
            install.source('core', None, root, copy)
            self.assertEqual((copy / 'source.txt').read_text(), 'uncommitted source edit')
            self.assertFalse((copy / 'build').exists())

    def test_managed_wrapper_updates_have_backup_and_edits_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(temp) / 'wrapper'; receipt = {}
            install.write_managed(path, b'first', receipt)
            install.write_managed(path, b'first', receipt)
            install.write_managed(path, b'new', receipt)
            backup, = Path(temp).glob('*.hyprune-backup-*')
            self.assertEqual(backup.read_bytes(), b'first')
            path.write_bytes(b'user edit')
            with self.assertRaises(RuntimeError):
                install.write_managed(path, b'upgrade', receipt)
            self.assertEqual(path.read_bytes(), b'user edit')

    def test_declining_uninstall_diff_preserves_installation(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            base = Path(temp); prefix = base / 'install'; prefix.mkdir()
            config = base / 'hyprland.lua'; config.write_text(install.INCLUDE)
            (prefix / 'receipt.json').write_text(json.dumps(dict(hyprland_config=str(config))))
            with patch.object(install, 'approved_edit', return_value=False), self.assertRaises(RuntimeError):
                install.uninstall(argparse.Namespace(dry_run=False), prefix, base / 'config')
            self.assertTrue((prefix / 'receipt.json').is_file())
            self.assertEqual(config.read_text(), install.INCLUDE)

    def test_diff_required_and_declined_edit_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()) as output:
            config = Path(temp) / 'hyprland.lua'; config.write_text('-- existing\n')
            self.assertFalse(install.approved_edit(config, '-- changed\n', lambda _: 'n'))
            self.assertEqual(config.read_text(), '-- existing\n')
            self.assertIn('\n--- existing\n', output.getvalue())
            self.assertEqual(list(Path(temp).glob('*.hyprune-backup-*')), [])
            self.assertTrue(install.approved_edit(config, '-- changed\n', lambda _: 'yes'))
            backup, = Path(temp).glob('*.hyprune-backup-*')
            self.assertEqual(backup.read_text(), '-- existing\n')
            self.assertEqual(config.read_text(), '-- changed\n')

    def test_managed_config_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'target'; target.write_text('managed')
            link = Path(temp) / 'hyprland.lua'; link.symlink_to(target)
            with self.assertRaises(RuntimeError):
                install.approved_edit(link, 'replacement', lambda _: 'y')
            self.assertEqual(target.read_text(), 'managed')

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {**os.environ, 'HOME': temp, 'XDG_CONFIG_HOME': temp + '/config', 'XDG_DATA_HOME': temp + '/data'}
            # Through bash from PATH: build sandboxes have no /usr/bin/env for the shebang.
            result = subprocess.run([shutil.which('bash') or 'bash', str(ROOT / 'install.sh'), '--dry-run', '--kit', 'minimal'], env=env,
                                    capture_output=True, text=True)
            # Test host may have an incompatible compositor; that must fail safely.
            self.assertIn(result.returncode, [0, 1])
            self.assertEqual(list(Path(temp).iterdir()), [])
            if result.returncode == 0:
                self.assertIn('no writes', result.stdout)
            else:
                self.assertIn('ABI mismatch', result.stderr)

    def test_archive_rejects_traversal_and_symlinks(self):
        if not __import__('shutil').which('zstd'):
            self.skipTest('zstd unavailable')
        for bad_name, kind in [('com.hyprune.test/../../escape', tarfile.REGTYPE),
                               ('com.hyprune.test/link', tarfile.SYMTYPE)]:
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp); archive = base / 'unsafe.tar'
                with tarfile.open(archive, 'w') as tf:
                    member = tarfile.TarInfo(bad_name); member.type = kind; member.linkname = '/tmp/escape'
                    tf.addfile(member)
                subprocess.run(['zstd', '-q', str(archive)], check=True)
                stage = base / 'unpacked'; stage.mkdir()
                with self.assertRaises(ValueError):
                    install.extract_world(base / 'unsafe.tar.zst', stage, 'com.hyprune.test')
                self.assertFalse((base / 'escape').exists())

    def test_valid_archive_identity(self):
        if not __import__('shutil').which('zstd'):
            self.skipTest('zstd unavailable')
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); archive = base / 'world.tar'
            with tarfile.open(archive, 'w') as tf:
                data = b'{"id":"com.hyprune.test"}'
                member = tarfile.TarInfo('com.hyprune.test/world.json'); member.size = len(data)
                tf.addfile(member, io.BytesIO(data))
            subprocess.run(['zstd', '-q', str(archive)], check=True)
            stage = base / 'unpacked'; stage.mkdir()
            install.extract_world(base / 'world.tar.zst', stage, 'com.hyprune.test')
            self.assertTrue((stage / 'com.hyprune.test/world.json').is_file())

    def test_archive_rejects_oversized_single_file_before_extracting(self):
        if not __import__('shutil').which('zstd'):
            self.skipTest('zstd unavailable')
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); archive = base / 'oversized.tar'
            member = tarfile.TarInfo('com.hyprune.test/huge.bin'); member.size = 128 * 1024**2 + 1
            archive.write_bytes(member.tobuf() + b'\0' * 1024)  # Reject before reading its absent body.
            subprocess.run(['zstd', '-q', str(archive)], check=True)
            stage = base / 'unpacked'; stage.mkdir()
            with self.assertRaisesRegex(ValueError, 'size/file limits'):
                install.extract_world(base / 'oversized.tar.zst', stage, 'com.hyprune.test')
            self.assertEqual(list(stage.iterdir()), [])


    def test_generation_installs_the_source_helper_beside_the_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            core, generation = Path(temp) / 'core', Path(temp) / 'generation'
            for name in ['dev/machines/source-helper.py', 'dev/machines/scripts/system-gauges.py',
                         'dev/machines/scripts/demo-source.py']:
                (core / name).parent.mkdir(parents=True, exist_ok=True)
                (core / name).write_text('#!/usr/bin/env python3\n')
            install.install_machines(core, generation)
            helper = generation / 'libexec/hyprune/source-helper'
            self.assertTrue(os.access(helper, os.X_OK))
            self.assertEqual(session.source_helper(dict(HYPRUNE_PLUGIN=str(generation / 'lib/hyprune-core.so'))), helper)
            gauges = generation / 'bin/hyprune-system-gauges'
            self.assertEqual(gauges.resolve(), (generation / 'share/hyprune/machines/system-gauges.py').resolve())
            self.assertTrue(os.access(gauges, os.X_OK))
            demo = generation / 'bin/hyprune-demo-source'
            self.assertEqual(demo.resolve(), (generation / 'share/hyprune/machines/demo-source.py').resolve())
            self.assertTrue(os.access(demo, os.X_OK))


class WorldFormatTests(unittest.TestCase):
    """The pinned core must load every pinned world release's format."""
    script = ROOT / 'scripts/check-world-formats.py'

    def run_check(self, formats, releases, extra=()):
        with tempfile.TemporaryDirectory() as temp:
            core = Path(temp) / 'core'
            if formats is not None:
                (core / 'src/world').mkdir(parents=True)
                listed = ', '.join('"' + v + '"' for v in formats)
                (core / 'src/world/Format.hpp').write_text(
                    'inline constexpr std::array<std::string_view, %d> supported{%s};\n' % (len(formats), listed))
            path = Path(temp) / 'releases.json'
            path.write_text(json.dumps(releases))
            return subprocess.run([sys.executable, str(self.script), '--core', str(core), str(path), *extra],
                                  capture_output=True, text=True)

    def run_shell(self, formats, releases):
        with tempfile.TemporaryDirectory() as temp:
            bridge = Path(temp) / 'shell/bridge'
            bridge.mkdir(parents=True)
            # The launcher catalog shape: version -> validator (only keys matter here).
            (bridge / 'protocol.py').write_text('WORLD_VALIDATORS = {%s}\n' % ', '.join(repr(v) + ': None' for v in formats))
            path = Path(temp) / 'releases.json'
            path.write_text(json.dumps(releases))
            return subprocess.run([sys.executable, str(self.script), '--shell', str(bridge.parent), str(path)],
                                  capture_output=True, text=True)

    def test_shell_catalog_must_accept_release_formats(self):
        ok = self.run_shell(['0.1', '0.5', '0.7'], {'lumen': {'version': '0.9.0', 'formatVersion': '0.7'}})
        self.assertEqual(ok.returncode, 0, ok.stderr)
        old = self.run_shell(['0.1', '0.2', '0.3', '0.4', '0.5'], {'lumen': {'version': '0.9.0', 'formatVersion': '0.7'}})
        self.assertNotEqual(old.returncode, 0)
        self.assertIn('not accepted by pinned shell', old.stderr)

    def test_component_pins_match_flake_lock(self):
        lock = json.loads((ROOT / 'flake.lock').read_text())['nodes']
        for repo, pin in json.loads((ROOT / 'component-pins.json').read_text()).items():
            self.assertEqual(pin['rev'], lock[repo]['locked']['rev'], repo)

    def test_every_release_records_its_format(self):
        releases = json.loads((ROOT / 'worlds/releases.json').read_text())
        for name, release in releases.items():
            self.assertRegex(release.get('formatVersion', ''), r'^0\.[0-9]+$', name)

    def test_supported_release_passes(self):
        result = self.run_check(['0.1', '0.3', '0.5'], {'w': {'version': '1', 'formatVersion': '0.5'}},
                                [str(ROOT / 'worlds/minimal/world.json')])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unloadable_release_fails(self):
        result = self.run_check(['0.1', '0.2', '0.3'], {'lumen': {'version': '0.7.1', 'formatVersion': '0.5'}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('format 0.5 not accepted by pinned core', result.stderr)

    def test_core_without_registry_fails(self):
        result = self.run_check(None, {'w': {'version': '1', 'formatVersion': '0.2'}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('predates the world format registry', result.stderr)

    def test_missing_recorded_format_fails(self):
        result = self.run_check(['0.2'], {'w': {'version': '1'}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('lacks formatVersion', result.stderr)


class SessionTests(unittest.TestCase):
    def test_worlds_are_real_files_and_existing_packages_survive(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = base / 'source'; world = source / 'com.hyprune.test'
            world.mkdir(parents=True)
            (world / 'world.json').write_text('{"id":"com.hyprune.test"}')
            (world / 'geometry.bin').write_bytes(b'original geometry')
            installed = base / 'installed'
            session.materialize_worlds([source], installed)
            target = installed / world.name
            self.assertFalse(target.is_symlink())
            self.assertFalse((target / 'geometry.bin').is_symlink())
            self.assertEqual((target / 'geometry.bin').read_bytes(), b'original geometry')
            (world / 'geometry.bin').write_bytes(b'new source')
            session.materialize_worlds([source], installed)
            self.assertEqual((target / 'geometry.bin').read_bytes(), b'original geometry')

    def test_supervisor_starts_only_its_child_and_hands_off_one_shot_grant(self):
        # Legacy profile: the initial workspace names a location in locations.json.
        self.run_supervisor([dict(id=1, label='Quiet Desk', worldId='com.hyprune.minimal', spawnId='arrival')], {},
                            dict(worldId='com.hyprune.minimal', spawnId='arrival'))

    def test_supervisor_loads_the_compiled_start_world_without_locations(self):
        # World-defined homes: no kit locations; the compiled start names the world.
        self.run_supervisor([], dict(initial_workspace=21, start=dict(worldId='com.hyprune.minimal')),
                            dict(worldId='com.hyprune.minimal'))

    def test_source_helper_always_starts_and_renews_through_core(self):
        # No sources.json: the helper still starts (it idles until the file appears), with a
        # data.publish-only grant that core's grant issuer renews through session-daemon.
        self.run_supervisor([], dict(initial_workspace=21, start=dict(worldId='com.hyprune.minimal')),
                            dict(worldId='com.hyprune.minimal'), helper='renew')

    def test_source_helper_without_hypruned_gets_a_one_use_grant(self):
        self.run_supervisor([], dict(initial_workspace=21, start=dict(worldId='com.hyprune.minimal')),
                            dict(worldId='com.hyprune.minimal'), helper='one-use')

    def test_source_helper_location(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp)
            helper = prefix / 'libexec/hyprune/source-helper'
            env = dict(HYPRUNE_PLUGIN=str(prefix / 'lib/hyprune-core.so'))
            self.assertIsNone(session.source_helper(env))
            self.assertIsNone(session.core_daemon(env))
            helper.parent.mkdir(parents=True); helper.write_text('')
            (prefix / 'bin').mkdir(); (prefix / 'bin/hypruned').write_text('')
            self.assertEqual(session.source_helper(env), helper)
            self.assertEqual(session.core_daemon(env), prefix / 'bin/hypruned')
            other = prefix / 'checkout-helper.py'; other.write_text('')
            self.assertEqual(session.source_helper(dict(env, HYPRUNE_SOURCE_HELPER=str(other))), other)
            self.assertEqual(session.core_daemon(dict(env, HYPRUNE_DAEMON=str(other))), other)
            self.assertIsNone(session.source_helper(dict(env, HYPRUNE_SOURCE_HELPER=str(prefix / 'missing'))))
            self.assertIsNone(session.source_helper({}))
            self.assertTrue(os.access(session.DAEMON_WRAPPER, os.X_OK))

    def run_supervisor(self, locations, session_fields, expected_load, helper=None):
        # Process/socket fixture; no compositor binary, GPU or owner-session IPC.
        # helper: None (core without a source helper), 'one-use' (a helper, no hypruned to
        # wrap) or 'renew' (both: the fake compositor spawns HYPRUNE_DAEMON like core's plugin).
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); runtime = base / 'runtime'; runtime.mkdir(mode=0o700)
            config = base / 'config/hyprune'; config.mkdir(parents=True)
            (config / 'session.lua').write_text('-- fixture\n')
            (config / 'locations.json').write_text(json.dumps(locations))
            fake = base / 'fake-hyprland'
            # An absolute interpreter: build sandboxes have no /usr/bin/env.
            fake.write_text('#!' + sys.executable + """
import json, os, pathlib, socket, struct, subprocess, sys, time
if '--version' in sys.argv:
    print('Hyprland 0.56.2'); sys.exit(0)
mode = os.environ['FIXTURE_HELPER']
fd = int(os.environ['HYPRUNE_LAUNCH_FD'])
data = os.read(fd, 8192); os.close(fd)
grants = json.loads(data)
assert len(grants) == (2 if mode == 'none' else 3) and grants[0]['client'] == 'com.hyprune.shell'
assert 'input.control' in grants[0]['capabilities']
assert grants[1]['client'] == 'com.hyprune.starter' and grants[1]['capabilities'] == ['world.control']
if mode != 'none':
    assert grants[2]['client'] == 'com.hyprune.sources' and grants[2]['capabilities'] == ['data.publish']
    assert len({g['token'] for g in grants}) == 3
assert 'HYPRLAND_INSTANCE_SIGNATURE' not in os.environ
assert ('HYPRUNE_SESSION_GRANTS' in os.environ) == (mode == 'renew')
root = pathlib.Path(os.environ['XDG_RUNTIME_DIR'])
daemon = None
if mode == 'renew':
    # Like core's plugin: HYPRUNE_DAEMON with the bridge and the launch grants inherited.
    assert os.environ['HYPRUNE_DAEMON'].endswith('/session-daemon')
    bridge, _ = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    read, write = os.pipe(); os.write(write, data); os.close(write)
    daemon = subprocess.Popen([os.environ['HYPRUNE_DAEMON']], pass_fds=(bridge.fileno(), read),
                              env=dict(os.environ, HYPRUNE_BRIDGE_FD=str(bridge.fileno()), HYPRUNE_LAUNCH_FD=str(read)))
    os.close(read)
    while not (root / 'daemon-ready').exists():
        assert daemon.poll() is None, 'hypruned exited'
        time.sleep(.01)
lock = root / 'hypr/fixture/hyprland.lock'; lock.parent.mkdir(parents=True)
lock.write_text(str(os.getpid()) + '\\nwayland-fixture\\n')
native = socket.socket(socket.AF_UNIX); native.bind(str(lock.parent / '.socket.sock')); native.listen()
control = root / 'hyprune/fixture/control.sock'; control.parent.mkdir(parents=True)
server = socket.socket(socket.AF_UNIX); server.bind(str(control)); server.listen(); server.settimeout(10)
def exact(peer, count):
    result = b''
    while len(result) < count:
        part = peer.recv(count - len(result)); assert part; result += part
    return result
seen = []
for _ in range({'none': 2, 'one-use': 3, 'renew': 4}[mode]):
    peer, _ = server.accept(); head = exact(peer, 4)
    seen.append(head)
    if head == b'SHEL':
        assert exact(peer, 65).decode().strip() == grants[0]['token']
    elif head == b'SRCS':
        token = exact(peer, 65).decode().strip()
        if seen.count(b'SRCS') == 1:
            assert token == grants[2]['token']
        else:  # a reconnection: the token core's grant issuer reissued for the helper's PID
            request = json.loads((root / 'renewal').read_text())
            assert request['client'] == 'com.hyprune.sources' and request['token'] == token, request
            peer_pid = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
            assert request['pid'] == peer_pid, (request, peer_pid)
    else:
        hello = json.loads(exact(peer, struct.unpack('!I', head)[0]))
        assert hello['params']['token'] == grants[1]['token']
        def reply(id, result):
            body = json.dumps(dict(jsonrpc='2.0', id=id, result=result)).encode()
            peer.sendall(struct.pack('!I', len(body)) + body)
        reply(hello['id'], dict(protocol='0.6', capabilities=['world.control']))
        size = struct.unpack('!I', exact(peer, 4))[0]; request = json.loads(exact(peer, size))
        assert request['method'] == 'world.load'
        assert request['params'] == json.loads(os.environ['EXPECTED_LOAD']), request['params']
        reply(request['id'], dict(revision=1))
    peer.close()
assert seen.count(b'SRCS') == {'none': 0, 'one-use': 1, 'renew': 2}[mode] and b'SHEL' in seen, seen
server.close(); native.close()
if daemon:
    daemon.terminate(); daemon.wait()
(root / 'authorized').write_text('IPC 0.6 fixture authorized')
""")
            fake.chmod(0o755)
            shell = base / 'fake-shell.py'
            shell.write_text('''import os, socket
assert os.environ['HYPRLAND_INSTANCE_SIGNATURE'] == 'fixture'
assert os.environ['WAYLAND_DISPLAY'] == 'wayland-fixture'
assert 'HYPRUNE_PROTOCOL' not in os.environ  # the shell negotiates its newest protocol
assert 'HYPRUNE_LAUNCH_FD' not in os.environ
assert not [k for k in os.environ if k.startswith('HYPRUNE_SESSION_')]
fd = int(os.environ['HYPRUNE_TOKEN_FD']); token = os.read(fd, 128); os.close(fd)
peer = socket.socket(socket.AF_UNIX); peer.connect(os.environ['HYPRUNE_SOCKET']); peer.sendall(b'SHEL' + token); peer.close()
''')
            prefix = base / 'core'
            if helper:
                path = prefix / 'libexec/hyprune/source-helper'; path.parent.mkdir(parents=True)
                # Started as `python3 <helper>`. One-use: one token line on a pipe, then EOF.
                # Renewable: a socket; `renew` asks for the next token line.
                path.write_text('''import os, socket, sys
args = sys.argv[1:]
renew = os.environ['FIXTURE_HELPER'] == 'renew'
assert args[:2] == ['--config', os.environ['XDG_CONFIG_HOME'] + '/hyprune/sources.json'], args
assert not os.path.exists(args[1])  # always started; it idles until sources.json appears
assert args[2:4] == ['--socket', os.environ['HYPRUNE_SOCKET']] and args[4] == '--token-fd', args
assert args[6:] == (['--token-refresh'] if renew else []), args
assert not {'HYPRUNE_TOKEN_FD', 'HYPRUNE_LAUNCH_FD', 'HYPRUNE_TOKEN_REFRESH', 'HYPRUNE_GRANT_FD'} & set(os.environ)
assert not [k for k in os.environ if k.startswith('HYPRUNE_SESSION_')]
assert os.environ['PATH'].split(os.pathsep)[0] == os.path.dirname(os.path.dirname(os.path.dirname(__file__))) + '/bin'
assert os.environ['HYPRLAND_INSTANCE_SIGNATURE'] == 'fixture'
fd = int(args[5])
def line():
    data = b''
    while not data.endswith(b'\\n'):
        part = os.read(fd, 1); assert part, 'token channel closed'; data += part
    return data
def connect(token):
    peer = socket.socket(socket.AF_UNIX); peer.connect(os.environ['HYPRUNE_SOCKET']); peer.sendall(b'SRCS' + token); peer.close()
print('fixture helper connecting', flush=True)  # the session stops it once the compositor exits
connect(line())
if renew:
    os.write(fd, b'renew\\n'); connect(line())
else:
    assert os.read(fd, 128) == b''
''')
            if helper == 'renew':
                # Stands in for core's hypruned: its grant issuer answers renewals.
                daemon = prefix / 'bin/hypruned'; daemon.parent.mkdir(parents=True)
                daemon.write_text('#!' + sys.executable + """
import os, pathlib, socket
assert os.environ['HYPRUNE_LAUNCH_FD'] and os.environ['HYPRUNE_BRIDGE_FD']
assert not [k for k in os.environ if k.startswith('HYPRUNE_SESSION_')]
issuer = socket.socket(fileno=int(os.environ['HYPRUNE_GRANT_FD']))
assert issuer.type == socket.SOCK_SEQPACKET
root = pathlib.Path(os.environ['XDG_RUNTIME_DIR']); (root / 'daemon-ready').write_text('')
while True:
    request = issuer.recv(1024)
    if not request:
        break
    (root / 'renewal').write_bytes(request)
    issuer.send(b'{"ok": true}')
""")
                daemon.chmod(0o755)
            (config / 'session.json').write_text(json.dumps(dict(dict(world_dirs=[], apps=[],
                initial_workspace=1, shell=[sys.executable, str(shell)]), **session_fields)))
            env = {**os.environ, 'XDG_CONFIG_HOME': str(base / 'config'),
                   'XDG_DATA_HOME': str(base / 'data'), 'XDG_STATE_HOME': str(base / 'state'),
                   'XDG_RUNTIME_DIR': str(runtime), 'PYTHONDONTWRITEBYTECODE': '1',
                   'EXPECTED_LOAD': json.dumps(expected_load), 'FIXTURE_HELPER': helper or 'none',
                   'HYPRUNE_PLUGIN': str(prefix / 'lib/hyprune-core.so')}
            for name in ['HYPRLAND_INSTANCE_SIGNATURE', 'HYPRUNE_SOURCE_HELPER', 'HYPRUNE_DAEMON']:
                env.pop(name, None)
            result = subprocess.run([sys.executable, str(ROOT / 'runtime/session.py'), '--hyprland', str(fake)],
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((runtime / 'authorized').read_text(), 'IPC 0.6 fixture authorized')
            log = base / 'state/hyprune/source-helper.log'
            if helper:
                self.assertEqual(log.read_text(), 'fixture helper connecting\n')
            else:
                self.assertFalse(log.exists())
            self.assertEqual('core has no source helper' in result.stderr, not helper, result.stderr)
            self.assertNotIn('stopped renewing', result.stderr)
            self.assertEqual([p.name for p in runtime.iterdir() if p.name.startswith('hyprune-session-')], [])

    def test_grant_broker_renews_only_for_its_child(self):
        opened = []
        self.addCleanup(lambda: [s.close() for s in opened])
        def broker(pid, reply=b'{"ok": true}'):
            channel, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            channel.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            issuer, daemon = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            opened.extend([channel, child, issuer, daemon])
            requests = []
            def answer():
                requests.append(json.loads(daemon.recv(1024))); daemon.send(reply)
            b = session.GrantBroker(channel, issuer, argparse.Namespace(pid=pid), session.SOURCES_CLIENT)
            return b, child, daemon, requests, answer
        import threading
        b, child, daemon, requests, answer = broker(os.getpid())
        thread = threading.Thread(target=answer); thread.start()
        child.sendall(b'renew\n')
        self.assertTrue(b.handle()); thread.join()
        self.assertEqual({k: requests[0][k] for k in ('client', 'pid')}, dict(client='com.hyprune.sources', pid=os.getpid()))
        self.assertEqual(child.recv(128), requests[0]['token'].encode() + b'\n')
        child.sendall(b'other\n'); self.assertFalse(b.handle())  # only `renew`
        b, child, *_ = broker(os.getpid() + 1)  # a request from another process
        child.sendall(b'renew\n'); self.assertFalse(b.handle())
        b, child, daemon, requests, answer = broker(os.getpid(), reply=b'{"ok": false}')
        thread = threading.Thread(target=answer); thread.start()
        child.sendall(b'renew\n'); self.assertFalse(b.handle()); thread.join()
        child.setblocking(False)
        with self.assertRaises(BlockingIOError):
            child.recv(128)  # core refused: no token goes out
        b, child, *_ = broker(os.getpid())
        child.close(); self.assertFalse(b.handle())  # the child exited

    def test_token_fd_contains_only_payload_and_is_not_inheritable_by_default(self):
        read = session.pipe_payload(b'secret\n')
        try:
            self.assertFalse(os.get_inheritable(read))
            self.assertEqual(os.read(read, 128), b'secret\n')
            self.assertEqual(os.read(read, 128), b'')
        finally:
            os.close(read)

    def test_no_outer_session_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            lock = runtime / 'hypr/outer/hyprland.lock'; lock.parent.mkdir(parents=True)
            lock.write_text(f'{os.getpid()}\nwayland-outer\n')
            child = type('Child', (), {'pid': 99999999, 'poll': lambda self: None})()
            with self.assertRaises(RuntimeError):
                session.child_environment(runtime, child, Path('/private.lua'), timeout=.01)


if __name__ == '__main__':
    unittest.main()
