"""runtime/content.py: library extraction safety (RFC-0004/0011/0015) and content.json records."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
import content  # noqa: E402
import install  # noqa: E402

LIB = 'com.example.street'
URL = f'https://github.com/example/libraries/releases/download/street-v1.2.0/{LIB}-1.2.0.tar.zst'
MANIFEST = {'formatVersion': '0.9', 'id': LIB, 'version': '1.2.0', 'name': 'Street', 'license': 'CC0-1.0',
            'objects': ['bench']}


def member(name, data=b'', kind=tarfile.REGTYPE, mode=0o644, size=None):
    info = tarfile.TarInfo(name)
    info.type, info.mode = kind, mode
    info.size = len(data) if size is None else size
    if kind == tarfile.DIRTYPE:
        info.mode = 0o755
    if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
        info.linkname = '/tmp/escape'
    return info, data


def library_members(manifest=None, root=LIB):
    data = json.dumps(manifest or MANIFEST).encode()
    return [member(root + '/', kind=tarfile.DIRTYPE), member(f'{root}/library.json', data),
            member(f'{root}/objects/bench/object.json', b'{}'), member(f'{root}/LICENSE', b'CC0')]


def pack(path, members, raw=False):
    """Write a .tar.zst; raw writes headers without bodies (sizes are only declared)."""
    path = Path(path)
    tar = path.with_suffix('')
    if raw:
        tar.write_bytes(b''.join(info.tobuf() + data + b'\0' * (-len(data) % 512) for info, data in members) + b'\0' * 1024)
    else:
        with tarfile.open(tar, 'w', format=tarfile.USTAR_FORMAT) as tf:
            for info, data in members:
                tf.addfile(info, io.BytesIO(data) if info.isfile() else None)
    subprocess.run(['zstd', '-q', '-f', '--rm', str(tar), '-o', str(path)], check=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which('zstd'), 'zstd unavailable')
class LibraryExtraction(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp)
        self.root = self.temp / 'data/hyprune/libraries'
        self.archive = self.temp / 'lib.tar.zst'

    def install(self, members, version='1.2.0', raw=False, sha256=None):
        digest = pack(self.archive, members, raw)
        return content.install_library(self.archive, self.root, LIB, version, sha256 or digest)

    def assert_refused(self, members, pattern, **kw):
        with self.assertRaisesRegex(ValueError, pattern):
            self.install(members, **kw)
        # Nothing is left behind: no library directory and no staging directory.
        self.assertEqual(list(self.root.iterdir()) if self.root.exists() else [], [])
        self.assertFalse((self.temp / 'escape').exists())

    def test_valid_library_lands_in_id_at_version(self):
        installed, path, manifest = self.install(library_members())
        self.assertTrue(installed)
        self.assertEqual(path, self.root / f'{LIB}@1.2.0')
        self.assertEqual(manifest['id'], LIB)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [f'{LIB}@1.2.0'])
        lib_json = path / 'library.json'
        self.assertEqual(stat.S_IMODE(lib_json.stat().st_mode), 0o644)
        # Again: the directory is kept as it is.
        self.assertEqual(content.install_library(self.archive, self.root, LIB, '1.2.0',
                                                 content.sha256_file(self.archive))[0], False)

    def test_traversal_absolute_and_unsafe_names(self):
        for name in [f'{LIB}/../../escape', '/tmp/escape', f'{LIB}/./x.json', f'{LIB}//x.json',
                     f'{LIB}/a\\b.json', f'{LIB}/a:b.json', f'{LIB}/a%20.json', f'{LIB}/a?.json', f'{LIB}/a#.json']:
            with self.subTest(name):
                self.assert_refused(library_members() + [member(name, b'{}')], 'Unsafe library archive member')

    def test_links_devices_and_fifos(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE]:
            with self.subTest(kind):
                self.assert_refused(library_members() + [member(f'{LIB}/objects/link', kind=kind)],
                                    'Unsafe library archive member')

    def test_wrong_root_directory(self):
        self.assert_refused(library_members(root='com.example.other'), 'Unsafe library archive member')
        self.assert_refused(library_members() + [member('README.md', b'x')], 'Unsafe library archive member')

    def test_manifest_id_and_version_must_match_the_pin(self):
        self.assert_refused(library_members({**MANIFEST, 'id': 'com.example.other'}), 'ID differs')
        self.assert_refused(library_members({**MANIFEST, 'version': '1.3.0'}), 'version .* differs')
        self.assert_refused(library_members()[:1] + library_members()[2:], 'no readable library.json')

    def test_hash_mismatch_is_refused_before_extraction(self):
        self.assert_refused(library_members(), 'SHA256 mismatch', sha256='0' * 64)

    def test_single_file_over_32_mib_is_refused_before_reading_it(self):
        members = library_members()[:2] + [member(f'{LIB}/objects/bench/huge.bin', size=32 * 1024**2 + 1)]
        self.assert_refused(members, 'size/file limits', raw=True)

    def test_expanded_size_and_file_count_limits(self):
        with patch.dict(content.LIMITS['library'], expanded=100):
            self.assert_refused(library_members() + [member(f'{LIB}/big.bin', b'\1' * 101)], 'size/file limits')
        with patch.dict(content.LIMITS['library'], files=4):
            self.assert_refused(library_members() + [member(f'{LIB}/extra.json', b'{}')], 'size/file limits')
        with patch.dict(content.LIMITS['library'], archive=10):
            self.assert_refused(library_members(), 'archive size limit')
        self.assertEqual((content.LIMITS['library']['files'], content.LIMITS['library']['expanded'],
                          content.LIMITS['library']['file']), (4000, 512 * 1024**2, 32 * 1024**2))

    def test_data_only(self):
        for name, data, mode, pattern in [
                (f'{LIB}/tool.sh', b'echo', 0o644, 'Not a data file'),
                (f'{LIB}/objects/bench/run.json', b'{}', 0o755, 'Executable mode bit'),
                (f'{LIB}/objects/bench/mesh.bin', b'\x7fELF\2\1\1', 0o644, 'signature'),
                (f'{LIB}/notes.txt', b'#!/bin/sh\n', 0o644, 'signature'),
                (f'{LIB}/objects/bench/mesh.bin', b'\0asm\1\0\0\0', 0o644, 'signature')]:
            with self.subTest(name):
                self.assert_refused(library_members() + [member(name, data, mode=mode)], pattern)
        # Licence files without an extension are data.
        installed, path, _ = self.install(library_members() + [member(f'{LIB}/NOTICE', b'n')])
        self.assertTrue(installed and (path / 'NOTICE').is_file())

    def test_duplicate_members(self):
        self.assert_refused(library_members() + [member(f'{LIB}/LICENSE', b'again')], 'Duplicate')

    def test_corrupt_archive(self):
        self.archive.write_bytes(b'not zstd')
        with self.assertRaises(ValueError):
            content.install_library(self.archive, self.root, LIB, '1.2.0', content.sha256_file(self.archive))

    def test_unpack_for_build_systems(self):
        pack(self.archive, library_members())
        out = self.temp / 'out/share/hyprune/libraries'
        subprocess.run([sys.executable, '-I', str(ROOT / 'runtime/content.py'), 'unpack-library', '--archive',
                        str(self.archive), '--id', LIB, '--version', '1.2.0', '--out', str(out)], check=True)
        self.assertEqual([p.name for p in out.iterdir()], [f'{LIB}@1.2.0'])
        bad = subprocess.run([sys.executable, '-I', str(ROOT / 'runtime/content.py'), 'unpack-library', '--archive',
                              str(self.archive), '--id', LIB, '--version', '9.9.9', '--out', str(self.temp / 'bad')],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn('differs from the pinned 9.9.9', bad.stderr)

    def test_worlds_keep_their_own_limits(self):
        world = [member('com.hyprune.test/', kind=tarfile.DIRTYPE),
                 member('com.hyprune.test/world.json', b'{"id":"com.hyprune.test"}'),
                 member('com.hyprune.test/run.sh', b'#!/bin/sh', mode=0o755)]
        pack(self.archive, world)
        stage = self.temp / 'stage'; stage.mkdir()
        # Worlds are not checked for data-only files here (core's loader and world-check decide).
        self.assertEqual(install.extract_world(self.archive, stage, 'com.hyprune.test')['id'], 'com.hyprune.test')
        self.assertEqual(stat.S_IMODE((stage / 'com.hyprune.test/run.sh').stat().st_mode), 0o644)


class Records(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp)
        self.state = self.temp / 'state/hyprune'
        self.path = self.state / 'content.json'

    def test_release_tag_comes_from_the_pinned_url(self):
        self.assertEqual(content.release_tag(URL), 'street-v1.2.0')
        self.assertEqual(content.release_tag('https://github.com/hyprune/worlds/releases/download/'
                                             'hyprune-starter-v0.1.0/com.hyprune.starter-0.1.0.tar.zst'),
                         'hyprune-starter-v0.1.0')
        for bad in ['https://example.com/street.tar.zst', 'https://github.com/o/r/releases/download/a/b/c.tar.zst',
                    'https://github.com/o/r/releases/download//c.tar.zst']:
            with self.subTest(bad), self.assertRaises(ValueError):
                content.release_tag(bad)

    def test_official_record_shape(self):
        record = content.official_record('library', LIB, '1.2.0', URL, 'a' * 64, 'CC0-1.0', '2026-10-12T00:00:00Z')
        self.assertEqual(record, {
            'id': LIB, 'type': 'library', 'source': 'official', 'pinned': False,
            'current': {'tag': 'street-v1.2.0', 'version': '1.2.0', 'sha256': 'a' * 64, 'digest': None,
                        'license': 'CC0-1.0', 'url': URL, 'installed': '2026-10-12T00:00:00Z'},
            'previous': None, 'pending': None})
        self.assertRegex(content.official_record('world', 'com.a.b', '1.0.0', URL, 'b' * 64)['current']['installed'],
                         r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')

    def test_writer_is_atomic_private_and_merges(self):
        other = {'id': 'io.github.ada.tidepool', 'type': 'world', 'source': 'community', 'pinned': True,
                 'current': {'tag': 'v1.0.0', 'version': '1.0.0', 'sha256': 'c' * 64}, 'previous': None, 'pending': None}
        content.write_records(self.path, {'version': 1, 'installs': [other]})
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        doc = content.load_records(self.path)
        first = content.official_record('library', LIB, '1.2.0', URL, 'a' * 64)
        self.assertEqual(content.upsert_record(doc, first), 'added')
        self.assertEqual(content.upsert_record(doc, dict(first)), 'kept')
        changed = content.official_record('library', LIB, '1.2.0', URL, 'd' * 64)
        self.assertEqual(content.upsert_record(doc, changed), 'replaced')
        content.write_records(self.path, doc)
        installs = json.loads(self.path.read_text())['installs']
        self.assertEqual([r['id'] for r in installs], ['io.github.ada.tidepool', LIB])
        self.assertEqual(installs[0], other)
        self.assertEqual(installs[1]['current']['sha256'], 'd' * 64)
        self.assertEqual([p.name for p in self.state.iterdir()], ['content.json'])
        self.assertFalse(content.remove_record(doc, LIB, 'library', 'a' * 64))
        self.assertTrue(content.remove_record(doc, LIB, 'library', 'd' * 64))

    def test_unknown_content_json_is_never_clobbered(self):
        self.state.mkdir(parents=True)
        for text in ['{"version": 2, "installs": []}', '[]', '{"version": 1}']:
            self.path.write_text(text)
            with self.subTest(text), self.assertRaises(ValueError):
                content.record_official_world(self.state, dict(id='com.a.b', version='1.0.0', url=URL, sha256='a' * 64), {})
            self.assertEqual(self.path.read_text(), text)
        self.path.write_text('{not json')
        with self.assertRaises(ValueError):
            content.load_records(self.path)

    def test_lock_takes_over_a_dead_owner_and_waits_for_a_live_one(self):
        self.state.mkdir(parents=True)
        lock = self.state / 'content.lock'
        dead = subprocess.Popen([sys.executable, '-c', 'pass']); dead.wait()
        lock.write_text(f'{dead.pid}\n')
        with content.ContentLock(self.state):
            self.assertEqual(lock.read_text().strip(), str(os.getpid()))
        self.assertFalse(lock.exists())
        lock.write_text(f'{os.getppid()}\n')
        with self.assertRaisesRegex(RuntimeError, 'held by process'):
            with content.ContentLock(self.state, wait=0.3):
                pass
        self.assertEqual(lock.read_text().strip(), str(os.getppid()))

    def test_world_record(self):
        release = dict(id='com.hyprune.lumen-reach', version='0.10.3', sha256='e' * 64,
                       url='https://github.com/hyprune/worlds/releases/download/lumen-reach-v0.10.3/'
                           'com.hyprune.lumen-reach-0.10.3.tar.zst')
        content.record_official_world(self.state, release, {'license': 'CC-BY-4.0'})
        record, = json.loads(self.path.read_text())['installs']
        self.assertEqual((record['type'], record['source'], record['current']['tag'], record['current']['license']),
                         ('world', 'official', 'lumen-reach-v0.10.3', 'CC-BY-4.0'))


@unittest.skipUnless(shutil.which('zstd'), 'zstd unavailable')
class OfficialLibraries(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp)
        self.root = self.temp / 'data/hyprune/libraries'
        self.state = self.temp / 'state/hyprune'
        self.archive = self.temp / 'release.tar.zst'
        self.pin = dict(id=LIB, version='1.2.0', url=URL, sha256=pack(self.archive, library_members()),
                        formatVersion='0.9', published=True)

    def fetch(self, url, target):
        self.assertEqual(url, URL)
        shutil.copyfile(self.archive, target)

    def test_installer_records_and_uninstall_removes_what_it_added(self):
        receipt = {}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            install.install_libraries([self.pin], self.root, self.state, receipt, fetch=self.fetch)
            install.install_libraries([self.pin], self.root, self.state, receipt, fetch=self.fail_fetch)
        self.assertIn('installed', out.getvalue())
        self.assertIn('already installed', out.getvalue())
        target = self.root / f'{LIB}@1.2.0'
        self.assertEqual(receipt, {str(target): self.pin['sha256']})
        record, = json.loads((self.state / 'content.json').read_text())['installs']
        self.assertEqual((record['id'], record['source'], record['current']['tag'], record['current']['license']),
                         (LIB, 'official', 'street-v1.2.0', 'CC0-1.0'))
        prefix = self.temp / 'install'; prefix.mkdir()
        (prefix / 'receipt.json').write_text(json.dumps(dict(libraries=receipt)))
        with contextlib.redirect_stdout(io.StringIO()):
            install.uninstall(argparse.Namespace(dry_run=False), prefix, self.temp / 'config', self.state)
        self.assertFalse(target.exists())
        self.assertEqual(json.loads((self.state / 'content.json').read_text())['installs'], [])
        self.assertFalse(prefix.exists())

    def test_uninstall_preserves_a_library_the_user_updated_since(self):
        receipt = {}
        with contextlib.redirect_stdout(io.StringIO()):
            install.install_libraries([self.pin], self.root, self.state, receipt, fetch=self.fetch)
        doc = content.load_records(self.state / 'content.json')
        doc['installs'][0]['current'].update(version='1.3.0', sha256='f' * 64, tag='street-v1.3.0')
        content.write_records(self.state / 'content.json', doc)
        prefix = self.temp / 'install'; prefix.mkdir()
        (prefix / 'receipt.json').write_text(json.dumps(dict(libraries=receipt)))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            install.uninstall(argparse.Namespace(dry_run=False), prefix, self.temp / 'config', self.state)
        self.assertTrue((self.root / f'{LIB}@1.2.0').is_dir())
        self.assertIn('Preserving library', out.getvalue())
        self.assertEqual(len(content.load_records(self.state / 'content.json')['installs']), 1)

    def test_another_recorded_version_is_left_to_the_content_pipeline(self):
        newer = content.official_record('library', LIB, '1.3.0', URL.replace('1.2.0', '1.3.0'), 'f' * 64)
        content.write_records(self.state / 'content.json', {'version': 1, 'installs': [newer]})
        receipt = {}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            install.install_libraries([self.pin], self.root, self.state, receipt, fetch=self.fail_fetch)
        self.assertIn('another version', out.getvalue())
        self.assertEqual(receipt, {})
        self.assertFalse(self.root.exists())

    def test_existing_unrecorded_directory_is_kept_and_not_claimed(self):
        (self.root / f'{LIB}@1.2.0').mkdir(parents=True)
        result = content.install_official_library(self.pin, self.archive, self.root, self.state)
        self.assertEqual(result, 'present')
        self.assertFalse((self.state / 'content.json').exists())

    def test_command_line_for_try(self):
        args = ['install-library', '--archive', str(self.archive), '--sha256', self.pin['sha256'], '--id', LIB,
                '--version', '1.2.0', '--url', URL, '--root', str(self.root), '--state', str(self.state)]
        run = lambda: subprocess.run([sys.executable, '-I', str(ROOT / 'runtime/content.py'), *args],
                                     capture_output=True, text=True)
        self.assertEqual(run().stdout, f'installed {LIB}@1.2.0\n')
        self.assertEqual(run().stdout, f'present {LIB}@1.2.0\n')
        args[4] = '0' * 64
        shutil.rmtree(self.root)
        failed = run()
        self.assertEqual((failed.returncode, failed.stdout), (1, ''))
        self.assertIn('SHA256 mismatch', failed.stderr)

    def fail_fetch(self, url, target):
        raise AssertionError('nothing should be downloaded')


if __name__ == '__main__':
    unittest.main()


class LockedWorldUnpack(unittest.TestCase):
    """content.py unpack-world (Nix content locks): the world root, the locked version, the rules."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp)
        self.archive = self.temp / 'world.tar.zst'

    def world(self, version='1.2.0', extra=()):
        manifest = json.dumps({'formatVersion': '0.9', 'id': 'org.example.harbour', 'version': version, 'name': 'Harbour'}).encode()
        return [member('org.example.harbour/', kind=tarfile.DIRTYPE, mode=0o755), member('org.example.harbour/world.json', manifest), *extra]

    def test_unpacks_into_the_world_root(self):
        pack(self.archive, self.world())
        content.main(['unpack-world', '--archive', str(self.archive), '--id', 'org.example.harbour', '--version', '1.2.0', '--out', str(self.temp / 'out')])
        self.assertTrue((self.temp / 'out/org.example.harbour/world.json').is_file())
        self.assertEqual([p.name for p in (self.temp / 'out').iterdir()], ['org.example.harbour'])

    def test_the_locked_version_must_match(self):
        pack(self.archive, self.world('1.1.0'))
        with self.assertRaisesRegex(ValueError, 'version 1.1.0, the lock 1.2.0'):
            content.unpack_world(self.archive, 'org.example.harbour', '1.2.0', self.temp / 'out')
        self.assertEqual(list((self.temp / 'out').iterdir()), [])

    def test_unsafe_members_are_refused(self):
        pack(self.archive, self.world(extra=[member('org.example.harbour/../escape', b'x')]))
        with self.assertRaises(ValueError):
            content.unpack_world(self.archive, 'org.example.harbour', '1.2.0', self.temp / 'out')
        self.assertFalse((self.temp / 'escape').exists())
