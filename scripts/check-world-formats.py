#!/usr/bin/env python3
"""Fail if a pinned component cannot accept a pinned world's formatVersion.

usage: check-world-formats.py [--core CORE_SRC] [--shell SHELL_SRC]
                              [--validate] RELEASES_JSON [WORLD_JSON ...]

--core reads core's own registry (src/world/Format.hpp `supported{...}`).
--shell imports the shell's launcher catalog (bridge/protocol.py
WORLD_VALIDATORS), the exact table bridge/launch.py rejects unknown formats
with; it needs jsonschema + referencing. With --validate, each WORLD_JSON is
also validated by that catalog. Pins of components and worlds/releases.json
therefore cannot drift apart unnoticed."""
import argparse, importlib.util, json, pathlib, re, sys

def core_formats(core):
    header = pathlib.Path(core) / 'src/world/Format.hpp'
    if not header.is_file():
        raise SystemExit(f'{header}: pinned core predates the world format registry (0.1-0.3 only)')
    match = re.search(r'supported\s*\{([^}]*)\}', header.read_text())
    if not match:
        raise SystemExit(f'{header}: cannot find the supported world format list')
    return re.findall(r'"([0-9]+\.[0-9]+)"', match.group(1))

def shell_catalog(shell):
    bridge = pathlib.Path(shell) / 'bridge'
    if not (bridge / 'protocol.py').is_file():
        raise SystemExit(f'{bridge}/protocol.py: pinned shell has no launcher world catalog')
    sys.path.insert(0, str(bridge))
    spec = importlib.util.spec_from_file_location('hyprune_shell_protocol', bridge / 'protocol.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.WORLD_VALIDATORS

def order(versions):
    return sorted(versions, key=lambda v: tuple(map(int, v.split('.'))))

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--core'); parser.add_argument('--shell')
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('releases'); parser.add_argument('worlds', nargs='*')
    args = parser.parse_args(argv[1:])
    if not args.core and not args.shell:
        parser.error('give --core and/or --shell')
    consumers = {}
    if args.core:
        consumers['core'] = core_formats(args.core)
    catalog = shell_catalog(args.shell) if args.shell else None
    if catalog is not None:
        consumers['shell'] = order(catalog)
    targets = [(name, release.get('version'), release.get('formatVersion'))
               for name, release in json.loads(pathlib.Path(args.releases).read_text()).items()]
    documents = {}
    for path in args.worlds:
        documents[path] = json.loads(pathlib.Path(path).read_text())
        targets.append((path, documents[path].get('version'), documents[path].get('formatVersion')))
    failures = []
    for name, version, fmt in targets:
        if not fmt:
            failures.append(f'{name}: releases.json lacks formatVersion')
            continue
        for consumer, known in consumers.items():
            if fmt not in known:
                failures.append(f'{name} {version}: format {fmt} not accepted by pinned {consumer} ({", ".join(known)})')
    if args.validate and catalog is not None:
        for path, document in documents.items():
            validator = catalog.get(document.get('formatVersion'))
            if validator:
                errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
                if errors:
                    failures.append(f'{path}: shell catalog rejects it at /{"/".join(map(str, errors[0].absolute_path))}: {errors[0].message[:200]}')
    if failures:
        raise SystemExit('\n'.join(failures))
    print('PASS world formats', ' '.join(f'{pathlib.Path(n).parent.name if n.endswith(".json") else n}={f}' for n, _, f in targets),
          'within', '; '.join(f'{c} {",".join(k)}' for c, k in consumers.items()))

if __name__ == '__main__':
    main(sys.argv)
