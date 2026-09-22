import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import variant_inputs
import runtime_profile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VariantInputTests(unittest.TestCase):
    def fixture(self, root):
        repo = root / 'mirror'; repo.mkdir()
        original = repo / 'a/b/1/b-1.jar'; original.parent.mkdir(parents=True)
        original.write_bytes(b'publisher-original')
        source = root / 'sources.json'; source.write_text('{"source":"exact inspected production source"}')
        output = root / 'ambisgis-variant.jar'; output.write_bytes(b'new-source-built-output')
        side = Path(str(original) + '.sha1'); side.write_text('old-publisher-checksum')
        rows = [{'maven_path': str(p.relative_to(repo)), 'sha256': digest(p), 'repository': 'publisher'} for p in (original, side)]
        item = {'maven_path': rows[0]['maven_path'], 'original_sha256': rows[0]['sha256'],
                'variant_id': 'ambisgis-b-1', 'path': str(output), 'sha256': digest(output),
                'source_evidence': [{'path': str(source), 'sha256': digest(source)}]}
        manifest = root / 'selection.json'; manifest.write_text(json.dumps({'schema_version': 1, 'variant_id': 'candidate-3', 'replacements': [item]}))
        return repo, rows, manifest, original, source, output

    def test_publisher_coordinate_is_only_local_resolution_and_checksum_is_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, rows, manifest, original, source, output = self.fixture(Path(tmp))
            updated, evidence = variant_inputs.apply(repo, rows, manifest)
            self.assertEqual(original.read_bytes(), output.read_bytes())
            self.assertEqual(updated[0]['original_record']['sha256'], rows[0]['sha256'])
            self.assertFalse(updated[0]['publisher_release_identity'])
            self.assertEqual(Path(str(original)+'.sha1').read_text().strip(), hashlib.sha1(output.read_bytes()).hexdigest())
            self.assertFalse(evidence['distribution_or_donor_publication'])

    def test_changed_source_evidence_refused_before_binary_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, rows, manifest, original, source, output = self.fixture(Path(tmp))
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source evidence'):
                variant_inputs.apply(repo, rows, manifest)
            self.assertEqual(digest(original), rows[0]['sha256'])

    def test_wrong_original_and_duplicate_replacement_refused(self):
        for mutation in ('wrong_original', 'duplicate'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                repo, rows, manifest, original, source, output = self.fixture(Path(tmp))
                data = json.loads(manifest.read_text())
                if mutation == 'duplicate': data['replacements'].append(data['replacements'][0])
                else: data['replacements'][0]['original_sha256'] = '0'*64
                manifest.write_text(json.dumps(data))
                with self.assertRaises(ValueError): variant_inputs.apply(repo, rows, manifest)
                self.assertEqual(digest(original), rows[0]['sha256'])

    def test_runtime_profile_rejects_war_or_renderer_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'lib').mkdir();jar=root/'lib/marlin-0.9.4.8.jar';jar.write_bytes(b'renderer')
            war=root/'app.war';war.write_bytes(b'war')
            manifest=root/'profile.json';manifest.write_text(json.dumps({'schema_version':1,'profile':'NO-ORACLE-headless-Temurin17',
                'war_sha256':digest(war),'renderer_member':runtime_profile.MEMBER,'renderer_sha256':digest(jar)}))
            profile=runtime_profile.load(manifest,{'war_sha256':digest(war)},root)
            self.assertIn('-Dsun.java2d.opengl=false',runtime_profile.flags(profile,war))
            jar.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'renderer changed'):runtime_profile.flags(profile,war)
            with self.assertRaises(ValueError):runtime_profile.load(manifest,{'war_sha256':'0'*64},root)

class NoJpeg2000RuntimeTests(unittest.TestCase):
    def test_replacements_are_bound_and_rechecked_before_every_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'lib').mkdir()
            war = root / 'app.war'; war.write_bytes(b'new-war')
            renderer = root / 'lib' / Path(runtime_profile.MEMBER).name
            renderer.write_bytes(b'renderer')
            profile = {'schema_version': 1, 'profile': runtime_profile.NO_JPEG2000,
                       'war_sha256': digest(war), 'renderer_member': runtime_profile.MEMBER,
                       'renderer_sha256': digest(renderer)}
            for key, member in runtime_profile.REPLACED_MEMBERS.items():
                jar = root / 'lib' / Path(member).name
                jar.write_bytes(('new-' + key).encode())
                profile[key + '_member'] = member
                profile[key + '_sha256'] = digest(jar)
            manifest = root / 'profile.json'; manifest.write_text(json.dumps(profile))
            loaded = runtime_profile.load(manifest, {'war_sha256': digest(war)}, root)
            self.assertIn('-Dambisgis.fixture.noJpeg2000=true', runtime_profile.flags(loaded, war))
            for key, member in runtime_profile.REPLACED_MEMBERS.items():
                jar = root / 'lib' / Path(member).name; original = jar.read_bytes()
                jar.write_bytes(b'stale-publisher')
                with self.assertRaisesRegex(ValueError, 'runtime ' + key + ' changed'):
                    runtime_profile.flags(loaded, war)
                with self.assertRaisesRegex(ValueError, 'packaged ' + key):
                    runtime_profile.load(manifest, {'war_sha256': digest(war)}, root)
                jar.write_bytes(original)
            del profile['json_sha256']; manifest.write_text(json.dumps(profile))
            with self.assertRaises(ValueError):
                runtime_profile.load(manifest, {'war_sha256': digest(war)}, root)


if __name__ == '__main__': unittest.main()
