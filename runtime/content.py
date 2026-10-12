#!/usr/bin/env python3
"""Official content: safe package extraction and install records (RFC-0004, RFC-0011, RFC-0015).

Shared by the installer, try.sh and the Nix library derivations; standard library only.

    content.py install-library --archive A --sha256 H --id ID --version V --url URL --root DIR --state DIR
    content.py unpack-library --archive A --id ID --version V --out DIR
    content.py record-world --state DIR --id ID --version V --url URL --sha256 H --manifest world.json
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse

# RFC-0015 "Archive" limits; zstd windows are at most 128 MiB for both.
LIMITS = {
    'world': dict(manifest='world.json', archive=512 * 1024**2, expanded=1024**3, file=128 * 1024**2, files=10000),
    'library': dict(manifest='library.json', archive=256 * 1024**2, expanded=512 * 1024**2, file=32 * 1024**2, files=4000),
}
# Data only (RFC-0015): file types a library may carry, and signatures no file may start with.
DATA_SUFFIXES = {'.json', '.glb', '.gltf', '.bin', '.png', '.jpg', '.jpeg', '.ktx2', '.svg', '.ogg', '.wav', '.md', '.txt'}
DATA_NAMES = {'LICENSE', 'NOTICE', 'COPYING', 'ATTRIBUTION'}
EXECUTABLE_SIGNATURES = (b'\x7fELF', b'MZ', b'#!', b'\0asm', b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf',
                         b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe')
ID = re.compile(r'^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$')
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?$')
TAG = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
LOCK_WAIT = 30


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def data_only(name, mode, head):
    """Raise unless a library file is data (RFC-0015): known type, no executable bit or signature."""
    base = name.rsplit('/', 1)[-1]
    stem, dot, suffix = base.rpartition('.')
    if not ((dot and '.' + suffix.lower() in DATA_SUFFIXES) or (stem if dot else base) in DATA_NAMES):
        raise ValueError(f'Not a data file: {name}')
    if mode & 0o111:
        raise ValueError(f'Executable mode bit: {name}')
    if head.startswith(EXECUTABLE_SIGNATURES):
        raise ValueError(f'Executable or script signature: {name}')


def extract_package(archive, destination, package_id, kind='world', version=None):
    """Unpack a verified .tar.zst into destination/<package_id>/; the hash check is the caller's job.

    One root directory named exactly package_id; regular files and directories only (no links,
    devices, absolute paths, '..', empty or '.' segments, backslashes, %, ?, #, :); the kind's
    file count, expanded and per-file limits; libraries are data only. The manifest names the
    same id (and version, for libraries)."""
    limits = LIMITS[kind]
    destination = Path(destination)
    if Path(archive).stat().st_size > limits['archive']:
        raise ValueError(f'{kind.capitalize()} archive exceeds the RFC-0015 archive size limit')
    total = count = 0
    with subprocess.Popen(['zstd', '-dc', '--memory=128MiB', str(archive)], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as decoder:
        try:
            with tarfile.open(fileobj=decoder.stdout, mode='r|') as stream:
                for member in stream:
                    parts = Path(member.name).parts
                    if (not parts or member.name.startswith('/') or '..' in parts or
                            any(c in member.name for c in ['\\', '%', '?', '#', ':']) or
                            any(p in ['', '.'] for p in member.name.rstrip('/').split('/')) or
                            parts[0] != package_id or not (member.isdir() or member.isfile())):
                        raise ValueError(f'Unsafe {kind} archive member: {member.name}')
                    total += member.size
                    count += 1
                    if total > limits['expanded'] or member.size > limits['file'] or count > limits['files']:
                        raise ValueError(f'{kind.capitalize()} archive exceeds RFC-0004 size/file limits')
                    target = destination.joinpath(*parts)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with stream.extractfile(member) as source:
                        head = source.read(8)
                        if kind == 'library':
                            data_only(member.name, member.mode, head)
                        try:
                            out = target.open('xb')
                        except FileExistsError:
                            raise ValueError(f'Duplicate {kind} archive member: {member.name}') from None
                        with out:
                            out.write(head)
                            shutil.copyfileobj(source, out)
                    target.chmod(0o644)
        except tarfile.TarError as error:
            decoder.kill(); decoder.wait()
            raise ValueError(f'Corrupt {kind} archive: {error}') from None
        except BaseException:
            decoder.kill(); decoder.wait()
            raise
        if decoder.wait() != 0:
            raise ValueError('zstd failed (corrupt archive or a window over 128 MiB)')
    root = destination / package_id
    try:
        manifest = json.loads((root / limits['manifest']).read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f'{kind.capitalize()} archive has no readable {limits["manifest"]}: {error}') from None
    if not isinstance(manifest, dict) or manifest.get('id') != package_id:
        raise ValueError(f'Archive manifest ID differs from selected {kind}')
    if version is not None and manifest.get('version') != version:
        raise ValueError(f'Archive manifest version {manifest.get("version")!r} differs from the pinned {version}')
    return manifest


def install_library(archive, root, library_id, version, sha256):
    """Verify, extract and move one library to root/<id>@<version>/.

    Returns (installed, path, manifest); an existing directory is kept as it is (installed False)."""
    if not ID.match(library_id) or not VERSION.match(version):
        raise ValueError(f'Not a library id@version: {library_id}@{version}')
    if sha256_file(archive) != sha256:
        raise ValueError(f'{library_id}@{version}: archive SHA256 mismatch')
    root = Path(root)
    target = root / f'{library_id}@{version}'
    if target.exists() or target.is_symlink():
        return False, target, None
    root.mkdir(parents=True, exist_ok=True)
    # Core ignores dot directories in the library root, so a half-written stage is never listed.
    stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=root))
    try:
        manifest = extract_package(archive, stage, library_id, 'library', version)
        os.rename(stage / library_id, target)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return True, target, manifest


def unpack_library(archive, library_id, version, out):
    """For build systems (Nix): extract into out/<id>@<version>/ with the same rules, no install records."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=out))
    try:
        extract_package(archive, stage, library_id, 'library', version)
        os.rename(stage / library_id, out / f'{library_id}@{version}')
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# --- install records: $XDG_STATE_HOME/hyprune/content.json (RFC-0015 "Where state lives") ------

def data_home():
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')


def state_home():
    return Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')


def release_tag(url):
    """The tag of a pinned GitHub Release asset URL: .../releases/download/<tag>/<asset>."""
    path = urllib.parse.urlsplit(url).path.split('/')
    if len(path) >= 4 and path[-4:-2] == ['releases', 'download'] and TAG.match(path[-2]) and path[-1]:
        return path[-2]
    raise ValueError(f'Not a release asset URL: {url}')


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def official_record(kind, package_id, version, url, sha256, license=None, installed=None):
    return {'id': package_id, 'type': kind, 'source': 'official', 'pinned': False,
            'current': {'tag': release_tag(url), 'version': version, 'sha256': sha256, 'digest': None,
                        'license': license if isinstance(license, str) else None, 'url': url,
                        'installed': installed or now()},
            'previous': None, 'pending': None}


class ContentLock:
    """$XDG_STATE_HOME/hyprune/content.lock, created with O_EXCL and holding the owner's pid.

    A lock whose pid is gone is stale and taken over; core and the CLI take the same lock."""

    def __init__(self, state, wait=LOCK_WAIT):
        self.path = Path(state) / 'content.lock'
        self.wait = wait

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.wait
        while True:
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                owner = self.owner()
                if owner is None or not alive(owner):
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() > deadline:
                    raise RuntimeError(f'{self.path} is held by process {owner}; try again when it finishes')
                time.sleep(0.2)
                continue
            with os.fdopen(fd, 'w') as stream:
                stream.write(f'{os.getpid()}\n')
            return self

    def owner(self):
        try:
            text = self.path.read_text().strip()
            age = time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return 0  # released meanwhile: retry at once
        if text.isdigit():
            return int(text)
        # Created but not yet written: give the writer a moment before calling it stale.
        return os.getpid() if age < 5 else None

    def __exit__(self, *exc):
        try:
            if self.path.read_text().strip() == str(os.getpid()):
                self.path.unlink()
        except FileNotFoundError:
            pass


def alive(pid):
    if pid in (0, os.getpid()):
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def load_records(path):
    path = Path(path)
    if not path.exists():
        return {'version': 1, 'installs': []}
    doc = json.loads(path.read_text())
    if not isinstance(doc, dict) or doc.get('version') != 1 or not isinstance(doc.get('installs'), list):
        raise ValueError(f'{path}: not a version 1 content.json; leaving it untouched')
    return doc


def write_records(path, doc):
    """Atomic replace, mode 0600."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.content-', suffix='.json')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(doc, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def find_record(doc, package_id, kind):
    return next((r for r in doc['installs'] if isinstance(r, dict) and r.get('id') == package_id and r.get('type') == kind), None)


def upsert_record(doc, record):
    """Add record, or replace one of the same id and type that describes other content.

    Returns 'added', 'kept' (same sha256 already recorded) or 'replaced'. Other installs are never touched."""
    existing = find_record(doc, record['id'], record['type'])
    if existing is None:
        doc['installs'].append(record)
        return 'added'
    if (existing.get('current') or {}).get('sha256') == record['current']['sha256']:
        return 'kept'
    doc['installs'][doc['installs'].index(existing)] = record
    return 'replaced'


def remove_record(doc, package_id, kind, sha256):
    """Drop the record only while it still describes the install we made (same current sha256)."""
    existing = find_record(doc, package_id, kind)
    if existing is None or (existing.get('current') or {}).get('sha256') != sha256:
        return False
    doc['installs'].remove(existing)
    return True


def library_status(pin, root, state):
    """Before downloading: 'install', 'present' (root/<id>@<version>/ exists) or 'skipped'
    (content.json records another version of this id, so the user's content pipeline owns it)."""
    existing = find_record(load_records(Path(state) / 'content.json'), pin['id'], 'library')
    if existing and (existing.get('current') or {}).get('version') != pin['version']:
        return 'skipped'
    target = Path(root) / f"{pin['id']}@{pin['version']}"
    return 'present' if target.exists() or target.is_symlink() else 'install'


def install_official_library(pin, archive, root, state):
    """One published pin from libraries/releases.json, under the content lock.

    Returns 'installed', 'present' (the directory exists; recorded only if already ours) or
    'skipped' (content.json records another version of this id: the CLI manages it now)."""
    state = Path(state)
    with ContentLock(state):
        doc = load_records(state / 'content.json')
        existing = find_record(doc, pin['id'], 'library')
        if existing and (existing.get('current') or {}).get('version') != pin['version']:
            return 'skipped'
        installed, _, manifest = install_library(archive, root, pin['id'], pin['version'], pin['sha256'])
        if installed:
            upsert_record(doc, official_record('library', pin['id'], pin['version'], pin['url'], pin['sha256'],
                                               (manifest or {}).get('license')))
            write_records(state / 'content.json', doc)
        return 'installed' if installed else 'present'


def record_official_world(state, release, manifest):
    """Record a kit world the caller just installed into the world root."""
    state = Path(state)
    with ContentLock(state):
        doc = load_records(state / 'content.json')
        upsert_record(doc, official_record('world', release['id'], release['version'], release['url'],
                                           release['sha256'], manifest.get('license')))
        write_records(state / 'content.json', doc)


def remove_official_library(path, sha256, state):
    """Uninstall: delete root/<id>@<version>/ and its record, if the record is still our install."""
    path = Path(path)
    library_id, _, version = path.name.partition('@')
    state = Path(state)
    with ContentLock(state):
        doc = load_records(state / 'content.json')
        existing = find_record(doc, library_id, 'library')
        current = (existing or {}).get('current') or {}
        if current.get('sha256') != sha256 or current.get('version') != version:
            return False
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        remove_record(doc, library_id, 'library', sha256)
        write_records(state / 'content.json', doc)
        return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    lib = sub.add_parser('install-library', help='verify, extract and record one pinned library')
    unpack = sub.add_parser('unpack-library', help='extract a library into OUT/<id>@<version>/ (no records)')
    world = sub.add_parser('record-world', help='record an installed official world in content.json')
    for p in [lib, unpack]:
        p.add_argument('--archive', required=True, type=Path)
        p.add_argument('--id', required=True)
        p.add_argument('--version', required=True)
    lib.add_argument('--sha256', required=True)
    lib.add_argument('--url', required=True)
    lib.add_argument('--root', required=True, type=Path)
    lib.add_argument('--state', required=True, type=Path)
    unpack.add_argument('--out', required=True, type=Path)
    for name in ['--state', '--id', '--version', '--url', '--sha256', '--manifest']:
        world.add_argument(name, required=True)
    args = parser.parse_args(argv)
    if args.command == 'install-library':
        pin = dict(id=args.id, version=args.version, url=args.url, sha256=args.sha256)
        result = install_official_library(pin, args.archive, args.root, args.state)
        print(f'{result} {args.id}@{args.version}')
    elif args.command == 'unpack-library':
        unpack_library(args.archive, args.id, args.version, args.out)
    else:
        release = dict(id=args.id, version=args.version, url=args.url, sha256=args.sha256)
        record_official_world(args.state, release, json.loads(Path(args.manifest).read_text()))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f'hyprune-content: {error}', file=sys.stderr)
        raise SystemExit(1)
