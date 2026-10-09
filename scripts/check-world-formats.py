#!/usr/bin/env python3
"""Fail if the pinned core cannot load a pinned world's formatVersion.

usage: check-world-formats.py CORE_SOURCE RELEASES_JSON [WORLD_JSON ...]
Reads core's own registry (src/world/Format.hpp `supported{...}`), so pins of
core and worlds/releases.json cannot drift apart unnoticed again."""
import json, pathlib, re, sys

def supported(core):
    header = pathlib.Path(core) / 'src/world/Format.hpp'
    if not header.is_file():
        raise SystemExit(f'{header}: pinned core predates the world format registry (0.1-0.3 only)')
    match = re.search(r'supported\s*\{([^}]*)\}', header.read_text())
    if not match:
        raise SystemExit(f'{header}: cannot find the supported world format list')
    return re.findall(r'"([0-9]+\.[0-9]+)"', match.group(1))

def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    known = supported(argv[1])
    failures, seen = [], []
    for name, release in json.loads(pathlib.Path(argv[2]).read_text()).items():
        version = release.get('formatVersion')
        if not version:
            failures.append(f'{name}: releases.json lacks formatVersion')
        elif version not in known:
            failures.append(f'{name} {release.get("version")}: format {version} not loadable by pinned core ({", ".join(known)})')
        seen.append(f'{name}={version}')
    for path in argv[3:]:
        version = json.loads(pathlib.Path(path).read_text()).get('formatVersion')
        if version not in known:
            failures.append(f'{path}: format {version} not loadable by pinned core ({", ".join(known)})')
        seen.append(f'{pathlib.Path(path).parent.name}={version}')
    if failures:
        raise SystemExit('\n'.join(failures))
    print('PASS world formats', ' '.join(seen), 'within core', ','.join(known))

if __name__ == '__main__':
    main(sys.argv)
