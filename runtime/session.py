#!/usr/bin/env python3
"""Own one compositor child, then autostart its authenticated shell and kit apps."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
from setup import init

TARGET = '0.56.2'
CAPABILITIES = ['state.read', 'world.control', 'surface.control', 'movement.control',
                'shell.control', 'runtime.control', 'input.control', 'quest.control',
                'objects.control']
SOURCES_CLIENT = 'com.hyprune.sources'
TOKEN_VARIABLES = ['HYPRUNE_TOKEN_FD', 'HYPRUNE_TOKEN_REFRESH', 'HYPRUNE_SOURCES_TOKEN', 'HYPRUNE_MACHINES_TOKEN']


def source_helper(env=os.environ):
    """Core's installed source helper, or None.

    HYPRUNE_SOURCE_HELPER names it explicitly; otherwise it is
    <prefix>/libexec/hyprune/source-helper beside the plugin at
    <prefix>/lib/hyprune-core.so (HYPRUNE_PLUGIN), the layout of core's release
    archive, the Nix package and the source installer's generations.
    """
    if env.get('HYPRUNE_SOURCE_HELPER'):
        path = Path(env['HYPRUNE_SOURCE_HELPER'])
    elif env.get('HYPRUNE_PLUGIN'):
        path = Path(env['HYPRUNE_PLUGIN']).parent.parent / 'libexec/hyprune/source-helper'
    else:
        return None
    return path if path.is_file() else None


SESSION_VARIABLES = ['HYPRUNE_SESSION_GRANTS', 'HYPRUNE_SESSION_DAEMON', 'HYPRUNE_SESSION_PYTHON']
DAEMON_WRAPPER = Path(__file__).resolve().parent / 'session-daemon'


def core_daemon(env=os.environ):
    """The hypruned that core's plugin would start: HYPRUNE_DAEMON, else <prefix>/bin/hypruned."""
    if env.get('HYPRUNE_DAEMON', '').startswith('/'):
        path = Path(env['HYPRUNE_DAEMON'])
    elif env.get('HYPRUNE_PLUGIN'):
        path = Path(env['HYPRUNE_PLUGIN']).parent.parent / 'bin/hypruned'
    else:
        return None
    return path if path.is_file() else None


def session_daemon():
    """HYPRUNE_DAEMON of a hyprune-session compositor (runtime/session-daemon runs this).

    Core's plugin spawns it with its private bridge (fd 3) and launch grants (fd 4).
    It connects to the session's one-shot grants socket and execs the real hypruned
    with that connection as HYPRUNE_GRANT_FD: core's grant issuer, which reissues
    PID-bound tokens for clients of the launch manifest. The channel exists only in
    hypruned and the session, never in the compositor or its other children. Without
    the socket, hypruned starts without renewal.
    """
    path = os.environ.get('HYPRUNE_SESSION_GRANTS')
    real = os.environ['HYPRUNE_SESSION_DAEMON']
    env = {k: v for k, v in os.environ.items() if k not in SESSION_VARIABLES + ['HYPRUNE_GRANT_FD']}
    try:
        channel = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        channel.connect(path)
        os.set_inheritable(channel.fileno(), True)
        env['HYPRUNE_GRANT_FD'] = str(channel.fileno())
    except (OSError, TypeError) as error:
        print(f'hyprune-session: no grant renewal for hypruned: {error}', file=sys.stderr, flush=True)
    os.execve(real, [real], env)


def accept_grant_channel(server, compositor, timeout=5):
    """The session's end of hypruned's grant channel, or None. Only our compositor's own
    child (the plugin's hypruned) is accepted, once."""
    server.settimeout(timeout)
    try:
        peer, _ = server.accept()
    except OSError:
        return None
    finally:
        server.close()
    try:
        pid, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        parent = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
        if uid == os.getuid() and parent == compositor.pid:
            return peer
    except (OSError, ValueError, IndexError):
        pass
    peer.close()
    return None


