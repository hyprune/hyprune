#!/usr/bin/env python3
"""Arch-first installer. Never invokes hyprctl or loads into an existing session."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from setup import ROOT, init, load_kit, render
import content
from content import extract_package
import icons

TARGET = '0.56.2'
DEPENDENCIES = ['base-devel', 'cmake', 'ninja', 'git', 'pkgconf', 'hyprgraphics',
                'pixman', 'libdrm', 'libxkbcommon', 'pango', 'wayland', 'wayland-protocols',
                'mesa', 'libxml2', 'openssl', 'lua', 'libpng', 'freetype2', 'fontconfig',
                'vulkan-icd-loader', 'vulkan-headers', 'quickshell', 'qt6-5compat',
                'python', 'python-pip', 'nodejs', 'npm', 'kitty', 'btop', 'zstd']
INCLUDE = '''-- BEGIN HYPRUNE STARTER
dofile((os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/hyprune/hyprune.lua")
-- END HYPRUNE STARTER
'''


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def approved_edit(path, new, input_fn=input):
    """Diff then prompt every time; no --yes option. Refuse symlink targets."""
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError(f'{path} is managed by a symlink; add the include through its manager')
    old = path.read_text() if path.exists() else ''
    if old == new:
        return True
    print(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                     fromfile=str(path), tofile=str(path) + ' (proposed)')))
    try:
        answer = input_fn(f'Apply this exact diff to {path}? [y/N] ')
    except EOFError:
        answer = ''
    if answer.strip().lower() not in ['y', 'yes']:
        print('Hyprland config preserved. Use the standalone starter session instead.')
        return False
    if path.exists():
        backup = path.with_name(path.name + f'.hyprune-backup-{time.time_ns()}')
        shutil.copy2(path, backup)
        print(f'Backup: {backup}')
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.hyprune-config-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(new)
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return True


def extract_world(archive, destination, world_id):
    """Hash checking is the caller's job. Reject traversal, links and devices (content.extract_package)."""
    return extract_package(archive, destination, world_id, 'world')


def published_libraries():
    """The published pins of libraries/releases.json (RFC-0011), in file order."""
    return [r for r in json.loads((ROOT / 'libraries/releases.json').read_text()).values() if r['published']]


def install_libraries(pins, root, state, receipt, fetch=urllib.request.urlretrieve):
    """Download, verify and unpack each pin into root/<id>@<version>/ with an official record.

    receipt maps the directories this installer created to their archive sha256 (for uninstall)."""
    for pin in pins:
        status = content.library_status(pin, root, state)
        if status != 'install':
            print(f"Library {pin['id']} {pin['version']}: " + {
                'present': 'already installed', 'skipped': 'content.json records another version; kept'}[status])
            continue
        with tempfile.TemporaryDirectory(prefix='hyprune-library-') as temp:
            archive = Path(temp) / 'library.tar.zst'
            fetch(pin['url'], archive)
            result = content.install_official_library(pin, archive, root, state)
        print(f"Library {pin['id']} {pin['version']}: {result}")
        if result == 'installed':
            receipt[str(Path(root) / f"{pin['id']}@{pin['version']}")] = pin['sha256']


def run(*argv, cwd=None):
    print('+', ' '.join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), cwd=cwd, check=True)


def source(repo, revision, local, destination):
    if local:
        path = Path(local) / repo
        destination.mkdir()
        for name in local_source_files(path):
            src = path / name
            if not src.exists() and not src.is_symlink():
                continue
            dst = destination / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                dst.symlink_to(os.readlink(src))
            else:
                shutil.copy2(src, dst)
    else:
        destination.mkdir()
        run('git', 'init', '-q', destination)
        run('git', '-C', destination, 'fetch', '--depth', '1', f'https://github.com/hyprune/{repo}.git', revision)
        run('git', '-C', destination, 'checkout', '--detach', 'FETCH_HEAD')


