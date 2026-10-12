#!/usr/bin/env python3
"""Nested end-to-end check of hyprune-session's source helper (Director data sources).

    scripts/sources-e2e.py CORE_PREFIX SHELL_DIR WORLDS_DIR

CORE_PREFIX is an unpacked core release archive (hyprune-core/: lib, bin, libexec, share),
SHELL_DIR a hyprune/shell checkout, WORLDS_DIR a directory holding world packages. It renders
the minimal kit into temporary XDG directories (never your profile), starts
runtime/session.py --nested (it takes the nested test lock), finds that session's own
compositor by its lock file, and drives the helper through the shell bridge's sources
module, the backend of Director > Objects > Placed > Data source:
1. the session always starts the helper: idle without sources.json, connected;
2. Test runs the installed hyprune-system-gauges through the helper;
3. a sources.json written after start is picked up and published (no restart);
4. Restart helper reconnects with a token renewed through the session;
5. stopping the session stops the helper.
Exit 0 when every check passes; results in <tmp>/e2e.json.
"""
import asyncio, importlib.util, json, os, pathlib, signal, subprocess, sys, tempfile, time

if len(sys.argv) != 4:
    raise SystemExit(__doc__)
R, SHELL, WORLDS = (pathlib.Path(a).resolve() for a in sys.argv[1:4])
META = pathlib.Path(__file__).resolve().parents[1]
E = pathlib.Path(tempfile.mkdtemp(prefix='hyprune-sources-e2e-'))
for d in ('config', 'state', 'data'):
    (E / d).mkdir()
xdg = {'XDG_CONFIG_HOME': str(E / 'config'), 'XDG_STATE_HOME': str(E / 'state'), 'XDG_DATA_HOME': str(E / 'data')}
subprocess.run([sys.executable, str(META / 'runtime/setup.py'), 'install', '--kit', str(META / 'kits/minimal/kit.toml'),
                '--plugin', str(R / 'lib/hyprune-core.so'), '--input-default', str(R / 'share/hyprune/input.default.json'),
                '--world-dir', str(WORLDS)], env={**os.environ, **xdg}, check=True, stdout=subprocess.DEVNULL)
config = E / 'config/hyprune/session.json'
session_config = json.loads(config.read_text())
start = next(json.loads((w / 'world.json').read_text())['id'] for w in sorted(WORLDS.iterdir()) if (w / 'world.json').is_file())
session_config.update(start={'worldId': start, 'spawnId': json.loads((WORLDS / start / 'world.json').read_text())['defaultSpawn']},
                      apps=[], shell=[sys.executable, str(SHELL / 'bridge/launch.py')])
config.write_text(json.dumps(session_config, indent=2) + '\n')
spec = importlib.util.spec_from_file_location('sources', SHELL / 'bridge/sources.py'); sources = importlib.util.module_from_spec(spec); spec.loader.exec_module(sources)
env = {**os.environ, **xdg,
       'HYPRUNE_PLUGIN': str(R / 'lib/hyprune-core.so'), 'HYPRUNE_RENDERER': str(R / 'bin/hyprune-renderer'),
       'PATH': f"{R / 'bin'}:{os.environ['PATH']}", 'TMPDIR': str(E)}
log = open(E / 'session.log', 'w')
session = subprocess.Popen([sys.executable, str(META / 'runtime/session.py'), '--nested'], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
results = []
def check(name, ok, data=None):
    results.append({'name': name, 'ok': bool(ok), 'evidence': data}); print(('PASS ' if ok else 'FAIL ') + name, json.dumps(data)[:240], flush=True)
    return ok
def wait(fn, timeout):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(.3)
    return None
try:
    def own_socket():  # our session's child compositor only (its lock names its pid)
        pids = subprocess.run(['pgrep', '-P', str(session.pid), '-x', 'Hyprland'], capture_output=True, text=True).stdout.split()
        for lock in (pathlib.Path(os.environ['XDG_RUNTIME_DIR']) / 'hypr').glob('*/hyprland.lock'):
            if pids and lock.read_text().split('\n')[0].strip() in pids:
                sock = pathlib.Path(os.environ['XDG_RUNTIME_DIR']) / 'hyprune' / lock.parent.name / 'control.sock'
                return sock if sock.is_socket() else None
        return None
    sock = wait(own_socket, 300)
    check('the session started core (its own compositor's control socket)', sock, str(sock.parent.name)[:12] if sock else None)
    control = sock.parent / 'sources.sock'
    panel = sources.Sources(sources.control_path(str(sock)), str(E / 'config/hyprune/sources.json'))
    ask = lambda kind, **f: asyncio.run(panel.handle({'type': kind, **f}))
    status = wait(lambda: (lambda s: s if s.get('ok') and s['status']['connected'] else None)(ask('sources.status')), 60)
    check('the session always starts the helper: idle without sources.json, connected with its data.publish grant',
          status and status['status']['sources'] == {} and not (E / 'config/hyprune/sources.json').exists(),
          status and {'config': pathlib.Path(status['status']['config']).name, 'connected': status['status']['connected']})
    argv = [str(R / 'bin/hyprune-system-gauges'), 'ram']
    test = ask('sources.test', id='gauge-ram', argv=argv)
    check('Test runs the installed hyprune-system-gauges through the helper', test.get('ok') and test['result']['values'].get('label') == 'RAM',
          test.get('result', {}).get('values'))
    saved = ask('sources.save', id='gauge-ram', argv=argv, intervalS=5)
    run = wait(lambda: (lambda s: s['status']['sources'].get('gauge-ram', {}).get('lastRun') if s.get('ok') else None)(ask('sources.status')), 15)
    check('a sources.json created after start is picked up and published (no restart)', saved.get('ok') and run and run['ok'],
          run and {k: run[k] for k in ('ok', 'exitCode')})
    first = run['at'] if run else 0
    again = ask('sources.restartAll')
    time.sleep(2)
    after = wait(lambda: (lambda s: s if s.get('ok') and s['status']['connected'] and
                          s['status']['sources'].get('gauge-ram', {}).get('lastRun', {}).get('at', 0) > first else None)(ask('sources.status')), 20)
    check('Restart helper reconnects with a token renewed through the session and publishes again', again.get('ok') and after,
          after and {'connected': after['status']['connected']})
    helper_log = (E / 'state/hyprune/source-helper.log').read_text() if (E / 'state/hyprune/source-helper.log').exists() else ''
    check('no grant refusals in the helper log', 'no data.publish grant' not in helper_log and 'refused' not in helper_log.lower(),
          helper_log.strip().splitlines()[-3:])
finally:
    session.send_signal(signal.SIGTERM)
    try: session.wait(timeout=20)
    except subprocess.TimeoutExpired: session.kill()
    left = subprocess.run(['pgrep', '-f', str(R / 'libexec/hyprune/source-helper')], capture_output=True, text=True).stdout.split()
    check('stopping the session stops the helper', not left, left)
    (E / 'e2e.json').write_text(json.dumps(results, indent=2))
sys.exit(0 if all(r['ok'] for r in results) else 1)
