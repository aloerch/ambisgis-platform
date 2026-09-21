"""Adversarial artifact-staging checks; these are not browser/GIS acceptance."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from smoke import verify_manifest
from smoke_backend import stage_frontend, add_wms_style


class ArtifactOriginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'compiled'
        (self.source / 'dist/js').mkdir(parents=True)
        (self.source / 'dist/js/gn-map.js').write_bytes(b'new compilation')
        (self.source / 'dist/js/42.chunk.js').write_bytes(b'fresh loaded chunk')
        self.manifest = self.root / 'output-manifest.json'
        self.files = {str(p.relative_to(self.source)):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in self.source.rglob('*') if p.is_file()}
        self.manifest.write_text(json.dumps({'files':[{'path':p,'sha256':sha,'bytes':(self.source/p).stat().st_size}
                                                        for p,sha in self.files.items()]}))

    def test_staging_replaces_inherited_chunks_with_exact_complete_compilation(self):
        target = self.root / 'static/mapstore'
        target.mkdir(parents=True)
        (target / 'inherited-old-chunk.js').write_bytes(b'never serve this')
        self.assertEqual(stage_frontend(self.source,target),self.files)
        self.assertFalse((target / 'inherited-old-chunk.js').exists())
        self.assertEqual(verify_manifest(target,self.manifest),self.files)

    def test_changed_compiled_entry_is_rejected(self):
        (self.source / 'dist/js/gn-map.js').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'differs'):
            verify_manifest(self.source,self.manifest)

    def test_extra_unmanifested_chunk_is_rejected(self):
        (self.source / 'dist/js/hidden.js').write_bytes(b'unrecorded')
        with self.assertRaisesRegex(ValueError,'differs'):
            verify_manifest(self.source,self.manifest)

    def test_missing_compiled_chunk_is_rejected(self):
        (self.source / 'dist/js/42.chunk.js').unlink()
        with self.assertRaisesRegex(ValueError,'differs'):
            verify_manifest(self.source,self.manifest)

    def test_manifest_duplicate_paths_are_rejected(self):
        doc = json.loads(self.manifest.read_text())
        doc['files'].append(doc['files'][0])
        self.manifest.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            verify_manifest(self.source,self.manifest)

    def test_symlink_artifact_is_rejected_before_old_assets_are_removed(self):
        (self.source / 'dist/js/external.js').symlink_to(self.manifest)
        target = self.root / 'static/mapstore'
        target.mkdir(parents=True)
        old = target / 'old.js'; old.write_bytes(b'preserve on failure')
        with self.assertRaisesRegex(ValueError,'symlink'):
            stage_frontend(self.source,target)
        self.assertEqual(old.read_bytes(),b'preserve on failure')

    def test_destination_symlink_cannot_delete_external_tree(self):
        external = self.root / 'external'; external.mkdir()
        target = self.root / 'mapstore'; target.symlink_to(external,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'disposable'):
            stage_frontend(self.source,target)
        self.assertTrue(external.is_dir())

    def test_wms_style_updates_the_native_feature_layer_location(self):
        layer = self.root / 'workspaces/fixture/public_points/public_points/layer.xml'
        layer.parent.mkdir(parents=True)
        layer.write_text('<layer><id>fixture-layer-public_points</id></layer>')
        add_wms_style(self.root)
        import xml.etree.ElementTree as ET
        self.assertEqual(ET.parse(layer).getroot().find('defaultStyle/id').text, 'fixture-witness-style')
        self.assertTrue((self.root / 'styles/witness.sld').is_file())

    def test_no_integrated_entry_is_not_a_build(self):
        (self.source / 'dist/js/gn-map.js').unlink()
        with self.assertRaisesRegex(ValueError,'missing'):
            stage_frontend(self.source,self.root / 'mapstore')


if __name__ == '__main__': unittest.main()
