"""Meaningful negative guards for the sole inherited generated-source allowance."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

QGIS = Path(__file__).resolve().parents[2] / 'build-support/qgis'
sys.path.insert(0, str(QGIS))
import build as qgis_build
import reconcile
from common import inventory, sha


class GeneratedSourceGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'original.txt').write_text('retained source bytes')
        (self.source / 'generator.py').write_text('reviewed generator fixture')
        self.identities = {'generator.py': sha(self.source / 'generator.py')}
        self.patch = mock.patch.object(qgis_build, 'GENERATOR_IDENTITIES', self.identities)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.before = inventory(self.source)
        self.generated = self.source / qgis_build.GENERATED_SOURCE
        self.generated.parent.mkdir(parents=True)
        self.generated.write_text(json.dumps([{'name': str(i)} for i in range(307)]))

    def test_only_expected_regular_generated_file_is_allowed(self):
        result = qgis_build.verify_source_delta(self.source, self.before)
        self.assertEqual(result['original_files_verified'], 2)
        self.assertEqual(result['added'][0]['sha256'], sha(self.generated))

    def test_original_source_mutation_rejected(self):
        (self.source / 'original.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Original source'):
            qgis_build.verify_source_delta(self.source, self.before)

    def test_original_source_removal_rejected(self):
        (self.source / 'original.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'Original source'):
            qgis_build.verify_source_delta(self.source, self.before)

    def test_unexpected_generated_file_rejected(self):
        (self.source / 'extra.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Unexpected generated'):
            qgis_build.verify_source_delta(self.source, self.before)

    def test_generated_symlink_rejected(self):
        target = self.root / 'outside.json'
        target.write_bytes(self.generated.read_bytes())
        self.generated.unlink()
        self.generated.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            qgis_build.verify_source_delta(self.source, self.before)

    def test_unreviewed_generator_identity_rejected(self):
        self.identities['generator.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'generator identity'):
            qgis_build.verify_source_delta(self.source, self.before)

    def test_expected_path_cannot_hide_arbitrary_payload(self):
        self.generated.write_text('{"unexpected": true}')
        with self.assertRaisesRegex(ValueError, 'metadata structure'):
            qgis_build.verify_source_delta(self.source, self.before)

    def test_reproduction_must_match_source_bytes(self):
        output = self.root / 'audit'
        output.mkdir()
        def changed_result(command, cwd, env, destination, name):
            Path(command[-1]).write_text('different generator result')
        with mock.patch.object(qgis_build, 'run', side_effect=changed_result):
            with self.assertRaisesRegex(ValueError, 'Independent generated metadata differs'):
                qgis_build.reproduce_generated_source(self.source, self.before, self.root / 'prefix', {}, output)


class CompletedPhaseGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = 'compile'
        self.expected = ['cmake', '--build', 'selected-build']
        self.runner = self.root / 'offline_exec.py'
        self.runner.write_text('retained runner fixture')
        self.patch = mock.patch.dict(reconcile.EXECUTED_RECIPE_HASHES, {'offline_exec.py': sha(self.runner)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.log = self.root / 'compile.log'
        self.log.write_text('completed compile')
        self.command = {'argv': ['/usr/bin/python3', str(self.runner), '--evidence', str(self.root / 'compile-network.json'), '--', *self.expected],
                        'cwd': str(self.root), 'exit_code': 0, 'log_sha256': sha(self.log), 'environment': {}}
        self.proof = {'command': self.expected, 'status': 'completed', 'command_exit_code': 0,
                      'kernel_state': {'no_new_privs': 1, 'seccomp_mode': 2},
                      'probes': [{'family': family, 'passed': True} for family in ['AF_INET', 'AF_INET6', 'AF_UNIX', 'AF_UNIX']]}
        self.write_receipts()

    def write_receipts(self):
        (self.root / 'compile-command.json').write_text(json.dumps(self.command))
        (self.root / 'compile-network.json').write_text(json.dumps(self.proof))

    def test_completed_exact_phase_is_accepted(self):
        self.assertEqual(reconcile.verify_phase(self.root, self.name, self.expected)['log']['sha256'], sha(self.log))

    def test_failed_phase_rejected(self):
        self.command['exit_code'] = 1
        self.write_receipts()
        with self.assertRaisesRegex(ValueError, 'Failed phase'):
            reconcile.verify_phase(self.root, self.name, self.expected)

    def test_changed_phase_log_rejected(self):
        self.log.write_text('different evidence')
        with self.assertRaisesRegex(ValueError, 'changed phase log'):
            reconcile.verify_phase(self.root, self.name, self.expected)

    def test_failed_network_probe_rejected(self):
        self.proof['probes'][1]['passed'] = False
        self.write_receipts()
        with self.assertRaisesRegex(ValueError, 'network enforcement'):
            reconcile.verify_phase(self.root, self.name, self.expected)

    def test_substituted_phase_command_rejected(self):
        self.command['argv'][-1] = 'other-build'
        self.write_receipts()
        with self.assertRaisesRegex(ValueError, 'phase command'):
            reconcile.verify_phase(self.root, self.name, self.expected)


if __name__ == '__main__':
    unittest.main()
