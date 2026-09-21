"""HTTP-evidence false-positive regressions, separate from actual servlet tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import configured_auth_evidence as evidence
import configured_auth_probe as probe


def feature(marker='PRIVATE_WITNESS'):
    return {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [1, 2]}, 'properties': {'label': marker}}]}


class ContentEvidenceTests(unittest.TestCase):
    def test_positive_control_requires_actual_point_and_exact_label(self):
        for marker in ('PUBLIC_WITNESS', 'PRIVATE_WITNESS'):
            self.assertTrue(evidence.validate_geojson(json.dumps(feature(marker)), marker))

    def test_echoes_empty_features_null_geometry_and_wrong_points_fail(self):
        invalid = ['PRIVATE_WITNESS', '<Exception>PRIVATE_WITNESS</Exception>',
                   {'type': 'FeatureCollection', 'features': [], 'message': 'PRIVATE_WITNESS'}]
        for change in ('null', 'wrong-coordinate', 'wrong-label', 'boolean-coordinate', 'duplicate-feature', 'wrong-type'):
            document = feature()
            item = document['features'][0]
            if change == 'null': item['geometry'] = None
            elif change == 'wrong-coordinate': item['geometry']['coordinates'] = [2, 1]
            elif change == 'wrong-label': item['properties']['label'] = 'PUBLIC_WITNESS'
            elif change == 'boolean-coordinate': item['geometry']['coordinates'] = [True, 2]
            elif change == 'duplicate-feature': document['features'].append(copy.deepcopy(item))
            elif change == 'wrong-type': item['type'] = 'Point'
            invalid.append(document)
        for document in invalid:
            with self.subTest(document=document):
                body = document if isinstance(document, str) else json.dumps(document)
                self.assertFalse(evidence.validate_geojson(body, 'PRIVATE_WITNESS'))

    def test_duplicate_json_members_and_nonfinite_numbers_fail(self):
        good = json.dumps(feature())
        for body in (good.replace('"label": "PRIVATE_WITNESS"', '"label": "OTHER", "label": "PRIVATE_WITNESS"'),
                     good.replace('[1, 2]', '[NaN, 2]')):
            self.assertFalse(evidence.validate_geojson(body, 'PRIVATE_WITNESS'))


class ReceiptEvidenceTests(unittest.TestCase):
    def test_recursive_redaction_includes_exception_messages_keys_and_overlapping_values(self):
        raw = {'error': {'message': 'Bearer fixture-token fixture-token'},
               'fixture-token': ['Basic fixture-basic', 'fixture-basic'], 'unchanged': True}
        sanitized, count = evidence.redact(raw, ['fixture-token', 'Basic fixture-basic', 'fixture-basic'])
        self.assertEqual(count, 5)
        self.assertNotIn('fixture-token', json.dumps(sanitized))
        self.assertNotIn('fixture-basic', json.dumps(sanitized))
        self.assertTrue(sanitized['unchanged'])
        self.assertIn('fixture-token', raw)

    def test_final_report_redaction_overrides_a_successful_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            result = evidence.finalize_report({'result_exit_code': 0, 'error': {'message': 'fixture-token'}},
                                              path, ['fixture-token'])
            self.assertEqual(result['result_exit_code'], 1)
            self.assertEqual(result['receipt_secret_redactions'], 1)
            self.assertNotIn('fixture-token', path.read_text())
            self.assertEqual(json.loads(path.read_text()), result)

    def test_cleanup_or_capture_failure_cannot_leave_success(self):
        for failure in ({'cleanup': {'round': {'log_reader_stopped': False}}},
                        {'cleanup': {'forced_kill': True}},
                        {'cleanup_errors': ['scrub failed']},
                        {'capture_errors': ['reader failed']},
                        {'finalization_errors': ['WAR unreadable']},
                        {'error': {'type': 'RuntimeError', 'message': 'failure'}}):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                result = evidence.finalize_report({'result_exit_code': 0, **failure}, Path(tmp) / 'result.json', [])
                self.assertEqual(result['result_exit_code'], 1)

    def test_reported_leaks_failed_cases_or_missing_capture_override_success(self):
        for evidence_failure in ({'diagnostic_leaks': [{'count': 1}]},
                                 {'response_leaks': [{'count': 1}]},
                                 {'residual_secret_files_redacted': ['runtime.log']},
                                 {'protocol': {'violations': ['unexpected-protocol']}},
                                 {'scenario_results': []},
                                 {'scenario_results': [{'case': 'denial', 'passed': False}]},
                                 {'logger_capture_controls': {}},
                                 {'logger_capture_controls': {'configured': 0, 'restart': 1}}):
            with self.subTest(evidence_failure=evidence_failure), tempfile.TemporaryDirectory() as tmp:
                result = evidence.finalize_report({'result_exit_code': 0, **evidence_failure},
                                                  Path(tmp) / 'result.json', [])
                self.assertEqual(result['result_exit_code'], 1)

    def test_success_is_preserved_only_without_evidence_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = evidence.finalize_report({'result_exit_code': 0, 'cleanup': {'identity_stopped': True}},
                                              Path(tmp) / 'result.json', [])
            self.assertEqual(result['result_exit_code'], 0)
            self.assertEqual(result['receipt_secret_redactions'], 0)

    def test_receipt_write_failure_propagates_and_existing_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            path.write_text('retained-failure')
            with self.assertRaises(FileExistsError):
                evidence.finalize_report({'result_exit_code': 0}, path, [])
            self.assertEqual(path.read_text(), 'retained-failure')


class MatrixEvidenceTests(unittest.TestCase):
    def request(self, status, body, headers=(), expected=(200,), contains=None):
        identity = Mock()
        identity.calls = []
        identity.sensitive.return_value = ['fixture-sensitive-token']
        response = Mock(status=status)
        response.read.return_value = body.encode()
        response.getheaders.return_value = list(headers)
        response.getheader.side_effect = lambda name, default=None: next((value for key, value in headers if key.lower() == name.lower()), default)
        connection = Mock()
        connection.getresponse.return_value = response
        matrix = probe.Matrix(1, identity)
        matrix.request('review-control', '/wfs', connection=connection,
                       expected=expected, contains=contains, excludes=())
        return matrix

    def test_server_error_and_login_form_are_not_authorization_denial(self):
        for status, body in ((500, 'error'), (403, '<form>login</form>')):
            with self.subTest(status=status):
                matrix = self.request(status, body, expected=(401,403,404))
                self.assertFalse(matrix.rows[-1]['passed'])

    def test_response_secret_fails_without_retaining_the_secret(self):
        matrix = self.request(403, 'fixture-sensitive-token', expected=(401,403,404))
        self.assertFalse(matrix.rows[-1]['passed'])
        self.assertTrue(matrix.leaks)
        self.assertNotIn('fixture-sensitive-token', json.dumps(matrix.rows))

    def test_earlier_duplicate_header_secret_and_redirect_cannot_be_hidden(self):
        matrix = self.request(403, 'denied', headers=(('Set-Cookie', 'fixture-sensitive-token'),
                                                    ('set-cookie', 'innocent')), expected=(401,403,404))
        self.assertFalse(matrix.rows[-1]['passed'])
        self.assertTrue(matrix.leaks)
        self.assertEqual(matrix.rows[-1]['set_cookie_header_count'], 2)
        self.assertNotIn('fixture-sensitive-token', json.dumps(matrix.rows))
        matrix = self.request(200, json.dumps(feature()), headers=(('Location','/login'), ('location','')),
                              contains='PRIVATE_WITNESS')
        self.assertFalse(matrix.rows[-1]['passed'])

    def test_marker_echo_is_not_a_positive_gis_read(self):
        matrix = self.request(200, '<Exception>PRIVATE_WITNESS</Exception>', contains='PRIVATE_WITNESS')
        self.assertFalse(matrix.rows[-1]['passed'])

    def test_lowercase_redirect_header_cannot_be_mistaken_for_positive_data(self):
        matrix = self.request(200, json.dumps(feature()), headers=(('location','/login'),), contains='PRIVATE_WITNESS')
        self.assertFalse(matrix.rows[-1]['passed'])


class ChildFinalizationTests(unittest.TestCase):
    def fixture(self, root):
        identity = Mock()
        identity.client = 'fixture-client'
        identity.secret = 'ephemeral-sensitive-test-token'
        identity.server.server_port = 1
        identity.calls = []
        identity.violations = []
        identity.extra_sensitive = []
        identity.sensitive.return_value = [identity.secret]
        war = root / 'input.war'
        war.write_bytes(b'controlled-fixture-war')
        out = root / 'evidence'
        out.mkdir()
        database_properties = root / 'database.properties'
        database_properties.write_text('geofenceDataSource.password=mock-database-value\n')
        config = {'output': str(out), 'source': str(root / 'source'), 'war': str(war),
                  'war_sha256': probe.digest(war), 'java': '/fixture/java/bin/java',
                  'servlet': str(root / 'servlet'), 'launcher': str(root / 'launcher'),
                  'database_properties': str(database_properties)}
        return identity, config, out

    def test_exception_diagnostic_is_redacted_before_final_receipt_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity, config, out = self.fixture(Path(tmp))
            with patch('configured_auth_probe.Identity', return_value=identity), \
                 patch('configured_auth_fixture.prepare', side_effect=RuntimeError(identity.secret)):
                self.assertEqual(probe.child(config), 1)
            stored = (out / 'http-result.json').read_text()
            self.assertNotIn(identity.secret, stored)
            self.assertEqual(json.loads(stored)['result_exit_code'], 1)
            identity.close.assert_called_once()

    def test_scrub_error_still_retains_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity, config, out = self.fixture(Path(tmp))
            def prepare(*args, **kwargs):
                (out / 'data/geofence').mkdir(parents=True)
                return {'files': []}
            with patch('configured_auth_probe.Identity', return_value=identity), \
                 patch('configured_auth_fixture.prepare', side_effect=prepare), \
                 patch('runtime_inputs.launcher_command', return_value=['fixture-java']), \
                 patch('configured_auth_probe.subprocess.Popen', side_effect=RuntimeError('startup failed')), \
                 patch('configured_auth_fixture.scrub_secrets', side_effect=OSError('scrub unavailable')):
                self.assertEqual(probe.child(config), 1)
            self.assertEqual(json.loads((out / 'http-result.json').read_text())['result_exit_code'], 1)

    def test_war_digest_error_still_retains_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity, config, out = self.fixture(Path(tmp))
            with patch('configured_auth_probe.Identity', return_value=identity), \
                 patch('configured_auth_fixture.prepare', side_effect=RuntimeError('setup failed')), \
                 patch('configured_auth_probe.digest', side_effect=OSError('WAR unavailable')):
                self.assertEqual(probe.child(config), 1)
            self.assertEqual(json.loads((out / 'http-result.json').read_text())['result_exit_code'], 1)

    def test_capture_reader_failure_cannot_leave_success_after_positive_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity, config, out = self.fixture(Path(tmp))
            rounds = iter(('configured', 'restart'))
            class BrokenStream:
                def __iter__(self):
                    yield 'AMBISGIS_CONFIGURED_OAUTH_LOG_CAPTURE_CONTROL\n'
                    yield 'AMBISGIS_CONFIGURED_CACHE_LOG_CAPTURE_CONTROL\n'
                    raise OSError('capture reader failed')
            def prepare(*args, **kwargs):
                (out / 'data/geofence').mkdir(parents=True)
                return {'files': []}
            def launch(*args, **kwargs):
                directory = out / next(rounds)
                directory.mkdir()
                (directory / 'ready.json').write_text(json.dumps({'port': 1, 'security_configuration': {
                    'role_source': 'UserGroupService', 'user_group_service': 'fixture'}}))
                (directory / 'requests.jsonl').write_text(''.join(json.dumps({'case': 'sequential-' + str(index),
                    'thread': 'fixture-worker', 'status': 200 if index % 2 else 403}) + '\n' for index in range(32)))
                process = Mock()
                process.stdout = BrokenStream()
                process.poll.return_value = 0
                process.wait.return_value = 0
                return process
            def exercise(matrix, fixture, restart=False):
                matrix.rows.append({'case': 'positive-control', 'passed': True})
            with patch('configured_auth_probe.Identity', return_value=identity), \
                 patch('configured_auth_fixture.prepare', side_effect=prepare), \
                 patch('configured_auth_fixture.scrub_secrets', return_value=[]), \
                 patch('runtime_inputs.launcher_command', return_value=['fixture-java']), \
                 patch('configured_auth_probe.subprocess.Popen', side_effect=launch) as launched, \
                 patch('configured_auth_probe.exercise', side_effect=exercise), \
                 patch('threading.excepthook'):
                code = probe.child(config)
                self.assertGreater(launched.call_count, 0)
                self.assertIn('AMBISGIS_CONFIGURED_OAUTH_LOG_CAPTURE_CONTROL', (out / 'configured-runtime.log').read_text())
                self.assertEqual(code, 1)
            report = json.loads((out / 'http-result.json').read_text())
            self.assertEqual(report['result_exit_code'], 1)
            self.assertTrue(report['capture_errors'])
            self.assertNotIn('error', report)


if __name__ == '__main__':
    unittest.main()
