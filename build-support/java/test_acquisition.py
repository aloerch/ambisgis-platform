"""Custody verification must detect tampering without following unsafe paths."""
import hashlib
import tempfile
import subprocess
import unittest
from pathlib import Path
from acquisition import entries, verify, restore_owned, local_git


class AuditCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = b'retained evidence\n'
        (self.root / 'source.tar').write_bytes(self.data)
        self.manifest = {'schema_version': 1, 'files': [
            {'path': 'source.tar', 'size': len(self.data),
             'sha256': hashlib.sha256(self.data).hexdigest()}]}

    def test_valid_custody_does_not_imply_build_ready(self):
        self.assertFalse(verify(self.root, self.manifest)['build_ready'])

    def test_same_size_tampering_fails(self):
        (self.root / 'source.tar').write_bytes(b'x' * len(self.data))
        with self.assertRaisesRegex(ValueError, 'changed'):
            verify(self.root, self.manifest)

    def test_missing_input_fails(self):
        (self.root / 'source.tar').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            verify(self.root, self.manifest)

    def test_path_escape_and_aliases_fail(self):
        for name in ['../outside', '/absolute', 'a/../source.tar', './source.tar', 'a//b', 'a\\b']:
            with self.subTest(name=name):
                self.manifest['files'][0]['path'] = name
                with self.assertRaisesRegex(ValueError, 'path'):
                    entries(self.root, self.manifest)

    def test_symlink_input_and_parent_fail(self):
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        self.manifest['files'][0]['path'] = 'link/source.tar'
        with self.assertRaisesRegex(ValueError, 'symlink'):
            verify(self.root, self.manifest)
        self.manifest['files'][0]['path'] = 'link'
        with self.assertRaisesRegex(ValueError, 'symlink'):
            verify(self.root, self.manifest)

    def test_duplicate_paths_fail(self):
        self.manifest['files'].append(dict(self.manifest['files'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            verify(self.root, self.manifest)

    def test_restore_never_overwrites_changed_input(self):
        (self.root / 'source.tar').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            restore_owned(self.root, self.manifest, self.root)
        self.assertEqual((self.root / 'source.tar').read_bytes(), b'changed')

    def test_restore_does_not_fetch_external_evidence(self):
        (self.root / 'source.tar').unlink()
        self.assertEqual(restore_owned(self.root, self.manifest, self.root), [])
        self.assertFalse((self.root / 'source.tar').exists())

    def test_restore_preflights_all_destinations(self):
        self.manifest['files'].append(dict(self.manifest['files'][0], path='../escape'))
        with self.assertRaisesRegex(ValueError, 'path'):
            restore_owned(self.root, self.manifest, self.root)
        self.assertEqual((self.root / 'source.tar').read_bytes(), self.data)


class OwnedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'ambisgis-geotools'
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'LICENSE').write_text('Synthetic test license witness\n')
        local_git(self.repo, 'add', 'LICENSE')
        local_git(self.repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                  '-c', 'commit.gpgSign=false', 'commit', '-qm', 'Fixture')
        self.commit = local_git(self.repo, 'rev-parse', 'HEAD').decode().strip()
        self.url = 'https://github.com/aloerch/ambisgis-geotools.git'
        local_git(self.repo, 'remote', 'add', 'origin', self.url)
        archive = local_git(self.repo, 'archive', '--format=tar', '--prefix=geotools/', self.commit)
        self.custody = self.root / 'custody'
        self.manifest = {'schema_version': 1, 'files': [
            {'path': 'gt.tar', 'size': len(archive), 'sha256': hashlib.sha256(archive).hexdigest(),
             'origin': {'kind': 'owned-git-archive', 'repository': self.url,
                        'commit': self.commit, 'prefix': 'geotools/'}}]}

    def test_exact_archive_recovers_without_network(self):
        self.assertEqual(restore_owned(self.custody, self.manifest, self.root), ['gt.tar'])
        self.assertEqual(verify(self.custody, self.manifest)['files'], 1)
        self.assertEqual(restore_owned(self.custody, self.manifest, self.root), [])

    def test_wrong_owned_remote_fails(self):
        local_git(self.repo, 'remote', 'set-url', 'origin', 'https://example.invalid/unrelated.git')
        with self.assertRaisesRegex(ValueError, 'remote mismatch'):
            restore_owned(self.custody, self.manifest, self.root)
        self.assertFalse(self.custody.exists())

    def test_promisor_clone_fails_before_recovery(self):
        local_git(self.repo, 'config', 'remote.origin.promisor', 'true')
        with self.assertRaisesRegex(ValueError, 'promisor'):
            restore_owned(self.custody, self.manifest, self.root)
        self.assertFalse(self.custody.exists())

    def test_unmatched_archive_hash_is_not_published(self):
        self.manifest['files'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'does not match'):
            restore_owned(self.custody, self.manifest, self.root)
        self.assertEqual(list(self.custody.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
