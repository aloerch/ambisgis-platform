"""Probe receipts fail closed; these fixtures are tooling tests, not GIS tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import compatibility


class CompatibilityTests(unittest.TestCase):
    def fixture(self, root, xml='<testsuite name="org.geotools.xml.SchemaResolverTest" tests="2" failures="0" errors="0" skipped="0"/>', network=True, mutate=False, code=0, database=None):
        def prepare(_custody, output):
            (output / 'source').mkdir(parents=True)
            (output / 'source/pom.xml').write_text('<project/>')
            (output / 'user').mkdir()
            (output / 'logs').mkdir()
            (output / 'empty-global-settings.xml').write_text('<settings/>\n')
            return output
        def execute(_cmd, source, _env, _stream, _timeout):
            reports = source / 'geotools/modules/library/xml/target/surefire-reports'
            reports.mkdir(parents=True)
            (reports / 'TEST-probe.xml').write_text(xml)
            if mutate:
                (source / 'pom.xml').write_text('<project>modified</project>')
            if network:
                (root / 'output/network-denial.json').write_text(json.dumps({
                    'status': 'completed', 'command_exit_code': code,
                    'probes': [{'family': f, 'operation': 'socket(SOCK_STREAM)', 'errno': 1, 'passed': True}
                               for f in ('AF_INET', 'AF_INET6')]}))
            return code
        with patch('compatibility.toolchain.verify_extracted', return_value={'verified': True}), \
             patch('compatibility.prepare', side_effect=prepare), \
             patch('compatibility.materialize', return_value=[]), \
             patch('compatibility.execute', side_effect=execute), \
             patch('geofence_fixture.start', return_value=(database, {})):
            return compatibility.probe(root / 'audit', root / 'custody', root / 'tc', root / 'tools',
                                       root / 'output', 'geofence' if database else 'xml', 'test', tests='target',
                                       postgres_prefix=root / 'pg' if database else None,
                                       postgres_evidence=root / 'historical.json' if database else None)

    def test_target_tests_and_network_receipt_required_for_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp))
            self.assertEqual(result['result_exit_code'], 0)
            self.assertTrue(result['network_denial_verified'])
            self.assertEqual(result['target_executed_tests'], 2)
            self.assertEqual(result['native_tests']['passed'], 2)
            self.assertFalse(result['acceptance_build'])

    def test_malformed_xml_preserves_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.fixture(root, xml='<broken')
            self.assertEqual(result['result_exit_code'], 1)
            self.assertEqual(result['finalization_error']['type'], 'ParseError')
            self.assertTrue((root / 'output/result.json').is_file())

    def test_no_matching_target_tests_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), xml='<testsuite name="unrelated.Test" tests="2"/>')
            self.assertEqual(result['result_exit_code'], 1)
            self.assertIn('no executed tests', result['finalization_error']['message'])

    def test_only_skipped_target_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), xml='<testsuite name="org.geotools.xml.Test" tests="2" skipped="2"/>')
            self.assertEqual(result['result_exit_code'], 1)

    def test_missing_network_receipt_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), network=False)
            self.assertEqual(result['result_exit_code'], 1)
            self.assertEqual(result['finalization_error']['type'], 'FileNotFoundError')

    def test_original_source_mutation_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), mutate=True)
            self.assertEqual(result['result_exit_code'], 1)
            self.assertEqual(result['changed_original_source_files'], ['pom.xml'])

    def test_native_failure_cannot_be_masked_by_zero_maven_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), xml='<testsuite name="org.geotools.xml.Test" tests="2" errors="1"/>')
            self.assertEqual(result['exit_code'], 0)
            self.assertEqual(result['result_exit_code'], 1)

    def test_maven_failure_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), code=1)
            self.assertEqual(result['exit_code'], 1)
            self.assertEqual(result['result_exit_code'], 1)

    def test_outputs_never_overwrite_previous_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            before = (root / 'output/result.json').read_bytes()
            with self.assertRaises(FileExistsError):
                self.fixture(root)
            self.assertEqual(before, (root / 'output/result.json').read_bytes())

    def test_database_cleanup_runs_when_result_parsing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Mock()
            result = self.fixture(Path(tmp), xml='<broken', database=database)
            database.stop.assert_called_once()
            self.assertTrue(result['postgres_cluster_stopped'])
            self.assertEqual(result['result_exit_code'], 1)

    def test_database_shutdown_failure_is_recorded_and_fails_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Mock()
            database.stop.side_effect = RuntimeError('fixture stop failed')
            result = self.fixture(Path(tmp), database=database)
            self.assertEqual(result['result_exit_code'], 1)
            self.assertEqual(result['shutdown_error']['message'], 'fixture stop failed')

    def test_unknown_stage_repair_and_target_refused(self):
        for target, stage, repair in [('xml', 'deploy', 'none'), ('unknown', 'test', 'none'), ('xml', 'test', '../arbitrary')]:
            with self.subTest(target=target, stage=stage, repair=repair), self.assertRaises(ValueError):
                compatibility.probe(Path('/audit'), Path('/custody'), Path('/tc'), Path('/tools'),
                                    Path('/absent'), target, stage, repair=repair)


if __name__ == '__main__':
    unittest.main()
