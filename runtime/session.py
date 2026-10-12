#!/usr/bin/env python3
"""Own one compositor child, then autostart its authenticated shell and kit apps."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import time
from setup import init

TARGET = '0.56.2'
CAPABILITIES = ['state.read', 'world.control', 'surface.control', 'movement.control',
                'shell.control', 'runtime.control', 'input.control', 'quest.control',
                'objects.control']


def bootstrap_world(control, token, location):
    """Load the kit's first world through an authenticated, short-lived IPC client.

    Core's empty-world toggle otherwise loads its developer atrium, not a kit.
    No compositor control socket is used and no token is put in argv or a file.
    """
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(31)
        peer.connect(control)

        def read_exact(size):
            result = bytearray()
            while len(result) < size:
                data = peer.recv(size - len(result))
                if not data:
                    raise RuntimeError('Core disconnected during starter world loading')
                result.extend(data)
            return bytes(result)

        def call(id, method, params):
            body = json.dumps(dict(jsonrpc='2.0', id=id, method=method, params=params)).encode()
            peer.sendall(struct.pack('!I', len(body)) + body)
            while True:
                size, = struct.unpack('!I', read_exact(4))
                if not 0 < size <= 1048576:
                    raise RuntimeError('Invalid IPC frame from core')
                response = json.loads(read_exact(size))
                if response.get('id') == id:
                    return response

        hello = call('starter-hello', 'session.hello', dict(protocols=['0.6'],
            client=dict(id='com.hyprune.starter', name='Hyprune starter'), capabilities=['world.control'], token=token))
        if 'error' in hello:
            raise RuntimeError(f'Core refused starter authentication: {hello["error"]["message"]}')
        deadline = time.monotonic() + 1
        attempt = 0
        while True:
            attempt += 1
            params = dict(worldId=location['worldId'])
            if location.get('spawnId'):
                params['spawnId'] = location['spawnId']  # otherwise the world's default spawn
            response = call(f'starter-load-{attempt}', 'world.load', params)
            if 'result' in response:
                return
            error = response['error']
            # The helper socket can precede the plugin's method advertisement.
            # Only retry a definite "unimplemented" rejection, never a lost mutation.
            if error['code'] != -32601 or time.monotonic() >= deadline:
                raise RuntimeError(f'Core could not load the starter world: {error["message"]}')
            time.sleep(.1)


def pipe_payload(data):
    read, write = os.pipe()
    try:
        os.write(write, data)
    finally:
        os.close(write)
    return read


def materialize_worlds(directories, installed):
    """Core rejects package-root and asset symlinks; copy immutable package bytes."""
    installed.mkdir(parents=True, exist_ok=True)
    for directory in directories:
        if not Path(directory).is_dir():
            continue
        for world in Path(directory).iterdir():
            if not (world / 'world.json').is_file():
                continue
            world_id = json.loads((world / 'world.json').read_text())['id']
            if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', world_id):
                raise ValueError('Invalid world package ID')
            target = installed / world_id
            if target.is_symlink():
                raise RuntimeError(f'Core refuses symlink world roots; move {target} aside first')
            if target.exists():
                continue  # existing data packages remain user-owned, including upgrades
            if world.is_symlink() or any(p.is_symlink() for p in world.rglob('*')):
                raise RuntimeError(f'Core refuses symlinks in world packages: {world}')
            with tempfile.TemporaryDirectory(prefix='.hyprune-world-', dir=installed) as staging:
                copy = Path(staging) / world_id
                shutil.copytree(world, copy)
                copy.rename(target)


def child_environment(runtime, child, config_path, timeout=25):
    """Never select a caller's signature. Find and verify only our child's lock."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('Hyprland exited before Hyprune started')
        for lock in (runtime / 'hypr').glob('*/hyprland.lock'):
            try:
                lines = lock.read_text().splitlines()
                argv = Path(f'/proc/{child.pid}/cmdline').read_bytes().split(b'\0')
                if not lines or lines[0] != str(child.pid) or len(lines) < 2:
                    continue
                if str(config_path).encode() not in argv or lock.stat().st_uid != os.getuid():
                    continue
                signature = lock.parent.name
                if not re.fullmatch(r'[A-Za-z0-9_.-]+', signature):
                    continue
                control = runtime / 'hyprune' / signature / 'control.sock'
                if control.is_socket() and (lock.parent / '.socket.sock').is_socket():
                    return dict(HYPRLAND_INSTANCE_SIGNATURE=signature, WAYLAND_DISPLAY=lines[1],
                                HYPRUNE_SOCKET=str(control))
            except (OSError, IndexError):
                continue
        time.sleep(.1)
    raise RuntimeError('Our compositor did not load Hyprune within 25s; check the plugin/config/ABI')


