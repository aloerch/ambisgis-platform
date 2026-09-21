"""Aggregate evidence guards; synthetic archives are not product acceptance."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import aggregate_evidence as evidence


class AggregateEvidenceTests(unittest.TestCase):
    def archive(self, names):
        stream = io.BytesIO()
        with warnings.catch_warnings(), zipfile.ZipFile(stream, 'w') as archive:
            warnings.simplefilter('ignore', UserWarning)
            for name in names:
                archive.writestr(name, b'fixture-data')
        return zipfile.ZipFile(io.BytesIO(stream.getvalue()))

    def test_complete_entry_hashing_includes_nonclass_resources(self):
        with self.archive(['META-INF/', 'META-INF/MANIFEST.MF', 'a/Example.class']) as archive:
            rows = list(evidence.entries(archive))
        self.assertEqual(rows, [('META-INF/MANIFEST.MF', b'fixture-data'),
                                ('a/Example.class', b'fixture-data')])

    def test_duplicate_and_unsafe_names_refused(self):
        for names in (['a', 'a'], ['../a'], ['/a'], ['a\\b']):
            with self.subTest(names=names), self.archive(names) as archive, self.assertRaises(ValueError):
                list(evidence.entries(archive))

    def test_missing_principal_guard_and_sensitive_diagnostics_refused(self):
        spec = evidence.PATCHED_CLASSES['org/geoserver/security/oauth2/services/GeoNodeTokenServices.class']
        valid = '\0'.join(spec['present']).encode()
        evidence.check_repaired_class(valid, spec)
        for data in (valid.replace(b'isBlank', b'isEmpty'), valid + b'Original map = '):
            with self.subTest(data=data), self.assertRaises(ValueError):
                evidence.check_repaired_class(data, spec)

    def test_stateless_context_must_carry_runtime_transient_annotation(self):
        spec = evidence.STATELESS_CLASSES[
            'org/geoserver/security/oauth2/GeoServerOAuthAuthenticationFilter$StatelessBearerSecurityContext.class']
        data = '\0'.join(spec['present']).encode()
        evidence.check_repaired_class(data, spec)
        with self.assertRaises(ValueError):
            evidence.check_repaired_class(data.replace(b'Lorg/springframework/security/core/Transient;', b'other'), spec)

    def test_missing_and_mismatched_repair_receipts_fail_before_inventory(self):
        for repair in ({}, {'authentication_decision_changed': True, 'injected_sources': ['test'],
                            'test_sources_unchanged': True}):
            with self.subTest(repair=repair), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                build = root / 'build'
                (build / 'work').mkdir(parents=True)
                (build / 'work/preparation.json').write_text(json.dumps({'profiles': evidence.PROFILES}))
                (build / 'result.json').write_text(json.dumps({
                    'command': ['-P' + ','.join(evidence.PROFILES)], 'aggregate_oauth_repair': repair}))
                with patch('aggregate_evidence.packaged_classpath') as inventory:
                    result = evidence.inspect(build, root / 'evidence')
                inventory.assert_not_called()
                self.assertEqual(result['result_exit_code'], 1)
                self.assertIn('main-source-only', result['error']['message'])
                self.assertEqual(json.loads((root / 'evidence/result.json').read_text()), result)

    def test_profile_omission_is_failure_even_with_zero_package_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = root / 'build'
            (build / 'work').mkdir(parents=True)
            (build / 'work/preparation.json').write_text(json.dumps({'profiles': evidence.PROFILES}))
            (build / 'result.json').write_text(json.dumps({'command': ['-Pimporter'], 'result_exit_code': 0}))
            result = evidence.inspect(build, root / 'evidence')
            self.assertEqual(result['result_exit_code'], 1)
            self.assertIn('omitted selected profiles', result['error']['message'])

    def test_role_service_profile_cannot_drop_existing_profiles_or_omit_marker(self):
        for profiles, marked in (([*evidence.PROFILES, 'authkey'], False),
                                 (['authkey'], True), (evidence.PROFILES, True)):
            with self.subTest(profiles=profiles, marked=marked), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                build = root / 'build'
                (build / 'work').mkdir(parents=True)
                (build / 'work/preparation.json').write_text(json.dumps({'profiles': profiles}))
                (build / 'result.json').write_text(json.dumps({
                    'role_service_profile': marked, 'command': ['-P' + ','.join(profiles)]}))
                with patch('aggregate_evidence.packaged_classpath') as inventory:
                    result = evidence.inspect(build, root / 'evidence')
                inventory.assert_not_called()
                self.assertEqual(result['result_exit_code'], 1)
                self.assertIn('selected profiles differ', result['error']['message'])

    def test_role_service_class_must_contain_identity_and_timeout_guards(self):
        for spec in evidence.ROLE_SERVICE_CLASSES.values():
            valid = '\0'.join(spec['present']).encode()
            evidence.check_repaired_class(valid, spec)
            markers = [spec['present'][0]]
            if 'STRICT_DUPLICATE_DETECTION' in spec['present']:
                markers += ['STRICT_DUPLICATE_DETECTION', 'FAIL_ON_TRAILING_TOKENS']
            for marker in markers:
                with self.subTest(marker=marker), self.assertRaises(ValueError):
                    evidence.check_repaired_class(valid.replace(marker.encode(), b'absent'), spec)

    def test_repair_manifest_comes_from_verified_build_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'tooling/java/configured-auth-stateless.json'
            path.parent.mkdir(parents=True)
            path.write_text('{"retained":true}')
            result = {'tooling_manifest': {'java/configured-auth-stateless.json': evidence.sha(path)}}
            self.assertEqual(evidence.retained_repair_manifest(root, result, path.name), path)
            path.write_text('{"retained":false}')
            with self.assertRaisesRegex(ValueError, 'manifest changed'):
                evidence.retained_repair_manifest(root, result, path.name)
            with self.assertRaises(ValueError):
                evidence.retained_repair_manifest(root, result, '../unexpected.json')

    def test_receipts_never_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'existing'
            output.mkdir()
            sentinel = output / 'result.json'
            sentinel.write_text('retained-failure')
            with self.assertRaises(FileExistsError):
                evidence.inspect(Path('/absent'), output)
            self.assertEqual(sentinel.read_text(), 'retained-failure')


if __name__ == '__main__':
    unittest.main()
