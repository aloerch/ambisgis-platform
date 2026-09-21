"""Guards for evidence handling. These are not QGIS native acceptance tests."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from unittest import mock
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

    def xml_config(self):
        prefix = self.root / 'selected-xml'
        (prefix / 'lib').mkdir(parents=True, exist_ok=True)
        (prefix / 'lib/libxml2.so').write_text('selected XML fixture')
        return {'xml_prefix': str(prefix), 'database_prefix': str(self.root / 'original-native')}

    def test_xml_prefix_is_mandatory_and_cannot_escape_to_original(self):
        config = self.xml_config()
        for value in (None, 'relative-xml', config['database_prefix']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_tests.selected_xml_prefix(dict(config, xml_prefix=value))
        outside = self.root / 'host-xml.so'
        outside.write_text('host fallback fixture')
        library = Path(config['xml_prefix']) / 'lib/libxml2.so'
        library.unlink()
        library.symlink_to(outside)
        with self.assertRaises(ValueError):
            native_tests.selected_xml_prefix(config)

    def test_xml_origin_refuses_old_fallback_and_duplicate_mapping(self):
        config = self.xml_config()
        selected = str(Path(config['xml_prefix']) / 'lib/libxml2.so.16.0.6')
        old = str(Path(config['database_prefix']) / 'lib/libxml2.so.16.0.6')
        native_tests.check_xml_origin(config, [selected, selected])
        for maps in ([], [old], [selected, old], [selected, '/usr/lib64/libxml2.so.2']):
            with self.subTest(maps=maps), self.assertRaises(ValueError):
                native_tests.check_xml_origin(config, maps)

    def test_native_environment_prioritizes_selected_xml_over_old_native(self):
        config = dict(self.xml_config(), qgis_build=str(self.root / 'build'),
                      qgis_source=str(self.root / 'source'), spatial_prefix=str(self.root / 'spatial'),
                      python=sys.executable, pg_service_file=str(self.root / 'service.conf'),
                      qt_plugins=str(self.root / 'qt-plugins'), python_paths=[],
                      library_paths=[str(self.root / 'original-native/lib')])
        output = self.root / 'output'; output.mkdir()
        env = native_tests.native_environment(config, output)
        self.assertEqual(env['LD_LIBRARY_PATH'].split(':')[:4],
                         [str(self.root / 'build/output/lib'),
                          str(self.root / 'selected-xml/lib'), str(self.root / 'selected-xml/lib64'),
                          str(self.root / 'original-native/lib')])

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


class NativeSupervisorCleanupGuards(unittest.TestCase):
    """Real process tests of graceful supervisor shutdown, plus DB ordering."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def start_surrogate(self):
        # Models the existing supervisor's SIGTERM/finally/reap contract. Its
        # child deliberately ignores SIGTERM, so SIGKILLing the supervisor
        # (subprocess.run's timeout behavior) cannot pass these checks.
        script = self.root / 'supervisor.py'
        script.write_text("""import os, signal, subprocess, sys, time
from pathlib import Path
root=Path(sys.argv[1])
def interrupted(signum, frame):
    raise InterruptedError('controlled stop')
signal.signal(signal.SIGTERM, interrupted)
child=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'])
(root/'child.pid').write_text(str(child.pid))
try:
    while True: time.sleep(.02)
except InterruptedError:
    pass
finally:
    child.kill()
    child.wait(timeout=5)
    (root/'reaped').write_text(str(child.pid))
""")
        process = subprocess.Popen([sys.executable, str(script), str(self.root)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.cleanup_surrogate, process)
        deadline = time.monotonic() + 5
        while not (self.root / 'child.pid').exists():
            if process.poll() is not None or time.monotonic() > deadline:
                self.fail('surrogate did not start its owned child')
            time.sleep(.01)
        return process

    def cleanup_surrogate(self, process):
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        if (self.root / 'reaped').exists():
            return
        path = self.root / 'child.pid'
        if path.exists():
            try:
                os.kill(int(path.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass

    def assert_reaped(self, process):
        self.assertIsNotNone(process.poll())
        child = int((self.root / 'child.pid').read_text())
        self.assertEqual((self.root / 'reaped').read_text(), str(child))
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_timeout_allows_supervisor_to_reap_real_child(self):
        process = self.start_surrogate()
        with self.assertRaises(subprocess.TimeoutExpired):
            native_database.wait_supervisor(process, timeout=.05, cleanup_timeout=5)
        self.assert_reaped(process)

    def test_keyboard_interrupt_allows_supervisor_to_reap_real_child(self):
        process = self.start_surrogate()
        timer = threading.Timer(.05, lambda: os.kill(os.getpid(), signal.SIGINT))
        try:
            with self.assertRaises(KeyboardInterrupt):
                timer.start()
                native_database.wait_supervisor(process, timeout=5, cleanup_timeout=5)
        finally:
            timer.cancel()
            timer.join()
        self.assert_reaped(process)

    def test_interrupted_controller_records_failure_after_supervisor_then_db_cleanup(self):
        calls = []
        process = mock.Mock(pid=123, returncode=None)
        process.poll.side_effect = lambda: process.returncode

        def wait(timeout):
            if not calls:
                calls.append('interrupted')
                raise KeyboardInterrupt('fixture interruption')
            calls.append('supervisor-reaped')
            process.returncode = 125
            return 125

        process.wait.side_effect = wait
        process.terminate.side_effect = lambda: calls.append('supervisor-terminate')
        database = mock.Mock()
        database.receipt = {'started': True, 'stopped': False, 'result_exit_code': 0}

        def invalidate(*args):
            self.assertIsNotNone(process.returncode)
            calls.append('credentials-invalidated')

        def stop():
            self.assertIsNotNone(process.returncode)
            calls.append('database-stopped')
            database.receipt['stopped'] = True

        database.sql.side_effect = invalidate
        database.stop.side_effect = stop
        config = dict(qgis_source='unused', database_prefix='unused', database_evidence='unused')
        with mock.patch.object(native_tests, 'load_selection', return_value={}), \
             mock.patch.object(native_database.configured_auth_database, 'start', return_value=database), \
             mock.patch.object(native_database, 'prepare', return_value={}), \
             mock.patch.object(native_database.subprocess, 'Popen', return_value=process):
            result = native_database.run(config, self.root / 'attempt')
        self.assertEqual(result, 1)
        self.assertEqual(calls, ['interrupted', 'supervisor-terminate', 'supervisor-reaped',
                                 'credentials-invalidated', 'database-stopped'])
        receipt = json.loads((self.root / 'attempt/result.json').read_text())
        self.assertEqual(receipt['error']['type'], 'KeyboardInterrupt')
        self.assertTrue(receipt['supervisor_stopped'])
        self.assertTrue(receipt['credentials_invalidated'])
        self.assertTrue(receipt['database']['stopped'])


if __name__ == '__main__':
    unittest.main()
