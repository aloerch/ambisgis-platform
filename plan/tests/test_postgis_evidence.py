"""Regression coverage for omitted or misleading exported suite evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'build-support/postgis/collect_evidence.py'
spec = importlib.util.spec_from_file_location('postgis_evidence', SCRIPT)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RegressionReportExportTests(unittest.TestCase):
    def test_failed_regression_nested_results_and_artifact_mismatch_survive_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / 'run'
            (run / 'logs').mkdir(parents=True)
            (run / 'logs/commands.jsonl').write_text('')
            location = run / 'regressions/database-fixture/regression-fixture'
            invocation = location / 'check-regress/invocation-fixture'
            invocation.mkdir(parents=True)
            recipe = location / 'regress_database.py'
            recipe.write_text('# frozen regression recipe\n')
            validation_recipe = location / 'validate_database.py'
            validation_recipe.write_text('# frozen database recipe\n')
            log = invocation.parent / 'make.log'
            log.write_text('Run tests: 2\nFailed: 1\n')
            receipt = invocation / 'command.json'
            receipt.write_text('{"exit_status":1}\n')
            output = invocation / 'output.log'
            output.write_text(log.read_text())
            diagnostic = invocation / 'failed.diff'
            diagnostic.write_text('actual retained failure details\n')
            expected = {'complete': True, 'tests_run': 2, 'failure_events': 1,
                        'test_skips': 0, 'tests_passed': None}
            environment = {'PGHOST': '/tmp/owned-pg', 'POSTGIS_REGRESS_DB': 'owned_probe',
                           'PGIS_REG_TMPDIR': str(invocation), 'AMBISGIS_REAL_PERL': '/usr/bin/perl',
                           'AMBISGIS_REGRESSION_ARTIFACTS': str(invocation.parent),
                           'UNRELATED_SECRET': 'must-not-export'}
            report = {
                'kind': 'ambisgis-postgis-regression-probe-v1', 'status': 'failed',
                'recipe_snapshot': str(recipe), 'recipe_sha256': sha(recipe),
                'validation_recipe_snapshot': str(validation_recipe),
                'validation_recipe_sha256': sha(validation_recipe),
                'suites': [{'target': 'check-regress', 'status': 'failed', 'results': expected}],
                'commands': [{'argv': ['make', '-j1', 'check-regress'], 'cwd': str(run),
                              'environment': environment, 'log': str(log), 'log_sha256': sha(log),
                              'exit_status': 1, 'results': expected, 'invocations': [{
                                  'command': ['/usr/bin/perl', 'run_test.pl'], 'cwd': str(run),
                                  'environment': environment, 'receipt': str(receipt),
                                  'output_sha256': sha(output), 'exit_status': 1, 'results': expected,
                                  'artifacts': [{'path': str(diagnostic), 'sha256': '0' * 64}]}]}]}
            report_path = location / 'report.json'
            report_path.write_text(json.dumps(report))
            manifest = root / 'inputs.json'
            manifest.write_text('{"inputs":[]}')
            args = argparse.Namespace(run=run, inputs=manifest, custody=None)
            # Tool/version probes are orthogonal to report export and are not run here.
            with patch.object(collector, 'tool_inventory', return_value=[]), \
                    patch.object(collector, 'runtime_inventory', return_value={}):
                exported = collector.collect(args)
            self.assertEqual(len(exported['regression_reports']), 1)
            self.assertEqual(exported['database_reports'], [])
            entry = exported['regression_reports'][0]
            self.assertEqual(entry['identity']['sha256'], sha(report_path))
            actual = entry['report']
            self.assertEqual(actual['status'], 'failed')
            self.assertEqual(actual['suites'][0]['results'], expected)
            self.assertTrue(actual['recorded_recipe_snapshot_hash_matches'])
            self.assertTrue(actual['recorded_validation_recipe_snapshot_hash_matches'])
            command = actual['commands'][0]
            self.assertEqual(command['argv'], report['commands'][0]['argv'])
            self.assertEqual(command['cwd'], str(run))
            self.assertTrue(command['recorded_log_hash_matches'])
            nested = command['invocations'][0]
            self.assertEqual(nested['results'], expected)
            self.assertEqual(nested['exit_status'], 1)
            self.assertTrue(nested['recorded_output_log_hash_matches'])
            self.assertFalse(nested['artifacts'][0]['recorded_path_hash_matches'])
            self.assertEqual(nested['environment']['PGIS_REG_TMPDIR'], str(invocation))
            self.assertEqual(command['environment']['POSTGIS_REGRESS_DB'], 'owned_probe')
            self.assertNotIn('must-not-export', json.dumps(exported))
            self.assertEqual(exported['snapshot_status'], 'incomplete_or_unverified_snapshot')
            self.assertEqual(exported['collection_problems'], [])


if __name__ == '__main__':
    unittest.main()
