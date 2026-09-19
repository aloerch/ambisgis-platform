"""Evidence parser tests: incomplete/skipped runs must never become passing counts."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import regress_database
from regress_database import parse_results, retain_driver_snapshots


class RegressionEvidenceTests(unittest.TestCase):
    def test_combined_normal_and_self_upgrade_counts(self):
        result = parse_results('a ok\nRun tests: 20\nFailed: 0\n\nother ok\nRun tests: 21\nFailed: 0\n')
        self.assertEqual(result['tests_run'], 41)
        self.assertEqual(result['tests_passed'], 41)
        self.assertTrue(result['complete'])

    def test_missing_summary_is_not_zero_failures_pass(self):
        result = parse_results('Creating database\nCould not connect\n')
        self.assertFalse(result['complete'])
        self.assertIsNone(result['tests_passed'])

    def test_failed_summary_does_not_invent_pass_count(self):
        result = parse_results('Run tests: 20\nFailed: 3\n')
        self.assertEqual(result['failure_events'], 3)
        self.assertIsNone(result['tests_passed'])

    def test_skipped_test_deducted_and_retained(self):
        result = parse_results("foo ... skipped (can't read any foo.sql)\nRun tests: 3\nFailed: 0\n")
        self.assertEqual(result['test_skips'], 1)
        self.assertEqual(result['tests_passed'], 2)
        self.assertEqual(len(result['skip_messages']), 1)

    def test_control_flow_skip_is_not_missing_sql_test(self):
        result = parse_results('Skipping upgrade test as RUNTESTFLAGS already requested upgrades\nRun tests: 3\nFailed: 0\n')
        self.assertEqual(result['test_skips'], 0)
        self.assertEqual(len(result['skip_messages']), 1)

    def test_empty_summary_does_not_establish_execution(self):
        self.assertFalse(parse_results('Run tests: 0\nFailed: 0\n')['complete'])


class DriverSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.probe = SimpleNamespace(log_dir=self.directory, report={}, save=lambda: None)

    def test_frozen_pair_imports_without_original_checkout_on_path(self):
        # Probe already snapshots its own driver in the integrated harness.
        validation = Path(regress_database.validation_driver.__file__).read_bytes()
        (self.directory / 'validate_database.py').write_bytes(validation)
        self.probe.report['recipe_sha256'] = hashlib.sha256(validation).hexdigest()
        retain_driver_snapshots(self.probe)
        report = self.probe.report
        self.assertNotEqual(report['recipe_sha256'], report['validation_recipe_sha256'])
        for key, hash_key in (('recipe_snapshot', 'recipe_sha256'),
                              ('validation_recipe_snapshot', 'validation_recipe_sha256')):
            snapshot = Path(report[key])
            self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), report[hash_key])
            self.assertEqual(snapshot.stat().st_mode & 0o222, 0)
        # Isolated interpreter cannot import the original checkout or user site.
        command = [sys.executable, '-I', '-B', '-c',
                   'import sys; sys.path.insert(0, sys.argv[1]); '
                   'import regress_database, validate_database; '
                   'print(regress_database.__file__); print(validate_database.__file__)',
                   str(self.directory)]
        output = subprocess.check_output(command, text=True).splitlines()
        self.assertEqual(output, [report['recipe_snapshot'], report['validation_recipe_snapshot']])

    def test_existing_validation_snapshot_mismatch_rejected(self):
        (self.directory / 'validate_database.py').write_text('different contents')
        self.probe.report['recipe_sha256'] = 'previously-recorded-hash'
        with self.assertRaisesRegex(RuntimeError, 'recorded identity'):
            retain_driver_snapshots(self.probe)
        self.assertFalse((self.directory / 'regress_database.py').exists())

    def test_existing_regression_snapshot_is_never_replaced(self):
        snapshot = self.directory / 'regress_database.py'
        snapshot.write_text('prior evidence')
        with self.assertRaises(FileExistsError):
            retain_driver_snapshots(self.probe)
        self.assertEqual(snapshot.read_text(), 'prior evidence')


if __name__ == '__main__':
    unittest.main()
