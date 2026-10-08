#!/usr/bin/env python3
"""Compile data-only kits into core's existing config contracts. No compositor IPC."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def merge(base, patch):
    result = copy.deepcopy(base)
    for key, value in patch.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else value
    return result


def lua(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value, allow_nan=False)
    if isinstance(value, str):
        # JSON unicode escapes are not Lua escapes; emit UTF-8 and Lua controls.
        return '"' + ''.join({'"': '\\"', '\\': '\\\\', '\n': '\\n', '\r': '\\r', '\t': '\\t'}.get(c, f'\\{ord(c):03d}' if ord(c) < 32 else c) for c in value) + '"'
    if isinstance(value, list):
        return "{" + ", ".join(map(lua, value)) + "}"
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{lua(k)}] = {lua(v)}" for k, v in value.items()) + "}"
    raise ValueError(f"Unsupported Lua value: {type(value).__name__}")


def load_kit(path):
    with Path(path).open('rb') as stream:
        kit = tomllib.load(stream)
    if kit['version'] != 1 or kit['keymap'] != 'core-default-v2':
        raise ValueError('Unsupported kit/keymap version')
    if kit['shell_theme'] != 'hyprune-dark':
        raise ValueError('Shell currently supports only its built-in hyprune-dark theme')
    homes = kit['homes']
    ids = [h['workspace'] for h in homes]
    if len(set(ids)) != len(ids) or not all(isinstance(i, int) and i > 0 for i in ids) or len(ids) > 32:
        raise ValueError('Workspace IDs must be distinct positive integers, at most 32')
    areas = [(h['world'], h['area']) for h in homes if 'area' in h]
    if len(set(areas)) != len(areas) or kit['initial_workspace'] not in ids:
        raise ValueError('Duplicate area or unmapped initial workspace')
    for app in kit.get('apps', []):
        home = next((h for h in homes if h['workspace'] == app['workspace']), None)
        if not home or ('mount' in app and 'area' not in home):
            raise ValueError('Mounted apps need a typed home')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', app['class']):
            raise ValueError('Starter app class must be a literal identifier')
        if not app['argv'] or not all(isinstance(s, str) and '\x00' not in s for s in app['argv']):
            raise ValueError('Apps need an argument array')
    return kit


def compile_kit(kit, plugin, world_dirs, settings, external_plugin=False):
    homes = kit['homes']
    locations = [dict(id=h['workspace'], label=h['label'], worldId=h['world'], spawnId=h['spawn']) for h in homes]
    bindings = [dict(id=h['workspace'], worldId=h['world'], areaId=h['area']) for h in homes if 'area' in h]
    placements = []
    for app in kit.get('apps', []):
        if 'mount' not in app:
            continue
        home = next(h for h in homes if h['workspace'] == app['workspace'])
        placements.append(dict(worldId=home['world'], areaId=home['area'], anchorId=app['mount'],
                               rule=dict(appClass=app['class'], title=app['title'])))
    config = merge(kit.get('settings', {}), settings)
    lines = ['-- User-owned Hyprune include; generated once. Edit freely.']
    if not external_plugin:
        lines.append(f'hl.plugin.load(os.getenv("HYPRUNE_PLUGIN") or {lua(str(plugin))})')
    lines += ['-- Hyprland 0.56.2 reloads Lua after newly registered plugins load.',
              'if hl.plugin.hyprune then', f'  hl.plugin.hyprune.config({lua(config)})',
              '  hl.bind("SUPER + F12", hl.plugin.hyprune.toggle)', 'end',
              'hl.bind("SUPER + RETURN", hl.dsp.exec_cmd("kitty"))']
    lines.append(f'hl.workspace_rule({{ workspace = {lua(str(kit["initial_workspace"]))}, default = true }})')
    for h in homes:
        lines.append(f'hl.bind("SUPER + {h["workspace"] % 10}", hl.dsp.focus({{ workspace = {lua(str(h["workspace"]))} }}))')
    for app in kit.get('apps', []):
        lines.append('hl.window_rule(' + lua(dict(name='hyprune-' + app['class'],
                     match={'class': '^' + re.escape(app['class']) + '$'}, workspace=str(app['workspace']))) + ')')
    # The supervisor explicitly launches shell/apps once, with an inherited token.
    session = dict(world_dirs=[str(p) for p in world_dirs], initial_workspace=kit['initial_workspace'],
                   apps=kit.get('apps', []), shell=['hyprune-shell'], kit=kit['name'])
    standalone = '''-- Standalone starter session. Your normal Hyprland config is separate.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })
hl.config({ general = { gaps_in = 5, gaps_out = 10, border_size = 2 },
            decoration = { rounding = 8 }, misc = { disable_hyprland_logo = true } })
local config = os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")
dofile(config .. "/hyprune/hyprune.lua")
'''
    return {'locations.json': locations, 'layout.json': dict(version=1, bindings=bindings, placements=placements),
            'session.json': session, 'hyprune.lua': '\n'.join(lines) + '\n', 'session.lua': standalone}


def render(args):
    kit = load_kit(args.kit)
    settings = json.loads(Path(args.settings).read_text()) if args.settings else {}
    files = compile_kit(kit, args.plugin, args.world_dir, settings, args.external_plugin)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        (output / name).write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + '\n')
    shutil.copyfile(args.input_default, output / 'input.json')
    shutil.copyfile(args.kit, output / 'kit.toml')


def write_once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    return True


def init(seed):
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'hyprune'
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hyprune'
    for path in Path(seed).iterdir():
        if path.is_file():
            target = (state if path.name == 'layout.json' else config) / path.name
            write_once(target, path.read_bytes())
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ['render', 'install']:
        p = sub.add_parser(command)
        p.add_argument('--kit', default=str(ROOT / 'kits/minimal/kit.toml'))
        p.add_argument('--plugin', default=os.environ.get('HYPRUNE_PLUGIN'))
        p.add_argument('--input-default', default=os.environ.get('HYPRUNE_INPUT_DEFAULT'))
        p.add_argument('--world-dir', action='append', default=[])
        p.add_argument('--settings')
        p.add_argument('--external-plugin', action='store_true')
        p.add_argument('--output', required=command == 'render')
    p = sub.add_parser('init'); p.add_argument('--seed', required=True)
    args = parser.parse_args()
    if args.command == 'init':
        init(args.seed)
    else:
        if not args.world_dir and os.environ.get('HYPRUNE_DEFAULT_WORLD_DIR'):
            args.world_dir = [os.environ['HYPRUNE_DEFAULT_WORLD_DIR']]
        if not args.plugin or not args.input_default:
            parser.error('--plugin and --input-default are required')
        if args.command == 'render':
            render(args)
        else:
            with tempfile.TemporaryDirectory() as temp:
                args.output = temp
                render(args)
                init(temp)


if __name__ == '__main__':
    main()
