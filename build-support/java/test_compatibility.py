"""Probe receipts fail closed; these fixtures are tooling tests, not GIS tests."""
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import compatibility


class CompatibilityTests(unittest.TestCase):
    def fixture(self, root, xml='<testsuite name="org.geotools.xml.SchemaResolverTest" tests="2" failures="0" errors="0" skipped="0"><testcase classname="org.geotools.xml.SchemaResolverTest" name="first"/><testcase classname="org.geotools.xml.SchemaResolverTest" name="second"/></testsuite>', network=True, mutate=False, code=0, database=None):
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
            self.assertEqual(result['finalization_error']['type'], 'AuditError')
            self.assertTrue((root / 'output/result.json').is_file())

    def test_no_matching_target_tests_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), xml='<testsuite name="unrelated.Test" tests="2" failures="0" errors="0" skipped="0"><testcase classname="unrelated.Test" name="first"/><testcase classname="unrelated.Test" name="second"/></testsuite>')
            self.assertEqual(result['result_exit_code'], 1)
            self.assertIn('no executed tests', result['finalization_error']['message'])

    def test_only_skipped_target_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), xml='<testsuite name="org.geotools.xml.Test" tests="2" failures="0" errors="0" skipped="2"><testcase classname="org.geotools.xml.Test" name="first"><skipped/></testcase><testcase classname="org.geotools.xml.Test" name="second"><skipped/></testcase></testsuite>')
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

    def test_source_verification_error_after_maven_success_fails_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_sha = compatibility.sha
            original_hashed = False

            def unreadable_after_execution(path):
                nonlocal original_hashed
                if path == root / 'output/work/source/pom.xml':
                    if original_hashed:
                        raise PermissionError('original source became unreadable')
                    original_hashed = True
                return original_sha(path)

            with patch('compatibility.sha', side_effect=unreadable_after_execution):
                result = self.fixture(root)
            self.assertEqual(result['exit_code'], 0)
            self.assertEqual(result['result_exit_code'], 1)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error']['type'], 'PermissionError')
            self.assertEqual(result['error']['message'], 'original source became unreadable')
            self.assertNotIn('changed_original_source_files', result)
            self.assertEqual(json.loads((root / 'output/result.json').read_text()), result)

    def test_native_failure_cannot_be_masked_by_zero_maven_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.fixture(Path(tmp), xml='<testsuite name="org.geotools.xml.Test" tests="2" failures="0" errors="1" skipped="0"><testcase classname="org.geotools.xml.Test" name="first"><error/></testcase><testcase classname="org.geotools.xml.Test" name="second"/></testsuite>')
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


class AggregateOAuthTests(unittest.TestCase):
    def sources(self, root):
        import oauth_fixture
        names = list(oauth_fixture.SOURCES)
        rows = []
        expected = {}
        for index, name in enumerate(names):
            before, after = 'diagnostic-' + str(index), 'redacted-' + str(index)
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(before)
            digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
            rows.append({'path': name, 'before_sha256': digest(before),
                         'after_sha256': digest(after), 'replacements': [[before, after]]})
            expected[name] = digest(before)
        name = oauth_fixture.MODULE + '/src/test/java/org/geoserver/security/oauth2/OAuth2RestTemplateTest.java'
        path = root / name
        path.parent.mkdir(parents=True)
        path.write_text('inherited-test')
        principal = [{'path': names[0], 'before_sha256': rows[0]['after_sha256'],
                      'after_sha256': digest('validated-principal'),
                      'replacements': [['redacted-0', 'validated-principal']]},
                     {'path': name, 'before_sha256': digest('inherited-test'),
                      'after_sha256': digest('changed-test'),
                      'replacements': [['inherited-test', 'changed-test']]}]
        return expected, {'oauth-redaction.json': rows, 'oauth-principal.json': principal}, path

    def test_main_repairs_are_ordered_and_inherited_tests_stay_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected, manifests, inherited_test = self.sources(root)
            with patch('oauth_fixture.SOURCES', expected), \
                 patch('oauth_fixture.repair_rows', side_effect=manifests.__getitem__):
                result = compatibility.prepare_webapp_oauth(root, principal=True)
            self.assertEqual([row['manifest'] for row in result['repairs']],
                             ['oauth-redaction.json', 'oauth-principal.json'])
            self.assertEqual([row['application_order'] for row in result['repairs']], [1, 2])
            self.assertEqual([len(row['sources']) for row in result['repairs']], [2, 1])
            self.assertEqual(inherited_test.read_text(), 'inherited-test')
            self.assertTrue(result['test_sources_unchanged'])
            self.assertEqual(result['injected_sources'], [])
            self.assertEqual(list(inherited_test.parent.iterdir()), [inherited_test])
            self.assertEqual((root / next(iter(expected))).read_text(), 'validated-principal')
            self.assertTrue(result['human_security_review_required'])
            self.assertFalse(result['acceptance_build'])

    def test_changed_original_source_prevents_all_repair_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected, manifests, _ = self.sources(root)
            names = list(expected)
            (root / names[1]).write_text('changed')
            with patch('oauth_fixture.SOURCES', expected), \
                 patch('oauth_fixture.repair_rows', side_effect=manifests.__getitem__), \
                 self.assertRaisesRegex(ValueError, 'exact inspected'):
                compatibility.prepare_webapp_oauth(root, principal=True)
            self.assertEqual((root / names[0]).read_text(), 'diagnostic-0')

    def test_unexpected_manifest_scope_prevents_all_repair_writes(self):
        for manifest in ('oauth-redaction.json', 'oauth-principal.json'):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                expected, manifests, _ = self.sources(root)
                manifests[manifest].append(dict(manifests[manifest][0]))
                with patch('oauth_fixture.SOURCES', expected), \
                     patch('oauth_fixture.repair_rows', side_effect=manifests.__getitem__), \
                     self.assertRaises(ValueError):
                    compatibility.prepare_webapp_oauth(root, principal=True)
                self.assertEqual((root / next(iter(expected))).read_text(), 'diagnostic-0')

    def test_packaging_repairs_reject_runtime_or_test_execution_modes_before_reserving_output(self):
        for target, stage, tests, runtime, redact, principal in (
                ('webapp', 'test', 'compile-only', False, True, True),
                ('webapp', 'package', 'target', False, True, True),
                ('webapp', 'package', 'compile-only', True, True, True),
                ('webapp', 'package', 'compile-only', False, False, True),
                ('xml', 'package', 'compile-only', False, True, False),
                ('oauth', 'package', 'compile-only', False, True, True)):
            with self.subTest(target=target, stage=stage, tests=tests, runtime=runtime), \
                 tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'not-reserved'
                with self.assertRaises(ValueError):
                    compatibility.probe(Path('/audit'), Path('/custody'), Path('/tc'), Path('/tools'),
                                        output, target, stage, tests=tests, runtime_http=runtime,
                                        oauth_redaction=redact, oauth_principal=principal)
                self.assertFalse(output.exists())


