import copy
import signal
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import importer_successor as candidate
import owned_successor as owned


class ImporterSelectionTests(unittest.TestCase):
    def valid(self):
        roots = copy.deepcopy(owned.SOURCES)
        # Synthetic identities exercise validation; these are not source receipts.
        roots['geoserver'].update(commit='a' * 40, tree='b' * 40)
        roots['geotools'].update(commit='c' * 40, tree='d' * 40)
        return {'schema_version': 1, 'predecessor': candidate.BASE, 'sources': roots,
                'retained_inputs_sha256': 'c' * 64}

    def test_exact_immutable_successor_shape(self):
        value = self.valid()
        self.assertEqual(value['sources'], candidate.selection(value))

    def test_unresolved_or_mutable_identity_refused(self):
        for invalid in (None, 'HEAD', 'a' * 39, 'A' * 40):
            with self.subTest(identity=invalid):
                value = self.valid()
                value['sources']['geoserver']['commit'] = invalid
                with self.assertRaises(ValueError):
                    candidate.selection(value)

    def test_unresolved_dependency_selection_refused(self):
        for invalid in (None, 'HEAD', 'a' * 63, 'A' * 64):
            value = self.valid()
            value['retained_inputs_sha256'] = invalid
            with self.subTest(identity=invalid), self.assertRaises(ValueError):
                candidate.selection(value)

    def test_repository_or_unchanged_root_drift_refused(self):
        for root, key, invalid in (('geoserver', 'repository_id', 1),
                                   ('geotools', 'repository_id', 1),
                                   ('geowebcache', 'tree', 'd' * 40)):
            with self.subTest(root=root, key=key):
                value = self.valid()
                value['sources'][root][key] = invalid
                with self.assertRaises(ValueError):
                    candidate.selection(value)

    def test_old_or_unexpected_selection_refused(self):
        values = [self.valid() for _ in range(5)]
        values[0]['sources']['geoserver']['commit'] = candidate.BASE
        values[1]['predecessor'] = 'e' * 40
        values[2]['sources']['additional-root'] = {}
        values[3]['sources']['geoserver']['fetch'] = True
        values[4]['sources']['geotools']['commit'] = owned.SOURCES['geotools']['commit']
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    candidate.selection(value)


class RetainedProcessIdentityTests(unittest.TestCase):
    def run_case(self, events, times):
        calls = []
        child = SimpleNamespace(pid=12345, wait=lambda **kw: calls.append(('wait', kw)) or 0)
        def observe(*args):
            calls.append(('observe', args))
            value = next(events)
            if isinstance(value, BaseException):
                raise value
            return value
        patches = (mock.patch.object(candidate.subprocess, 'Popen', return_value=child),
                   mock.patch.object(candidate.os, 'waitid', side_effect=observe),
                   mock.patch.object(candidate.os, 'killpg', side_effect=lambda *args: calls.append(('signal', args))),
                   mock.patch.object(candidate.time, 'monotonic', side_effect=times))
        return calls, patches

    def execute(self, patches):
        with patches[0] as popen, patches[1], patches[2], patches[3]:
            value = candidate.execute(['owned-test-command'], Path('/tmp'), {}, None, 1)
            self.assertTrue(popen.call_args.kwargs['start_new_session'])
            return value

    def test_normal_completion_reaps_without_signal(self):
        calls, patches = self.run_case(iter([SimpleNamespace(si_pid=12345)]), [0])
        self.assertEqual(0, self.execute(patches))
        self.assertEqual(['observe', 'wait'], [c[0] for c in calls])
        self.assertTrue(calls[0][1][-1] & candidate.os.WNOWAIT)

    def test_timeout_kills_group_before_reap_even_if_term_exits_leader(self):
        calls, patches = self.run_case(iter([None, SimpleNamespace(si_pid=12345)]), [0, 2, 3])
        with self.assertRaises(subprocess.TimeoutExpired):
            self.execute(patches)
        self.assertEqual(['observe', 'signal', 'observe', 'signal', 'wait'], [c[0] for c in calls])
        self.assertEqual((12345, signal.SIGTERM), calls[1][1])
        self.assertEqual((12345, signal.SIGKILL), calls[3][1])

    def test_lost_identity_never_signalled(self):
        for event in (ChildProcessError(), SimpleNamespace(si_pid=99999)):
            with self.subTest(event=event):
                calls, patches = self.run_case(iter([event]), [0])
                with self.assertRaises((ChildProcessError, RuntimeError)):
                    self.execute(patches)
                self.assertEqual(['observe'], [c[0] for c in calls])


