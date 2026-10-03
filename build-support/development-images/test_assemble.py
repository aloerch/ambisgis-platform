"""Real archive checks with inert synthetic input files; no container execution."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
import zipfile

import assemble as build


class Assembly(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.inputs = self.root / 'inputs'; self.inputs.mkdir()
        (self.inputs / 'app.py').write_bytes(b'not executed\n'); (self.inputs / 'app.py').chmod(0o644)
        self.provenance = self.root / 'provenance.json'; self.provenance.write_text('{"synthetic":true}\n')
        self.inventory = self.root / 'inventory.json'; self.snapshot()
        self.selection = {'schema_version': 1, 'platform_revision': '1' * 40, 'epoch': 1790899200,
            'components': [{'id': 'synthetic', 'kind': 'tree', 'root': str(self.inputs),
                            'inventory': self.ref(self.inventory), 'destination': 'opt/test',
                            'revision': '2' * 40, 'provenance': [self.ref(self.provenance)]}],
            'images': {role: ['synthetic'] for role in build.ROLES}}
        self.selection_path = self.root / 'selection.json'

    def ref(self, path): return {'path': str(path), 'sha256': build.digest(path)}

    def snapshot(self):
        entries = {}
        for path in self.inputs.iterdir():
            if path.is_symlink(): entries[path.name] = {'kind': 'symlink', 'target': os.readlink(path)}
            elif path.is_dir(): entries[path.name] = {'kind': 'directory', 'mode': path.stat().st_mode & 0o7777}
            else: entries[path.name] = {'kind': 'file', 'mode': path.stat().st_mode & 0o7777,
                                        'bytes': path.stat().st_size, 'sha256': build.digest(path)}
        self.inventory.write_bytes(build.encoded({'schema_version': 1, 'entries': entries}))

    def run_assembly(self, name='out'):
        self.selection_path.write_bytes(build.encoded(self.selection))
        return build.assemble(self.selection_path, self.root / name)

    def test_two_actual_archives_are_identical_and_bind_source(self):
        first = self.run_assembly('one'); second = self.run_assembly('two')
        self.assertEqual(first, second)
        self.assertFalse(first['runtime_executed'])
        with tarfile.open(self.root / 'one/database.oci.tar') as archive:
            index = json.load(archive.extractfile('index.json'))
            descriptor = index['manifests'][0]
            manifest = json.load(archive.extractfile('blobs/sha256/' + descriptor['digest'][7:]))
            raw = archive.extractfile('blobs/sha256/' + manifest['layers'][0]['digest'][7:]).read()
        with tarfile.open(fileobj=io.BytesIO(raw)) as layer:
            item = layer.getmember('opt/test/app.py')
            self.assertEqual((item.uid, item.gid, item.mode, item.mtime), (0, 0, 0o644, 1790899200))
            self.assertEqual(layer.extractfile(item).read(), b'not executed\n')

    def test_archives_load_through_real_bundle_contract(self):
        # Reuse only the explicitly synthetic inert runtime prerequisite fixture.
        # The product image references and OCI archives go through bundle.load.
        sys.path.insert(0, str(build.ROOT / 'plan/tests'))
        from test_development_installer import InstallerStateTests
        from installer import bundle
        fixture = InstallerStateTests(); fixture.setUp()
        try:
            result = self.run_assembly()
            shutil.copyfile(self.root / 'out/source-manifest.json', fixture.inputs / 'source.json')
            fixture.document['source_manifest'] = fixture.ref('source.json')
            for role, row in result['images'].items():
                shutil.copyfile(self.root / 'out' / row['path'], fixture.inputs / row['path'])
                fixture.document['images'][role] = {'archive': row['path'], 'archive_sha256': row['sha256'],
                    'reference': row['reference'], 'image_id': row['image_id'],
                    'source_manifest_sha256': result['source_manifest_sha256']}
            fixture.seal()
            bundle.load(fixture.manifest, fixture.identity)
        finally: fixture.tearDown()

    def test_unlisted_python_startup_module_rejected_before_output(self):
        (self.inputs / 'sitecustomize.py').write_text('raise Exception("must not execute")')
        with self.assertRaisesRegex(ValueError, 'complete inventory'): self.run_assembly()
        self.assertFalse((self.root / 'out').exists())

    def test_pinned_inventory_and_payload_changes_rejected(self):
        (self.inputs / 'app.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'complete inventory'): self.run_assembly()
        self.snapshot()
        with self.assertRaisesRegex(ValueError, 'digest differs'): self.run_assembly()

    def test_special_shared_writable_and_privileged_modes_rejected(self):
        for permissions in (0o666, 0o4755, 0o2755):
            (self.inputs / 'app.py').chmod(permissions); self.snapshot()
            self.selection['components'][0]['inventory'] = self.ref(self.inventory)
            with self.assertRaisesRegex(ValueError, 'unsafe source mode'): self.run_assembly()
        (self.inputs / 'app.py').chmod(0o644)
        os.mkfifo(self.inputs / 'pipe')
        with self.assertRaisesRegex(ValueError, 'special file'): self.run_assembly()

    def test_private_producer_modes_become_readable_to_keep_id_users(self):
        (self.inputs / 'app.py').chmod(0o600)
        (self.inputs / 'private').mkdir(mode=0o700); self.snapshot()
        self.selection['components'][0]['inventory'] = self.ref(self.inventory)
        self.run_assembly()
        source = json.loads((self.root / 'out/source-manifest.json').read_bytes())
        rows = source['images']['database']
        self.assertEqual((rows['opt/test/app.py']['mode'], rows['opt/test/app.py']['source_mode']), (0o644, 0o600))
        self.assertEqual((rows['opt/test/private']['mode'], rows['opt/test/private']['source_mode']), (0o755, 0o700))

    def test_source_parent_symlink_rejected(self):
        (self.root / 'redirect').symlink_to(self.inputs, target_is_directory=True)
        self.selection['components'][0]['root'] = str(self.root / 'redirect')
        with self.assertRaises(ValueError): self.run_assembly()

    def test_safe_image_symlink_preserved_and_bad_links_rejected(self):
        (self.inputs / 'alias').symlink_to('app.py'); self.snapshot()
        self.selection['components'][0]['inventory'] = self.ref(self.inventory)
        self.run_assembly('safe')
        for target in ('../../../outside', 'absent', 'alias'):
            (self.inputs / 'alias').unlink(); (self.inputs / 'alias').symlink_to(target); self.snapshot()
            self.selection['components'][0]['inventory'] = self.ref(self.inventory)
            with self.assertRaises(ValueError): self.run_assembly()

    def test_duplicate_payload_destination_rejected(self):
        extra = copy.deepcopy(self.selection['components'][0]); extra['id'] = 'collision'
        self.selection['components'].append(extra)
        for row in self.selection['images'].values(): row.append('collision')
        with self.assertRaisesRegex(ValueError, 'collision'): self.run_assembly()

    def test_existing_output_is_untouched(self):
        out = self.root / 'out'; out.mkdir(); sentinel = out / 'retained'; sentinel.write_bytes(b'original')
        with self.assertRaisesRegex(ValueError, 'fresh'): self.run_assembly()
        self.assertEqual(sentinel.read_bytes(), b'original')

    def wheel(self, extra=None, wrong_record=False):
        values = {'pkg/__init__.py': b'unchanged source\n', 'pkg-1.dist-info/LICENSE': b'synthetic notice\n'}
        if extra: values.update(extra)
        rows = []
        for name, data in values.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            rows.append(name + ',sha256=' + ('wrong' if wrong_record else digest) + ',' + str(len(data)))
        values['pkg-1.dist-info/RECORD'] = ('\n'.join(rows) + '\npkg-1.dist-info/RECORD,,\n').encode()
        path = self.root / 'pkg.whl'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in values.items():
                info = zipfile.ZipInfo(name); info.external_attr = 0o100644 << 16; archive.writestr(info, data)
        return {'id': 'wheel', 'kind': 'wheel', 'archive': self.ref(path), 'destination': 'opt/python-site',
                'revision': None, 'provenance': [self.ref(self.provenance)]}

    def test_wheel_record_and_data_projection_preserve_all_bytes(self):
        component = self.wheel({'pkg-1.data/scripts/tool': b'#!python\n'})
        result = build.wheel(component)
        self.assertEqual(len(result), 4)
        script = next(row for row in result if row.source.endswith('/tool'))
        self.assertEqual(script.name, 'opt/ambisgis/wheel-data/wheel/scripts/tool')
        with build.stream(script) as source: self.assertEqual(source.read(), b'#!python\n')

    def test_wrong_wheel_record_and_traversal_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'RECORD'): build.wheel(self.wheel(wrong_record=True))
        with self.assertRaisesRegex(ValueError, 'unsafe image member'): build.wheel(self.wheel({'../escape': b'bad'}))

    def test_wheel_modes_and_colliding_test_packages_have_explicit_projection(self):
        component = self.wheel({'tests/source.py': b'exact test bytes'})
        path = Path(component['archive']['path']); original = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(path, 'w') as target:
            for info in source.infolist():
                info.external_attr = 0o100664 << 16; target.writestr(info, source.read(info))
        component['archive'] = self.ref(path)
        rows = build.wheel(component)
        entry = next(x for x in rows if x.source == 'tests/source.py')
        self.assertEqual(entry.name, 'opt/ambisgis/wheel-data/wheel/tests/source.py')
        self.assertEqual((entry.mode, entry.source_mode), (0o644, 0o664))
        self.assertEqual(entry.sha256, hashlib.sha256(b'exact test bytes').hexdigest())

    def test_mapped_input_hash_and_source_parent_guard(self):
        path = self.inputs / 'app.py'
        inventory = self.root / 'mapped.json'
        inventory.write_bytes(build.encoded({'schema_version': 1, 'entries': {'opt/app.py': {
            'kind': 'file', 'file': self.ref(path), 'mode': 0o644, 'origin': 'synthetic signed member'}}}))
        component = {'id': 'mapped', 'inventory': self.ref(inventory)}
        self.assertEqual(build.mapped_files(component)[0].sha256, build.digest(path))
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'digest differs'): build.mapped_files(component)

    def test_path_alias_and_whiteout_are_rejected(self):
        for name in ('/root', '../parent', 'a/../b', 'a//b', 'a/./b', 'a\\b', '.wh.app', 'a/.wh..wh..opq'):
            with self.assertRaises(ValueError): build.relative(name)


if __name__ == '__main__': unittest.main()