class ConfiguredDiagnosticModeTests(unittest.TestCase):
    def test_fixture_injection_and_repairs_are_limited_to_reviewed_modes(self):
        for options in (
                {'target': 'webapp', 'stage': 'package', 'tests': 'compile-only',
                 'configured_auth_diagnostic_tests': True},
                {'target': 'oauth', 'stage': 'test', 'tests': 'target',
                 'configured_auth_diagnostics': True},
                {'target': 'xml', 'stage': 'test', 'tests': 'target', 'runtime_http': True,
                 'configured_auth_diagnostics': True},
                {'target': 'webapp', 'stage': 'package', 'tests': 'compile-only',
                 'configured_auth_diagnostics': True, 'oauth_principal': False},
                {'target': 'webapp', 'stage': 'package', 'tests': 'all',
                 'configured_auth_diagnostics': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'not-reserved'
                parameters = {'oauth_redaction': True, 'oauth_principal': True, **options}
                with self.assertRaises(ValueError):
                    compatibility.probe(Path('/audit'), Path('/custody'), Path('/tc'), Path('/tools'),
                                        output, **parameters)
                self.assertFalse(output.exists())


class StatelessBearerModeTests(unittest.TestCase):
    def test_stateless_checks_require_complete_repairs_and_refuse_packaged_test_injection(self):
        for extra in ({'configured_auth_diagnostics': False},
                      {'oauth_principal': False},
                      {'oauth_redaction': False},
                      {'configured_auth_stateless_tests': True},
                      {'stage': 'test'},
                      {'tests': 'target'},
                      {'runtime_http': True}):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'not-reserved'
                options = {'target': 'webapp', 'stage': 'package', 'tests': 'compile-only',
                           'oauth_redaction': True, 'oauth_principal': True,
                           'configured_auth_diagnostics': True, 'configured_auth_stateless': True, **extra}
                with self.assertRaises(ValueError):
                    compatibility.probe(Path('/audit'), Path('/custody'), Path('/tc'), Path('/tools'), output, **options)
                self.assertFalse(output.exists())


class InjectedNativeEvidenceTests(unittest.TestCase):
    def result(self, expected=2, skipped=0, name='org.geoserver.security.oauth2.WitnessTest'):
        module = 'geoserver/src/community/security/oauth2-geonode'
        return {'native_tests': {'failures': 0, 'errors': 0, 'suites': [{
                    'name': name, 'path': module + '/target/surefire-reports/TEST-witness.xml',
                    'tests': 2, 'skipped': skipped}]},
                'configured_auth_stateless': {'native_test_count': expected, 'injected_sources': [
                    {'path': module + '/src/test/java/org/geoserver/security/oauth2/WitnessTest.java'}]}}

    def test_declared_injected_native_cases_must_actually_execute(self):
        result = self.result()
        compatibility.validate_execution(result, Path('/unused'), 'oauth', 'target')
        self.assertEqual(result['configured_auth_stateless']['native_executed_tests'], 2)
        for invalid in (self.result(expected=3), self.result(skipped=1),
                        self.result(name='org.geoserver.security.oauth2.UnrelatedTest')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                compatibility.validate_execution(invalid, Path('/unused'), 'oauth', 'target')


if __name__ == '__main__':
    unittest.main()