def run(args, extra):
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') and not args.nested:
        raise RuntimeError('Start hyprune-session from a TTY/login screen, or explicitly use --nested')
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    if not runtime.is_absolute() or runtime.stat().st_uid != os.getuid():
        raise RuntimeError('XDG_RUNTIME_DIR must be absolute and owned by this user')
    if args.seed:
        init(args.seed)
    config_dir = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'hyprune'
    state_dir = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hyprune'
    data_dir = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'hyprune'
    config = json.loads((config_dir / 'session.json').read_text())
    normal = config_dir.parent / 'hypr/hyprland.lua'
    # HM's generated config contains the module's include; explicit -c also works.
    config_path = Path(args.config or (normal if args.prefer_user_config and normal.is_file() else config_dir / 'session.lua')).resolve()
    version = subprocess.check_output([args.hyprland, '--version'], text=True, stderr=subprocess.STDOUT)
    if not re.search(r'(?<![\d.])v?' + re.escape(TARGET) + r'(?![\d.])', version):
        raise RuntimeError(f'Hyprune needs Hyprland {TARGET}; installed binary differs')
    installed = data_dir / 'worlds'
    directories = json.loads(os.environ.get('HYPRUNE_PACKAGED_WORLD_DIRS', '[]')) + config['world_dirs']
    materialize_worlds(directories, installed)
    env = dict(os.environ)
    for name in ['HYPRLAND_INSTANCE_SIGNATURE', 'HYPRUNE_TOKEN_FD', 'HYPRUNE_SOCKET', 'HYPRUNE_LAUNCH_FD']:
        env.pop(name, None)
    env.update(HYPRUNE_WORLD_DIR=str(installed), HYPRUNE_WORKSPACE_LOCATIONS=str(config_dir / 'locations.json'),
               HYPRUNE_LAYOUT_FILE=str(state_dir / 'layout.json'), HYPRUNE_INPUT_FILE=str(config_dir / 'input.json'),
               HYPRUNE_EDITOR_FILE=str(state_dir / 'editor.json'))
    if args.nested:
        env['AQ_BACKEND'] = 'wayland'
    token = secrets.token_hex(32)
    bootstrap_token = secrets.token_hex(32)
    grant_fd = pipe_payload(json.dumps([
        dict(token=token, client='com.hyprune.shell', capabilities=CAPABILITIES),
        dict(token=bootstrap_token, client='com.hyprune.starter', capabilities=['world.control']),
    ]).encode())
    env['HYPRUNE_LAUNCH_FD'] = str(grant_fd)
    children = []
    compositor = None
    stopping = False

    def stop(_sig, _frame):
        nonlocal stopping
        stopping = True
        if compositor and compositor.poll() is None:
            compositor.terminate()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, stop)
    try:
        compositor = subprocess.Popen([args.hyprland, '-c', str(config_path), *extra], env=env, pass_fds=(grant_fd,))
        os.close(grant_fd); grant_fd = -1
        local = child_environment(runtime, compositor, config_path)
        # No HYPRUNE_PROTOCOL: the shell negotiates its newest vendored protocol with core.
        child_env = {**env, **local}
        child_env.pop('HYPRUNE_LAUNCH_FD', None)
        # Kits compiled since world-defined homes carry the start world; older
        # user-owned profiles still name an initial workspace in locations.json.
        location = config.get('start')
        if location is None:
            locations = json.loads((config_dir / 'locations.json').read_text())
            location = next((h for h in locations if h['id'] == config['initial_workspace']), None)
        if location is None:
            raise RuntimeError('Initial workspace has no location in locations.json')
        # A committed load also proves the complete method profile is advertised
        # before the shell consumes its own launch token.
        bootstrap_world(local['HYPRUNE_SOCKET'], bootstrap_token, location)
        if args.enter:
            # Our own verified child only; the world is loaded, so this never falls back to the atrium.
            subprocess.run(['hyprctl', '-i', local['HYPRLAND_INSTANCE_SIGNATURE'], 'eval', 'hl.plugin.hyprune.toggle()'],
                           env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        token_fd = pipe_payload((token + '\n').encode())
        try:
            children.append(subprocess.Popen(config['shell'], env={**child_env, 'HYPRUNE_TOKEN_FD': str(token_fd)}, pass_fds=(token_fd,)))
        finally:
            os.close(token_fd)
        for app in config.get('apps', []):
            if stopping:
                break
            children.append(subprocess.Popen(app['argv'], env=child_env))
        # No auto-restart with a spent token: core has no production renewal API.
        return compositor.wait()
    finally:
        if grant_fd >= 0:
            os.close(grant_fd)
        for child in reversed(children + ([compositor] if compositor else [])):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed')
    parser.add_argument('--hyprland', default='Hyprland')
    parser.add_argument('-c', '--config')
    parser.add_argument('--nested', action='store_true')
    parser.add_argument('--window', action='store_true',
                        help='Nested window in the current Wayland session, without the developer test lock')
    parser.add_argument('--enter', action='store_true', help='Enter the world as soon as the start world is loaded')
    parser.add_argument('--prefer-user-config', action='store_true', help='Use the Home Manager generated Lua config')
    args, extra = parser.parse_known_args()
    window, args.nested = args.window, args.nested or args.window
    try:
        if args.nested and not window:
            with open('/tmp/worldshell-nested.lock', 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                return run(args, extra)
        return run(args, extra)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'hyprune-session: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