def local_source_files(path):
    data = subprocess.check_output(['git', '-C', str(path), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    return sorted(set(name.decode() for name in data.split(b'\0') if name))


def local_fingerprint(root):
    h = hashlib.sha256()
    for repo in ['core', 'shell', 'sdk']:
        path = Path(root) / repo
        for name in local_source_files(path):
            file = path / name
            h.update((repo + '/' + name + '\0').encode())
            if file.is_symlink():
                h.update(('link:' + os.readlink(file)).encode())
            elif file.is_file():
                h.update(str(file.stat().st_mode & 0o777).encode())
                h.update(digest(file).encode())
            else:
                h.update(b'deleted')
    return h.hexdigest()


def write_managed(path, data, receipt, mode=0o755):
    path = Path(path)
    if path.exists() or path.is_symlink():
        if path.is_file() and not path.is_symlink() and path.read_bytes() == data:
            receipt[str(path)] = digest(path)
            return
        if path.is_file() and not path.is_symlink() and receipt.get(str(path)) == digest(path):
            backup = path.with_name(path.name + f'.hyprune-backup-{time.time_ns()}')
            shutil.copy2(path, backup)
            path.write_bytes(data)
            path.chmod(mode)
            receipt[str(path)] = digest(path)
            print(f'Updated managed file; backup: {backup}')
            return
        raise RuntimeError(f'Refusing to overwrite {path}; move it aside and rerun')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(mode)
    receipt[str(path)] = digest(path)


def install_icons(icon_dir, receipt):
    """App icons in the user's hicolor theme; unchanged copies are removed on uninstall."""
    for source, relative in icons.hicolor_files():
        write_managed(icon_dir / relative, source.read_bytes(), receipt, mode=0o644)


def session_entry(exec_path):
    return ('[Desktop Entry]\nName=Hyprune\nComment=An explorable Hyprland desktop\n'
            f'Exec="{exec_path}"\nIcon={icons.NAME}\nType=Application\nDesktopNames=Hyprland\n')


def write_session_entry(prefix, bin_dir):
    """Login-screen entry kept in the prefix; installing it system-wide needs root, so we only print how."""
    path = prefix / 'share/wayland-sessions/hyprune.desktop'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session_entry(bin_dir / 'hyprune-session'))
    return path


def uninstall(args, prefix, config_dir, state=None):
    receipt_path = prefix / 'receipt.json'
    if not receipt_path.exists():
        print('No script installation receipt; nothing to uninstall.')
        return
    receipt = json.loads(receipt_path.read_text())
    config = Path(receipt['hyprland_config']) if receipt.get('hyprland_config') else None
    if args.dry_run:
        print(f'Dry run: show/ask before removing include from {config}; remove unchanged wrappers, icons and {prefix}.')
        print('Remove the official libraries this installer unpacked, unless they were updated since.')
        print(f'Keep user-owned {config_dir}, layouts/worlds, backups and distro dependencies.')
        return
    if config and config.exists() and INCLUDE in config.read_text():
        if not approved_edit(config, config.read_text().replace(INCLUDE, '')):
            raise RuntimeError('Uninstall stopped because the include still references installed packages')
    for name, expected in {**receipt.get('wrappers', {}), **receipt.get('icons', {})}.items():
        path = Path(name)
        if path.is_file() and not path.is_symlink() and digest(path) == expected:
            path.unlink()
        elif path.exists():
            print(f'Preserving edited file: {path}')
    state = Path(state) if state else content.state_home() / 'hyprune'
    for name, sha256 in receipt.get('libraries', {}).items():
        if content.remove_official_library(name, sha256, state):
            print(f'Removed library {name}')
        elif Path(name).exists():
            print(f'Preserving library {name}: its install record changed since this installer added it')
    backup = prefix.with_name(f'install.uninstalled-{time.time_ns()}')
    prefix.rename(backup)
    print(f'Installation moved to {backup} (rollback backup).')
    print(f'User config/state/worlds and package dependencies preserved. Remove {backup} after review.')



def install_machines(core, prefix):
    """Core's source helper and system gauge script, in the layout of its release archive:
    hyprune-session finds libexec/hyprune/source-helper beside lib/hyprune-core.so."""
    for source, target in [('dev/machines/source-helper.py', 'libexec/hyprune/source-helper'),
                           ('dev/machines/scripts/system-gauges.py', 'share/hyprune/machines/system-gauges.py')]:
        (prefix / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(core / source, prefix / target)
        (prefix / target).chmod(0o755)
    (prefix / 'bin').mkdir(exist_ok=True)
    (prefix / 'bin/hyprune-system-gauges').symlink_to('../share/hyprune/machines/system-gauges.py')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', choices=['lumen-reach', 'minimal', 'dev'], default='lumen-reach')
    parser.add_argument('--kit-file', help='Your forked kit.toml; trusted local app commands')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--source-root', help='Sibling component checkout root (includes uncommitted local work)')
    parser.add_argument('--world-package', action='append', default=[], metavar='NAME=ARCHIVE')
    parser.add_argument('--world-sha256', action='append', default=[], metavar='NAME=SHA256')
    parser.add_argument('--hyprland-config', help='Optional Lua config to extend, after diff and confirmation')
    parser.add_argument('--skip-deps', action='store_true', help='Use already installed dependencies')
    parser.add_argument('--no-libraries', action='store_true', help='Skip the pinned official object libraries')
    parser.add_argument('--jobs', type=int, default=3)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    prefix = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'hyprune/install'
    config_dir = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'hyprune'
    bin_dir = Path.home() / '.local/bin'
    icon_dir = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'icons'
    library_root = content.data_home() / 'hyprune/libraries'
    state = content.state_home() / 'hyprune'
    if args.uninstall:
        uninstall(args, prefix, config_dir, state)
        return
    kit_path = Path(args.kit_file or ROOT / f'kits/{args.kit}/kit.toml').resolve()
    kit = load_kit(kit_path)
    releases = json.loads((ROOT / 'worlds/releases.json').read_text())
    library_pins = [] if args.no_libraries else published_libraries()
    packages = dict(x.split('=', 1) for x in args.world_package)
    hashes = dict(x.split('=', 1) for x in args.world_sha256)
    os_release = Path('/etc/os-release').read_text() if Path('/etc/os-release').exists() else ''
    arch = bool(re.search(r'^ID=(?:"arch"|arch)$', os_release, re.M))
    version = subprocess.check_output(['Hyprland', '--version'], text=True, stderr=subprocess.STDOUT) if shutil.which('Hyprland') else ''
    match = re.search(r'(?<![\d.])v?' + re.escape(TARGET) + r'(?![\d.])', version)
    if version and not match:
        raise RuntimeError(f'Installed Hyprland does not match {TARGET}; refusing an ABI mismatch')
    blockers = []
    if not arch:
        blockers.append('Fedora/Debian builds are not validated; use Nix or port dependencies manually')
    if not version:
        blockers.append(f'Install Hyprland {TARGET} before building')
    for world in kit['worlds']:
        if world == 'minimal':
            continue
        r = releases[world]
        if world in packages:
            if not re.fullmatch(r'[a-f0-9]{64}', hashes.get(world, '')):
                blockers.append(f'{world}: local archive needs --world-sha256 {world}=<64 lowercase hex>')
        elif not r['published']:
            blockers.append(f'{world}: TODO owner must publish the GitHub Release URL and SHA256')
    print(f'Kit: {kit["name"]}; Hyprland: {TARGET}; destination: {prefix}')
    print('Dependencies: sudo pacman -S --needed ' + ' '.join(DEPENDENCIES))
    print('Build core with matching pkg-config headers (hyprpm manifest proposal: proposals/hyprpm.toml).')
    print('Install shell in a Python venv, Quickshell wrapper, SDK CLI; verify and unpack data-only worlds.')
    print(f'Generate once: {config_dir}; backup/refuse replacement of existing files.')
    if library_pins:
        print('Libraries: ' + ', '.join(f"{r['id']} {r['version']}" for r in library_pins) +
              f' into {library_root} (sha256-checked; records in {state}/content.json)')
    else:
        print('Libraries: none' + (' (--no-libraries)' if args.no_libraries else ''))
    print(f'App icons: {icon_dir}/hicolor; login-screen entry: {prefix}/share/wayland-sessions (copy with sudo yourself).')
    print('Hyprland configuration is optional: --hyprland-config PATH shows a diff and asks.')
    for blocker in blockers:
        print('BLOCKED:', blocker)
    if args.dry_run:
        print('Dry run complete: no writes, downloads, package installation or session commands.')
        return
    if blockers:
        raise RuntimeError('Resolve the blockers above before installation')
    if os.getuid() == 0:
        raise RuntimeError('Run as your login user, not root; sudo is used only for pacman')
    if not args.skip_deps:
        run('sudo', 'pacman', '-S', '--needed', *DEPENDENCIES)
    headers = subprocess.check_output(['pkg-config', '--modversion', 'hyprland'], text=True).strip()
    if headers != TARGET:
        raise RuntimeError(f'Plugin headers are {headers}; need {TARGET} generated protocol headers')
    pins = json.loads((ROOT / 'component-pins.json').read_text())
    recipe = hashlib.sha256((ROOT / 'runtime/install.py').read_bytes()).hexdigest()
    local_hash = local_fingerprint(args.source_root) if args.source_root else None
    key = hashlib.sha256(json.dumps([pins, recipe, local_hash]).encode()).hexdigest()[:16]
    generation = prefix / 'versions' / key
    previous = json.loads((prefix / 'receipt.json').read_text()) if (prefix / 'receipt.json').exists() else {}
    prefix.mkdir(parents=True, exist_ok=True)
    if not (generation / 'complete').exists():
        generation.mkdir(parents=True, exist_ok=False)
        try:
            for repo in ['core', 'shell', 'sdk']:
                source(repo, pins[repo]['rev'], args.source_root, generation / repo)
            core = generation / 'core'
            cmake = core / 'CMakeLists.txt'
            # Core embeds build-tree helper paths (daemon, offload renderer); point them at the generation.
            cmake.write_text(cmake.read_text()
                             .replace('${CMAKE_CURRENT_BINARY_DIR}/hypruned', str(generation / 'bin/hypruned'))
                             .replace('${CMAKE_CURRENT_BINARY_DIR}/hyprune-renderer', str(generation / 'bin/hyprune-renderer')))
            run('cmake', '-S', core, '-B', core / 'build', '-G', 'Ninja', '-DBUILD_TESTING=OFF', '-DCMAKE_BUILD_TYPE=RelWithDebInfo')
            run('cmake', '--build', core / 'build', '-j', args.jobs)
            (generation / 'bin').mkdir()
            (generation / 'lib').mkdir()
            for name in ['hypruned', 'hyprune-renderer', 'hyprune-world-check']:
                shutil.copy2(core / 'build' / name, generation / 'bin' / name)
            shutil.copy2(core / 'build/hyprune-core.so', generation / 'lib/hyprune-core.so')
            install_machines(core, generation)
            run(sys.executable, '-m', 'venv', generation / 'venv')
            run(generation / 'venv/bin/pip', 'install', '--require-hashes', '-r', generation / 'shell/requirements.txt')
            run('npm', 'ci', '--ignore-scripts', cwd=generation / 'sdk')
            run('npm', 'run', 'build', cwd=generation / 'sdk')
            (generation / 'complete').touch()
        except Exception:
            # Preserve logs/sources for diagnosis; incomplete generations are never activated.
            generation.rename(generation.with_name(generation.name + '-failed-' + str(time.time_ns())))
            raise
    world_dirs = [ROOT / 'worlds']
    data_worlds = prefix.parent / 'worlds'
    data_worlds.mkdir(exist_ok=True)
    # Copy the original minimal package out of the installer checkout.
    if 'minimal' in kit['worlds'] and not (data_worlds / 'com.hyprune.minimal').exists():
        shutil.copytree(ROOT / 'worlds/minimal', data_worlds / 'com.hyprune.minimal')
    for name in kit['worlds']:
        if name == 'minimal':
            continue
        r = releases[name]
        expected = hashes.get(name, r['sha256'])
        target = data_worlds / r['id']
        if target.exists():
            print(f'Preserving installed world {target}; remove/move explicitly to upgrade it.')
            continue
        with tempfile.TemporaryDirectory(prefix='hyprune-world-') as temp:
            archive = Path(temp) / 'package.tar.zst'
            if name in packages:
                shutil.copyfile(packages[name], archive)
            else:
                urllib.request.urlretrieve(r['url'], archive)
            if digest(archive) != expected:
                raise RuntimeError(f'{name}: archive SHA256 mismatch')
            stage = Path(temp) / 'unpacked'; stage.mkdir()
            manifest = extract_world(archive, stage, r['id'])
            run(generation / 'bin/hyprune-world-check', stage / r['id'])
            shutil.copytree(stage / r['id'], target)
            if expected == r['sha256']:  # the pinned release, not a local development archive
                content.record_official_world(state, r, manifest)
    installed_libraries = dict(previous.get('libraries', {}))
    install_libraries(library_pins, library_root, state, installed_libraries)
    world_dirs = [data_worlds]
    with tempfile.TemporaryDirectory() as temp:
        render(argparse.Namespace(kit=kit_path, output=temp, plugin=generation / 'lib/hyprune-core.so',
               world_dir=world_dirs, settings=None, external_plugin=False,
               input_default=generation / 'core/config/input.default.json'))
        init(temp)
    runtime = generation / 'runtime'
    if not runtime.exists():
        shutil.copytree(ROOT / 'runtime', runtime, ignore=shutil.ignore_patterns('__pycache__'))
    wrappers = dict(previous.get('wrappers', {}))
    # Stable wrappers target the installed generation through an atomic symlink.
    active = prefix / 'current'
    import shlex
    commands = {
        'hyprune-session': [str(active / 'venv/bin/python'), str(active / 'runtime/session.py')],
        # No --protocol: the pinned shell negotiates its newest vendored protocol (as Nix does).
        'hyprune-shell': [str(active / 'venv/bin/python'), str(active / 'shell/bridge/launch.py')],
        'hyprune': ['node', str(active / 'sdk/dist/src/cli.js')],
        'hyprune-mock': ['node', str(active / 'sdk/dist/src/mock-cli.js')],
    }
    for name, argv in commands.items():
        data = ('#!/bin/sh\nexport PATH=' + shlex.quote(str(bin_dir)) + ':"$PATH"\n' +
                ('export HYPRUNE_PLUGIN=' + shlex.quote(str(active / 'lib/hyprune-core.so')) + '\n' if name == 'hyprune-session' else '') +
                'exec ' + shlex.join(argv) + ' "$@"\n').encode()
        write_managed(bin_dir / name, data, wrappers)
    installed_icons = dict(previous.get('icons', {}))
    install_icons(icon_dir, installed_icons)
    session_entry = write_session_entry(prefix, bin_dir)
    # Existing user-owned includes keep their previous plugin path; old generations stay installed.
    if active.is_symlink():
        if not active.resolve().is_relative_to(prefix / 'versions'):
            raise RuntimeError('Refusing to replace an unowned current symlink')
    elif active.exists():
        raise RuntimeError('Refusing to replace an unowned current path')
    if not active.is_symlink() or active.resolve() != generation.resolve():
        staged_link = prefix / f'.current-{time.time_ns()}'
        staged_link.symlink_to(generation)
        staged_link.replace(active)
    config = Path(args.hyprland_config).expanduser().absolute() if args.hyprland_config else None
    configured = previous.get('hyprland_config')
    if config:
        old = config.read_text() if config.exists() else ''
        if INCLUDE in old or approved_edit(config, old + ('\n' if old and not old.endswith('\n') else '') + INCLUDE):
            configured = str(config)
    receipt = dict(wrappers=wrappers, icons=installed_icons, libraries=installed_libraries, generation=str(generation),
                   hyprland_config=configured)
    receipt_file = prefix / 'receipt.json'
    receipt_data = json.dumps(receipt, indent=2) + '\n'
    if not receipt_file.exists() or receipt_file.read_text() != receipt_data:
        if receipt_file.exists():
            shutil.copy2(receipt_file, prefix / f'receipt.backup-{time.time_ns()}.json')
        receipt_file.write_text(receipt_data)
    print('Installed. Put ~/.local/bin on PATH; log out, then run hyprune-session from a TTY.')
    print(f'To list Hyprune on a login screen: sudo install -Dm644 {session_entry} /usr/share/wayland-sessions/hyprune.desktop')
    print('For your normal Lua config: hyprune-session --config PATH (must include hyprune.lua).')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'hyprune-install: {error}', file=sys.stderr)
        raise SystemExit(1)
