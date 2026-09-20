"""Adversarial JavaCSV guard tests; fake native execution is not build evidence."""
import copy
import errno
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import javacsv_probe as subject
from javacsv_recovery import digest


def denial(command, exit_code=0):
    return {'status': 'completed', 'command': command, 'command_exit_code': exit_code,
            'kernel_state': {'no_new_privs': 1},
            'probes': [{'family': family, 'operation': 'socket(SOCK_STREAM)',
                        'passed': True, 'errno': errno.EPERM}
                       for family in ('AF_INET', 'AF_INET6')]}


class GuardTests(unittest.TestCase):
    def test_denial_rejects_incomplete_wrong_exit_and_wrong_command(self):
        for changes in ({'status': 'running'}, {'command_exit_code': 1},
                        {'command': ['other']}, {'kernel_state': {}}):
            data = denial(['java']); data.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                subject.verify_denial(data, ['java'], 0)

    def test_denial_requires_unique_successful_ipv4_and_ipv6_eperm(self):
        original = denial(['java'])
        invalid = []
        for family_index in (0, 1):
            data = copy.deepcopy(original); data['probes'].pop(family_index); invalid.append(data)
            for key, value in (('passed', False), ('errno', 0), ('errno', errno.EACCES)):
                data = copy.deepcopy(original); data['probes'][family_index][key] = value; invalid.append(data)
        data = copy.deepcopy(original); data['probes'].append(data['probes'][0]); invalid.append(data)
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                subject.verify_denial(data, ['java'], 0)
        subject.verify_denial(original, ['java'], 0)

    def test_environment_excludes_inherited_jvm_agents_and_credentials(self):
        with patch.dict(os.environ, {'JAVA_TOOL_OPTIONS': '-javaagent:tripwire',
                                     'JDK_JAVA_OPTIONS': '-javaagent:tripwire',
                                     'CLASSPATH': '/unreviewed', 'GITHUB_TOKEN': 'synthetic-fixture'}):
            self.assertEqual(subject.clean_environment(),
                             {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'})

    def test_source_guard_rejects_changed_bytes_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'A.java').write_bytes(b'original')
            with patch.dict(subject.SELECTED, {'A.java': ('1.0', digest(b'original'))}, clear=True):
                subject.verify_sources(root)
                (root/'A.java').write_bytes(b'changed')
                with self.assertRaises(ValueError): subject.verify_sources(root)
                (root/'A.java').unlink(); (root/'actual').write_bytes(b'original')
                (root/'A.java').symlink_to('actual')
                with self.assertRaises(ValueError): subject.verify_sources(root)

    def fixture(self, root):
        sources = root/'sources'; (sources/'src').mkdir(parents=True)
        (sources/'src/A.java').write_bytes(b'original')
        (sources/'src/Injected.java').write_bytes(b'unreviewed source must never compile')
        (sources/'recovery.json').write_text('{}')
        dependency = root/'dependency'; dependency.write_bytes(b'fixture')
        return sources, dependency

    def test_rejected_toolchain_never_executes_and_retains_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(subject.toolchain, 'verify_extracted', side_effect=ValueError('tampered toolchain')), \
                    patch.object(subject, 'execute') as execute:
                result = subject.probe(root/'sources', root/'jdk-17.0.20.1+1', root/'maven', root/'custody', root/'run')
            execute.assert_not_called()
            self.assertFalse(result['passed'])
            self.assertEqual(result['error']['message'], 'tampered toolchain')
            self.assertTrue((root/'run/result.json').exists())

    def run_fake(self, root, mode='pass'):
        sources, dependency = self.fixture(root)
        calls = []
        def execute(argv, cwd, env, output, timeout, termination_grace):
            calls.append(argv)
            self.assertEqual(env, subject.clean_environment())
            self.assertEqual(timeout, 12)
            self.assertEqual(termination_grace, 2)
            self.assertNotIn('Injected.java', ' '.join(argv))
            receipt = Path(argv[argv.index('--evidence') + 1])
            command = argv[argv.index('--') + 1:]
            if mode == 'timeout':
                output.write(b'timeout diagnostic\n'); output.flush()
                raise subprocess.TimeoutExpired(argv, timeout)
            data = denial(command)
            if mode == 'bad-denial': data['probes'][1]['errno'] = 0
            receipt.write_text(json.dumps(data))
            if mode == 'source-change': (sources/'src/A.java').write_bytes(b'changed')
            output.write(b'AMBISGIS_JUNIT_RESULT run=105 failures=0 ignored=0\n')
            return 0
        with patch.dict(subject.SELECTED, {'src/A.java': ('1.0', digest(b'original'))}, clear=True), \
                patch.object(subject.toolchain, 'verify_extracted', return_value={'verified': True}) as verify, \
                patch.object(subject, 'retained_jar', return_value=(dependency, {})), \
                patch.object(subject, 'execute', side_effect=execute):
            result = subject.probe(sources, root/'jdk-17.0.20.1+1', root/'maven', root/'custody', root/'run', timeout=12)
        verify.assert_called_once()
        self.assertEqual(verify.call_args.args[0], root/'custody')
        self.assertEqual(verify.call_args.args[2], root)
        return result, calls

    def test_clean_run_verifies_both_denial_receipts_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = self.run_fake(Path(tmp))
        self.assertTrue(result['passed'])
        self.assertEqual(len(calls), 2)
        self.assertTrue(result['original_sources_unchanged'])
        self.assertTrue(all(c['denial_verified'] for c in result['commands']))

    def test_bad_denial_or_changed_source_stops_before_native_tests(self):
        for mode in ('bad-denial', 'source-change'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                result, calls = self.run_fake(Path(tmp), mode)
                self.assertFalse(result['passed'])
                self.assertEqual(len(calls), 1)
                if mode == 'source-change': self.assertFalse(result['original_sources_unchanged'])

    def test_timeout_is_failed_and_keeps_command_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = self.run_fake(Path(tmp), 'timeout')
        self.assertFalse(result['passed'])
        self.assertEqual(result['error']['type'], 'TimeoutExpired')
        self.assertIn('log_sha256', result['commands'][0])
        self.assertEqual(len(calls), 1)


if __name__ == '__main__': unittest.main()
