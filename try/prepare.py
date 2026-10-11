#!/usr/bin/env python3
"""Render a kit into a try folder: a nested-window session with folder-local paths.

Differences from a normal starter install: the session config opens one window
(HYPRUNE_TRY_SIZE, default 1600x900) instead of taking the monitors; every
Super chord also works with Alt, because the desktop around the window usually
keeps Super for itself; apps whose programs are missing are left out.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from setup import compile_kit, load_kit, write_once  # noqa: E402

WINDOW = '''-- Hyprune try: one nested window in your current Wayland session. Edit freely.
hl.monitor({ output = "", mode = os.getenv("HYPRUNE_TRY_SIZE") or "1600x900", position = "0x0", scale = 1 })
hl.config({ general = { gaps_in = 5, gaps_out = 10, border_size = 2 }, decoration = { rounding = 8 },
            cursor = { no_hardware_cursors = true }, xwayland = { enabled = false },
            misc = { disable_hyprland_logo = true, disable_splash_rendering = true, disable_watchdog_warning = true } })
dofile(os.getenv("XDG_CONFIG_HOME") .. "/hyprune/hyprune.lua")
hl.bind("ALT + SHIFT + Q", hl.dsp.exit())
'''


def alt_binds(lua):
    """Follow each `hl.bind("SUPER + ...` line with the same bind on ALT (same block)."""
    out = []
    for line in lua.splitlines():
        out.append(line)
        if line.lstrip().startswith('hl.bind("SUPER + '):
            out.append(line.replace('hl.bind("SUPER + ', 'hl.bind("ALT + ', 1))
    return '\n'.join(out) + '\n'


def alt_input(keymap):
    """Add an Alt+ twin for Super+ bindings in core's input file (at most three per action)."""
    for mode in keymap.get('modes', {}).values():
        for action, bindings in mode.items():
            twins = [b.replace('Super+', 'Alt+') for b in bindings if 'Super+' in b]
            mode[action] = (bindings + [b for b in twins if b not in bindings])[:max(3, len(bindings))]
    return keymap


def available(app):
    """The app's program, and for kitty the command it runs, are on PATH."""
    argv = app['argv']
    if not shutil.which(argv[0]):
        return False
    if Path(argv[0]).name == 'kitty':
        rest = argv[1:]
        while rest[:1] and rest[0].startswith('--'):
            rest = rest[2:] if '=' not in rest[0] else rest[1:]
        return not rest or bool(shutil.which(rest[0]))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', required=True, type=Path)
    parser.add_argument('--kit', required=True, type=Path)
    parser.add_argument('--plugin', required=True, type=Path)
    parser.add_argument('--input-default', required=True, type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    config, state = folder / 'config/hyprune', folder / 'state/hyprune'
    kit = load_kit(args.kit)
    skipped = [a['title'] for a in kit.get('apps', []) if not available(a)]
    kit['apps'] = [a for a in kit.get('apps', []) if available(a)]
    files = compile_kit(kit, args.plugin.resolve(), [folder / 'data/hyprune/worlds'], {})
    files['hyprune.lua'] = alt_binds(files['hyprune.lua'])
    files['session.lua'] = WINDOW
    files['input.json'] = alt_input(json.loads(args.input_default.read_text()))
    config.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        data = value if isinstance(value, str) else json.dumps(value, indent=2) + '\n'
        if name == 'layout.json':  # window placements are yours after the first run
            write_once(state / name, data.encode())
        else:
            (config / name).write_text(data)
    shutil.copyfile(args.kit, config / 'kit.toml')
    for title in skipped:
        print(f'note: "{title}" is left out: its program is not installed')


if __name__ == '__main__':
    main()