class NativeCountTests(unittest.TestCase):
    def test_missing_or_skipped_lifecycle_cases_cannot_pass(self):
        for counts in ({'tests': 2, 'passed': 2, 'failures': 0, 'errors': 0, 'skipped': 0},
                       {'tests': 3, 'passed': 2, 'failures': 0, 'errors': 0, 'skipped': 1}):
            with self.subTest(counts=counts), tempfile.TemporaryDirectory() as root:
                p = Path(root)
                with mock.patch.object(owned, 'command', return_value=(['mvn', '-pl', 'old'], {})), \
                     mock.patch.object(owned, 'verify_network_receipt', return_value={}), \
                     mock.patch.object(owned, 'test_reports', return_value=counts):
                    with self.assertRaisesRegex(ValueError, 'test count'):
                        owned.native_tests(p, p, p, 10, module='org.geoserver.importer:gs-importer-core',
                                           selector='org.geoserver.importer.ImporterShutdownTest',
                                           expected_count=3, executor=lambda *args: 0)



class RetainedInputLockTests(unittest.TestCase):
    def test_incomplete_retained_selection_stops_before_native_command(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            here = root / 'java'
            here.mkdir()
            (here / 'toolchain-inputs.json').write_text('{"remaining_gaps": []}')
            offline = root / 'build-support/postgis/offline_exec.py'
            offline.parent.mkdir(parents=True)
            offline.write_text('# inert fixture; never executed')
            args = SimpleNamespace(output=root / 'out', recovered=root, geotools_repo=root,
                                   geoserver_repo=root, toolchain_custody=root, tools=root,
                                   custody=root, timeout=1)
            with (
                mock.patch.object(owned, 'HERE', here),
                mock.patch.object(owned, 'ROOT', root),
                mock.patch.object(owned, 'prepare_sources', return_value=({}, {})),
                mock.patch.object(owned.toolchain, 'verify_extracted', return_value={}),
                mock.patch.object(owned, 'materialize', return_value=[]),
                mock.patch.object(owned.variant_inputs, 'apply', return_value=([], {})),
                mock.patch.object(owned, 'command') as command,
                mock.patch('builtins.print'),
            ):
                executor = mock.Mock()
                code = owned.build(args, expected_retained_inputs_sha256='f' * 64, executor=executor)
            self.assertEqual(1, code)
            command.assert_not_called()
            executor.assert_not_called()
            result = candidate.json.loads((args.output / 'result.json').read_text())
            self.assertEqual('Retained input selection differs from the locked predecessor', result['error']['message'])
            self.assertNotIn('build_exit_code', result)


class SourceIdentityEnvironmentTests(unittest.TestCase):
    def test_parallel_reactor_is_refused_before_environment_change(self):
        for flag in ('-T', '-T4', '--threads', '--threads=4'):
            env = {'LANG': 'C.UTF-8'}
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'serial'):
                owned.configure_source_identity(['mvn', flag], env, Path('/source'))
            self.assertEqual({'LANG': 'C.UTF-8'}, env)

    def test_ambient_git_overrides_are_removed(self):
        command = ['mvn', 'package']
        env = {'GIT_DIR': '/unrelated', 'GIT_WORK_TREE': '/unrelated',
               'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.hooksPath',
               'GIT_CONFIG_VALUE_0': '/unrelated', 'LANG': 'C.UTF-8'}
        owned.configure_source_identity(command, env, Path('/source'))
        self.assertEqual('C.UTF-8', env['LANG'])
        self.assertEqual('/source', env['GIT_CEILING_DIRECTORIES'])
        self.assertEqual('/dev/null', env['GIT_CONFIG_GLOBAL'])
        self.assertEqual('file', env['GIT_ALLOW_PROTOCOL'])
        self.assertNotIn('GIT_DIR', env)
        self.assertNotIn('GIT_CONFIG_COUNT', env)
        self.assertIn('-Dgit.commit.runOnlyOnce=false', command)