class GrantBroker:
    """Renews one child's launch grant: it writes `renew\\n` on a private socket; we ask
    core's grant issuer for a fresh token bound to its PID and write the token line back.
    Requests carry kernel credentials and must come from that PID; at most 8 a second and
    4096 in total. Any irregularity closes the channel (fail closed)."""

    def __init__(self, channel, issuer, child, client):
        self.channel, self.issuer, self.child, self.pid, self.client = channel, issuer, child, child.pid, client
        self.buffer, self.count, self.window, self.burst = b'', 0, time.monotonic(), 0
        channel.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        issuer.settimeout(3)

    def handle(self):
        """Serve the readable channel; False when it must close."""
        data, ancillary, flags, _ = self.channel.recvmsg(64, socket.CMSG_SPACE(12))
        if not data:
            return False
        credentials = [struct.unpack('3i', value[:12]) for level, kind, value in ancillary
                       if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS]
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or credentials != [(self.pid, os.getuid(), os.getgid())]:
            return False
        self.buffer += data
        if len(self.buffer) > 64:
            return False
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            now = time.monotonic()
            if now - self.window >= 1:
                self.window, self.burst = now, 0
            if line != b'renew' or self.count >= 4096 or self.burst >= 8:
                return False
            self.count += 1; self.burst += 1
            token = secrets.token_hex(32)
            self.issuer.send(json.dumps(dict(client=self.client, pid=self.pid, token=token)).encode())
            if json.loads(self.issuer.recv(1024)) != {'ok': True}:
                return False
            self.channel.sendall((token + '\n').encode())
        return True


def start_sources(helper, config, control, token, env, log_path, renew=False):
    """Start core's source helper with its own data.publish grant, always: with no
    sources.json it idles until the file appears (edits from the Director included).

    The launch token is the first line on an inherited descriptor (never argv, the
    environment or a file). With `renew` it is a socket and the helper asks for a
    fresh token per reconnection (`--token-refresh`, served by GrantBroker); without,
    it is a pipe that then closes. <prefix>/bin goes first on its PATH so sources.json
    can name hyprune-system-gauges. Returns (process, session end of the channel or None).
    """
    env = {k: v for k, v in env.items() if k not in TOKEN_VARIABLES}
    if helper.parent.name == 'hyprune' and helper.parent.parent.name == 'libexec':
        env['PATH'] = os.pathsep.join(filter(None, [str(helper.parent.parent.parent / 'bin'), env.get('PATH')]))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if renew:
        channel, child_end = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        channel.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)  # before the child can write
        channel.sendall((token + '\n').encode())
        token_fd = child_end.detach()
    else:
        channel, token_fd = None, pipe_payload((token + '\n').encode())
    try:
        with open(log_path, 'a') as log:
            child = subprocess.Popen([sys.executable, str(helper), '--config', str(config), '--socket', control,
                                      '--token-fd', str(token_fd)] + (['--token-refresh'] if renew else []),
                                     env=env, pass_fds=(token_fd,), stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT)
    except OSError:
        if channel:
            channel.close()
        raise
    finally:
        os.close(token_fd)
    return child, channel


