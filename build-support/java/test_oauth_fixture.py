import hashlib
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import oauth_fixture as fixture
from resolution_inventory import InventoryError


def digest(data):
    return hashlib.sha256(data.encode()).hexdigest()


class OAuthFixtureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'disposable'
        self.source.mkdir()
        self.original = self.source / 'owned.java'
        self.original.write_text('diagnostic(response);\n')
        self.test_directory = self.source / fixture.MODULE / 'src/test/java/org/geoserver/security/oauth2'
        self.test_directory.mkdir(parents=True)
        self.patch = patch.dict(fixture.SOURCES, {'owned.java': digest(self.original.read_text())}, clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_changed_source_rejected_before_any_overlay(self):
        self.original.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'exact inspected'):
            fixture.prepare(self.source)
        self.assertEqual(list(self.test_directory.iterdir()), [])
        self.assertEqual(self.original.read_text(), 'changed')

    def test_symlink_cannot_mutate_retained_original(self):
        archive = self.root / 'retained-original.java'
        archive.write_bytes(self.original.read_bytes())
        self.original.unlink()
        self.original.symlink_to(archive)
        before = archive.read_bytes()
        with self.assertRaises(InventoryError):
            fixture.prepare(self.source, redact=True)
        self.assertEqual(archive.read_bytes(), before)
        self.assertEqual(list(self.test_directory.iterdir()), [])

    def test_principal_requires_diagnostic_repair_before_source_access(self):
        with self.assertRaisesRegex(ValueError, 'requires the diagnostic'):
            fixture.prepare(self.root / 'absent', principal=True)

    def test_existing_fixture_is_preserved_before_source_repair(self):
        existing = self.test_directory / fixture.FIXTURES[0]
        existing.write_text('existing human fixture')
        with self.assertRaisesRegex(ValueError, 'must not overwrite'):
            fixture.prepare(self.source, redact=True)
        self.assertEqual(existing.read_text(), 'existing human fixture')
        self.assertEqual(self.original.read_text(), 'diagnostic(response);\n')

    def test_bad_expected_output_fails_before_mutation_or_receipt(self):
        row = {'path': 'owned.java', 'before_sha256': digest(self.original.read_text()),
               'after_sha256': 'f' * 64, 'replacements': [['response', 'redacted']]}
        with self.assertRaisesRegex(ValueError, 'predicted output mismatch'):
            fixture.apply_repairs(self.source, [row])
        self.assertEqual(self.original.read_text(), 'diagnostic(response);\n')

    def test_later_input_mismatch_does_not_partially_apply_group(self):
        row = {'path': 'owned.java', 'before_sha256': digest(self.original.read_text()),
               'after_sha256': digest('diagnostic(redacted);\n'), 'replacements': [['response', 'redacted']]}
        second = self.source / 'second.java'
        second.write_text('unexpected')
        bad = {'path': 'second.java', 'before_sha256': digest('expected'),
               'after_sha256': digest('repaired'), 'replacements': [['expected', 'repaired']]}
        with self.assertRaisesRegex(ValueError, 'requires exact'):
            fixture.apply_repairs(self.source, [row, bad])
        self.assertEqual(self.original.read_text(), 'diagnostic(response);\n')

    def test_unrepaired_overlay_preserves_sources_and_reports_actual_fixture_scope(self):
        before = self.original.read_bytes()
        receipt = fixture.prepare(self.source)
        self.assertEqual(self.original.read_bytes(), before)
        self.assertFalse(receipt['authentication_decision_changed'])
        self.assertEqual(receipt['diagnostic_repair'], [])
        self.assertEqual(receipt['principal_repair'], [])
        self.assertEqual(len(receipt['injected_sources']), 2)
        for row in receipt['injected_sources']:
            path = self.source / row['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['sha256'])
        http = (self.test_directory / fixture.FIXTURES[0]).read_text()
        scenarios = set(re.findall(r'^\s*\{"([a-z-]+)", "\d+",', http, re.M))
        self.assertEqual(len(scenarios), receipt['http_scenarios'])
        self.assertTrue({'valid', 'missing-token', 'empty-token', 'wrong-client', 'wrong-secret',
                         'expired-geonode', 'invalid-geonode', 'missing-principal', 'empty-principal',
                         'blank-principal', 'non-string-principal', 'role-injection'} <= scenarios)
        diagnostics = (self.test_directory / fixture.FIXTURES[1]).read_text()
        self.assertEqual(diagnostics.count('@Test'), receipt['diagnostic_tests'])
        self.assertIn('AMBISGIS_ERROR_CAPTURE_CONTROL', diagnostics)


if __name__ == '__main__':
    unittest.main()
