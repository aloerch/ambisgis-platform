"""Guards for evidence handling. These are not QGIS native acceptance tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import native_database
import native_tests


class NativeEvidenceGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def qtest(self, body, methods=('read',)):
        path = self.root / 'report.xml'
        path.write_text('<TestCase>' + body + '</TestCase>')
        return native_tests.parse_qtest(path, methods)

    def test_cpp_zero_selected_assertions_is_failure(self):
        result = self.qtest('<TestFunction name="initTestCase"><Incident type="pass"/></TestFunction>')
        self.assertEqual(result['result_exit_code'], 1)
        self.assertEqual(result['passed_cases'], 0)

    def test_cpp_selected_skip_is_failure_and_preserved(self):
        result = self.qtest('<TestFunction name="read"><Incident type="skip"><DataTag>a</DataTag></Incident></TestFunction>')
        self.assertEqual(result['result_exit_code'], 1)
        self.assertEqual(result['nonpassing'][0]['type'], 'skip')

    def test_cpp_failed_setup_cannot_be_hidden_by_passing_method(self):
        result = self.qtest('<TestFunction name="initTestCase"><Incident type="fail"/></TestFunction><TestFunction name="read"><Incident type="pass"/></TestFunction>')
        self.assertEqual(result['result_exit_code'], 1)

    def test_cpp_discovery_must_match_selection(self):
        result = self.qtest('<TestFunction name="another"><Incident type="pass"/></TestFunction>')
        self.assertEqual(result['result_exit_code'], 1)
        self.assertEqual(result['nonpassing'][0]['missing'], ['read'])

    def test_cpp_data_rows_are_counted_without_setup(self):
        result = self.qtest('<TestFunction name="initTestCase"><Incident type="pass"/></TestFunction><TestFunction name="read"><Incident type="pass"><DataTag>one</DataTag></Incident><Incident type="pass"><DataTag>two</DataTag></Incident></TestFunction>')
        self.assertEqual(result['result_exit_code'], 0)
        self.assertEqual(result['passed_cases'], 2)

    def test_python_zero_or_skipped_or_incomplete_run_is_failure(self):
        valid = dict(selected_count=2, tests_run=2, successes=2, failures=0, errors=0,
                     skips=[], expected_failures=0, unexpected_successes=0)
        self.assertTrue(native_tests.check_python_result(valid, 2))
        for changes, count in [(dict(selected_count=0, tests_run=0, successes=0), 0),
                               (dict(skips=[{'test': 'one', 'reason': 'missing DB'}]), 2),
                               (dict(tests_run=1), 2), (dict(successes=1), 2),
                               (dict(failures=1), 2), (dict(errors=1), 2),
                               (dict(expected_failures=1), 2)]:
            with self.subTest(changes=changes):
                self.assertFalse(native_tests.check_python_result(dict(valid, **changes), count))

    def service(self, **changes):
        values = dict(host='127.0.0.1', dbname='qgis_native', user='qgis_native_reader',
                      sslmode='disable', connect_timeout='5')
        values.update(changes)
        path = self.root / 'service.conf'
        path.write_text('[qgis_test]\n' + '\n'.join(k + '=' + v for k, v in values.items()) + '\n')
        path.chmod(0o600)
        return path

    def test_service_refuses_other_database_or_nonloopback(self):
        native_tests.check_service(self.service())
        for changes in [dict(dbname='postgres'), dict(host='example.com'), dict(user='fixture_owner')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                native_tests.check_service(self.service(**changes))

    def test_service_refuses_public_or_symlink_file(self):
        path = self.service()
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            native_tests.check_service(path)
        path.chmod(0o600)
        link = self.root / 'service-link.conf'
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            native_tests.check_service(link)

    def test_empty_manifest_never_counts_as_native_success(self):
        path = self.root / 'selection.json'
        path.write_text(json.dumps(dict(schema=1, cpp=[], python=[])))
        with self.assertRaises(ValueError):
            native_tests.load_selection(self.root, path)

    def fixture(self, contents):
        path = self.root / 'fixture.sql'
        path.write_text(contents)
        return {'database_fixture': {'source': 'fixture.sql', 'start_marker': '--- start', 'end_marker': '-- end'},
                'source_sha256': {'fixture.sql': hashlib.sha256(contents.encode()).hexdigest()}}

    def test_fixture_extracts_exact_statements_and_rejects_tampering(self):
        contents = 'ignored\n--- start\nCREATE TABLE a(x int);\nCREATE TABLE b(x int);\n-- end\nignored'
        selection = self.fixture(contents)
        self.assertEqual(native_database.fixture_sql(self.root, selection), '--- start\nCREATE TABLE a(x int);\nCREATE TABLE b(x int);\n')
        (self.root / 'fixture.sql').write_text(contents.replace('x int', 'x text'))
        with self.assertRaises(ValueError):
            native_database.fixture_sql(self.root, selection)

    def test_fixture_refuses_extra_tables_and_ambiguous_markers(self):
        for text in ['--- start\nCREATE TABLE a(x int);\nCREATE TABLE b(x int);\nCREATE TABLE c(x int);\n-- end',
                     '--- start\n--- start\nCREATE TABLE a(x int);\nCREATE TABLE b(x int);\n-- end']:
            selection = self.fixture(text)
            with self.assertRaises(ValueError):
                native_database.fixture_sql(self.root, selection)


if __name__ == '__main__':
    unittest.main()