def serve(compositor, brokers, interval=.25):
    """Wait for the compositor, renewing grants meanwhile. A broker whose channel fails
    is dropped (its child keeps its current connection); the session goes on."""
    while compositor.poll() is None:
        channels = {b.channel: b for b in brokers}
        issuers = {b.issuer for b in brokers}
        if not channels:
            return compositor.wait()
        try:
            readable = select.select(list(channels) + list(issuers), [], [], interval)[0]
        except OSError:
            readable = []
        for item in readable:
            broker = channels.get(item)
            try:
                ok = broker is not None and broker.handle()
            except (OSError, ValueError):
                ok = False
            if not ok:  # the child exited, or unsolicited issuer data or a bad request
                for b in list(brokers):
                    if b is broker or item is b.issuer:
                        brokers.remove(b); b.channel.close()
                        try:
                            code = b.child.wait(timeout=1)
                            message = f'{b.client} exited with status {code}'
                        except subprocess.TimeoutExpired:
                            message = f'stopped renewing {b.client} grants'
                        print(f'hyprune-session: {message}', file=sys.stderr, flush=True)
    return compositor.returncode


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
    grants = [
        dict(token=token, client='com.hyprune.shell', capabilities=CAPABILITIES),
        dict(token=bootstrap_token, client='com.hyprune.starter', capabilities=['world.control']),
    ]
    # Gauges and other machines: the source helper always runs, with only data.publish.
    sources = config_dir / 'sources.json'
    helper = source_helper()
    sources_token = secrets.token_hex(32) if helper else None
    if sources_token:
        grants.append(dict(token=sources_token, client=SOURCES_CLIENT, capabilities=['data.publish']))
    else:
        print('hyprune-session: core has no source helper here; machines get no data',
              file=sys.stderr, flush=True)
    # Renewal: hypruned starts through runtime/session-daemon, which hands it a private
    # grant channel from this one-shot socket (see session_daemon).
    real_daemon = core_daemon()
    grants_dir = grants_server = None
    if sources_token and real_daemon and DAEMON_WRAPPER.is_file():
        grants_dir = Path(tempfile.mkdtemp(prefix='hyprune-session-', dir=runtime))
        grants_server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        grants_server.bind(str(grants_dir / 'grants.sock'))
        grants_server.listen(1)
        env.update(HYPRUNE_DAEMON=str(DAEMON_WRAPPER), HYPRUNE_SESSION_DAEMON=str(real_daemon),
                   HYPRUNE_SESSION_GRANTS=str(grants_dir / 'grants.sock'), HYPRUNE_SESSION_PYTHON=sys.executable)
    grant_fd = pipe_payload(json.dumps(grants).encode())
    env['HYPRUNE_LAUNCH_FD'] = str(grant_fd)
    children = []
    brokers = []
    issuer = None
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
        if grants_server:
            issuer = accept_grant_channel(grants_server, compositor)
            grants_server = None
            if issuer is None:
                print('hyprune-session: hypruned did not connect its grant channel; no renewal',
                      file=sys.stderr, flush=True)
        # No HYPRUNE_PROTOCOL: the shell negotiates its newest vendored protocol with core.
        child_env = {k: v for k, v in {**env, **local}.items() if k not in SESSION_VARIABLES + ['HYPRUNE_DAEMON']}
        if 'HYPRUNE_DAEMON' in os.environ:
            child_env['HYPRUNE_DAEMON'] = os.environ['HYPRUNE_DAEMON']
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
        # Its launch token expires 30 s after core starts, like the shell's: start it now.
        if sources_token and not stopping:
            try:
                sources_child, channel = start_sources(helper, sources, local['HYPRUNE_SOCKET'], sources_token,
                                                       child_env, state_dir / 'source-helper.log', renew=issuer is not None)
                children.append(sources_child)
                if channel:
                    brokers.append(GrantBroker(channel, issuer, sources_child, SOURCES_CLIENT))
            except OSError as error:
                print(f'hyprune-session: source helper not started: {error}', file=sys.stderr, flush=True)
        for app in config.get('apps', []):
            if stopping:
                break
            children.append(subprocess.Popen(app['argv'], env=child_env))
        # Neither the shell nor the source helper is restarted when it exits. The helper
        # renews its grant to reconnect; the shell still holds a one-use token.
        return serve(compositor, brokers)
    finally:
        if grant_fd >= 0:
            os.close(grant_fd)
        for item in [grants_server, issuer] + [b.channel for b in brokers]:
            if item:
                item.close()
        if grants_dir:
            shutil.rmtree(grants_dir, ignore_errors=True)
        for child in reversed(children + ([compositor] if compositor else [])):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()


def main():
    if sys.argv[1:] == ['--session-daemon']:
        return session_daemon()
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
