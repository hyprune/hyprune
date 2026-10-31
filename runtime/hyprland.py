"""Which Hyprland a Hyprune core is built for, and what to say when the installed one differs.

The plugin is ABI-locked to the Hyprland headers it was built against. Core supports the
current Hyprland release and the one before; component-pins.json lists the releases the
pinned core builds for (core.hyprland), and every core build records its own release.
"""
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DOCS = 'https://hyprune.com/hyprland-versions/'


def supported(root=ROOT):
    """The Hyprland releases ("0.56", "0.57") the pinned core builds for."""
    pins = Path(root) / 'component-pins.json'
    core = json.loads(pins.read_text()).get('core', {}) if pins.is_file() else {}
    return core.get('hyprland', ['0.56'])


def release(version):
    """'0.57' from '0.57.0' or 'v0.57.0'."""
    return '.'.join(str(version or '').lstrip('v').split('.')[:2])


def binary_version(binary='Hyprland'):
    """'0.57.0' from `Hyprland --version`, or None."""
    try:
        # Hyprland 0.56 prints nothing but an error without XDG_RUNTIME_DIR.
        env = {**os.environ, 'XDG_RUNTIME_DIR': os.environ.get('XDG_RUNTIME_DIR') or '/tmp'}
        out = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=10, env=env).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r'^Hyprland (\d+\.\d+\.\d+)', out, re.M)
    return match.group(1) if match else None


def core_built_for(plugin):
    """The Hyprland release a core build is for: its release archive's abi.json, the
    hyprland-version an installed or packaged core carries, or a build tree's. None if the
    core predates the record."""
    plugin = Path(plugin)
    for record in (plugin.parent.parent / 'abi.json', plugin.parent.parent / 'share/hyprune/hyprland-version',
                   plugin.parent / 'hyprland-version'):
        if record.is_file():
            text = record.read_text().strip()
            return json.loads(text)['tag'].lstrip('v') if record.suffix == '.json' else text
    return None


def configured_plugin(config_dir):
    """The plugin a starter config loads: HYPRUNE_PLUGIN wins at run time, else hyprune.lua's path."""
    lua = Path(config_dir) / 'hyprune.lua'
    match = re.search(r'hl\.plugin\.load\(os\.getenv\("HYPRUNE_PLUGIN"\) or "([^"]+)"\)', lua.read_text()) if lua.is_file() else None
    return match.group(1) if match else None


def unsupported(installed, releases):
    """The message for a Hyprland release this core does not build for, or None."""
    if installed and release(installed) in releases:
        return None
    names = ', '.join(r + '.x' for r in releases)
    return f'Hyprland {installed or "(not found)"} is not supported: this Hyprune release supports Hyprland {names} ({DOCS})'


def mismatch(installed, built):
    """The message when the installed Hyprland is not the one this core was built for, or None."""
    if not built or installed == built:
        return None
    return (f'This Hyprune core is built for Hyprland {built}, but Hyprland {installed or "(not found)"} is installed: '
            f'the plugin only loads into the release it was built for. Get the core build for Hyprland '
            f'{installed} (rerun try or the installer), or install Hyprland {built} ({DOCS})')
