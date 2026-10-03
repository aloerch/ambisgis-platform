import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from custody import (TREE, VERSIONS, WORKSPACES, archive_files, production_lock,
                     regular, resolve, source_manifest, verify_inventory, verify_sri)
from install import source_projection, verify_installed, verify_reviewed


class CustodyGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def archive(self, members):
        path = self.root / 'input.tar.gz'
        with tarfile.open(path, 'w:gz') as stream:
            for name, value in members:
                member = tarfile.TarInfo(name)
                if value is None:
                    member.type = tarfile.SYMTYPE
                    member.linkname = '/tmp/escape'
                    stream.addfile(member)
                else:
                    member.size = len(value)
                    stream.addfile(member, io.BytesIO(value))
        return path

    def fixture(self):
        packages = {'': {}}
        files = {}
        for name in WORKSPACES:
            path = 'packages/' + name
            actual_name = '@koopjs/' + ('koop-core' if name == 'core' else name)
            row = {'name': actual_name, 'version': VERSIONS[name], 'dependencies': {}}
            files[path + '/package.json'] = json.dumps(row).encode()
            packages[path] = row
            packages['node_modules/' + actual_name] = {'link': True, 'resolved': path}
        files['package-lock.json'] = json.dumps({'lockfileVersion': 2, 'packages': packages}).encode()
        return files

    def tree(self, files):
        entries = [{'path': name, 'type': 'blob', 'mode': '100644',
                    'sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}
                   for name, data in sorted(files.items())]
        encoded = b''.join(b'100644 ' + row['path'].encode() + b'\0' + bytes.fromhex(row['sha'])
                           for row in entries)
        digest = hashlib.sha1(b'tree ' + str(len(encoded)).encode() + b'\0' + encoded).hexdigest()
        return {'sha': digest, 'tree': entries}

    def test_valid_archive_matches_git_blob(self):
        data = b'license and source\n'
        path = self.archive([('repo/LICENSE', data)])
        tree = self.tree({'LICENSE': data})
        with patch('custody.TREE', tree['sha']):
            actual, rows = source_manifest(path, tree)
        self.assertEqual(actual['LICENSE'], data)
        self.assertEqual(rows['LICENSE']['bytes'], len(data))

    def test_corrupt_source_blob_rejected(self):
        path = self.archive([('repo/LICENSE', b'changed')])
        tree = self.tree({'LICENSE': b'original'})
        with patch('custody.TREE', tree['sha']), self.assertRaisesRegex(ValueError, 'Git blob differs'):
            source_manifest(path, tree)

    def test_missing_source_file_rejected(self):
        path = self.archive([('repo/a', b'a')])
        tree = self.tree({'a': b'a', 'b': b'b'})
        with patch('custody.TREE', tree['sha']), self.assertRaisesRegex(ValueError, 'file set differs'):
            source_manifest(path, tree)

    def test_relabelled_tree_metadata_rejected(self):
        path = self.archive([('repo/a', b'a')])
        tree = self.tree({'a': b'a'})
        tree['sha'] = TREE
        with self.assertRaisesRegex(ValueError, 'Git tree content hash differs'):
            source_manifest(path, tree)

    def test_traversal_and_archive_links_rejected(self):
        for name, value in [('repo/../escape', b'x'), ('repo/link', None)]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                archive_files(self.archive([(name, value)]))

    def test_missing_and_symlink_input_rejected(self):
        with self.assertRaises(ValueError):
            regular(self.root, 'missing')
        (self.root / 'target').write_text('source')
        (self.root / 'link').symlink_to('target')
        with self.assertRaises(ValueError):
            regular(self.root, 'link')

    def test_extra_symlink_directory_rejected(self):
        (self.root / 'outside-link').symlink_to('/tmp', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink in retained inventory'):
            verify_inventory(self.root)

    def test_corrupt_registry_archive_rejected(self):
        path = self.root / 'archive'
        path.write_bytes(b'original')
        integrity = 'sha512-' + base64.b64encode(hashlib.sha512(b'original').digest()).decode()
        verify_sri(path, integrity)
        path.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            verify_sri(path, integrity)

    def test_wrong_workspace_version_rejected(self):
        files = self.fixture()
        value = json.loads(files['packages/core/package.json'])
        value['version'] = '10.4.18'
        files['packages/core/package.json'] = json.dumps(value).encode()
        with self.assertRaisesRegex(ValueError, 'source version differs'):
            production_lock(files)

    def test_missing_lock_dependency_rejected(self):
        files = self.fixture()
        value = json.loads(files['packages/core/package.json'])
        value['dependencies'] = {'absent': '^1.0.0'}
        files['packages/core/package.json'] = json.dumps(value).encode()
        with self.assertRaisesRegex(ValueError, 'unresolved locked dependency'):
            production_lock(files)

    def test_nested_resolution_and_dev_graph_omission(self):
        packages = {'node_modules/dep': {}, 'node_modules/outer/node_modules/dep': {}}
        self.assertEqual(resolve(packages, 'node_modules/outer/node_modules/inner', 'dep'),
                         'node_modules/outer/node_modules/dep')
        files = self.fixture()
        lock = json.loads(files['package-lock.json'])
        lock['packages']['node_modules/dev-only'] = {'version': '1.0.0', 'dev': True}
        files['package-lock.json'] = json.dumps(lock).encode()
        _, actual, _ = production_lock(files)
        self.assertNotIn('node_modules/dev-only', actual['packages'])

    def test_relabelled_retained_manifest_rejected(self):
        (self.root / 'manifest.json').write_text('{}')
        spec = self.root / 'reviewed.json'
        from custody import COMMIT
        spec.write_text(json.dumps({'source_commit': COMMIT, 'source_tree': TREE,
                                    'manifest_sha256': '0' * 64}))
        with self.assertRaisesRegex(ValueError, 'reviewed manifest differs'):
            verify_reviewed(self.root, spec)

    def test_relabelled_production_lock_rejected(self):
        manifest = self.root / 'manifest.json'
        manifest.write_text('{}')
        (self.root / 'package-lock.json').write_text('{"substituted":true}')
        spec = self.root / 'reviewed.json'
        from custody import COMMIT, sha
        spec.write_text(json.dumps({'source_commit': COMMIT, 'source_tree': TREE,
                                    'manifest_sha256': sha(manifest), 'production_lock_sha256': '0' * 64}))
        with self.assertRaisesRegex(ValueError, 'reviewed lock differs'):
            verify_reviewed(self.root, spec)

    def test_projection_preserves_runtime_fields_and_original(self):
        files = self.fixture()
        for name in WORKSPACES:
            path = 'packages/' + name + '/package.json'
            value = json.loads(files[path])
            value.update(devDependencies={'test-only': '1.0.0'}, main='src/index.js', scripts={'test': 'test-only'})
            files[path] = json.dumps(value).encode()
            (self.root / path).parent.mkdir(parents=True)
        before = dict(files)
        changes = source_projection(files, self.root)
        self.assertEqual(files, before)
        self.assertEqual(len(changes), 6)
        for name in WORKSPACES:
            value = json.loads((self.root / 'packages' / name / 'package.json').read_text())
            self.assertNotIn('devDependencies', value)
            self.assertEqual(value['main'], 'src/index.js')
            self.assertEqual(value['scripts'], {'test': 'test-only'})

    def incomplete_registry_fixture(self):
        files = self.fixture()
        package = json.loads(files['packages/core/package.json'])
        package['dependencies'] = {'example': '1.2.3'}
        files['packages/core/package.json'] = json.dumps(package).encode()
        lock = json.loads(files['package-lock.json'])
        lock['packages']['node_modules/example'] = {'version': '1.2.3'}
        files['package-lock.json'] = json.dumps(lock).encode()
        return files

    def test_missing_registry_identity_cannot_pass_closure(self):
        with self.assertRaisesRegex(ValueError, 'unresolved registry archive identity'):
            production_lock(self.incomplete_registry_fixture())
        with self.assertRaisesRegex(ValueError, 'unresolved installed registry identity'):
            verify_installed(self.root, self.root, {'packages': {'node_modules/example': {'version': '1.2.3'}}})

    def test_explicit_supplement_preserves_locked_version(self):
        supplement = {'name': 'example', 'version': '1.2.3',
                      'resolved': 'https://registry.npmjs.org/example/-/example-1.2.3.tgz',
                      'integrity': 'sha512-' + base64.b64encode(b'example').decode()}
        _, lock, reconciliation = production_lock(self.incomplete_registry_fixture(), {'example@1.2.3': supplement})
        self.assertEqual(lock['packages']['node_modules/example']['version'], '1.2.3')
        self.assertEqual(len(reconciliation['archive_identity_supplements']), 1)
        supplement['version'] = '1.2.4'
        with self.assertRaisesRegex(ValueError, 'supplemented registry version differs'):
            production_lock(self.incomplete_registry_fixture(), {'example@1.2.3': supplement})

    def test_unexpected_installed_module_rejected(self):
        files = self.fixture()
        _, lock, _ = production_lock(files)
        for name in WORKSPACES:
            source = self.root / 'packages' / name
            source.mkdir(parents=True)
            value = json.loads(files['packages/' + name + '/package.json'])
            (source / 'package.json').write_text(json.dumps(value))
            link = self.root / 'node_modules' / value['name']
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(source)
        self.assertEqual(len(verify_installed(self.root, self.root, lock)['links']), 6)
        extra = self.root / 'node_modules/extra/index.js'
        extra.parent.mkdir()
        extra.write_text('throw new Error("unselected code")')
        with self.assertRaisesRegex(ValueError, 'unexpected installed file'):
            verify_installed(self.root, self.root, lock)


if __name__ == '__main__':
    unittest.main()
