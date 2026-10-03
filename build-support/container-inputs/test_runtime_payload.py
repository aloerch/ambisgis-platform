# SPDX-License-Identifier: GPL-3.0-or-later
"""Adversarial guards for inert runtime selection; no package code executes."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('runtime_payload', Path(__file__).with_name('runtime_payload.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RuntimePayloadGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pkg = self.root / 'payload'
        self.pkg.mkdir()
        source = self.pkg / 'usr/bin/fixture'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'inert executable bytes\n')
        source.chmod(0o600)
        self.row = {'path': 'usr/bin/fixture', 'kind': 'file', 'signed_mode': '0o100755',
                    'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        self.receipts = [{'packages': [{'identity': {'name': 'fixture'}, 'directory': str(self.pkg),
                                       'archive_sha256': 'a' * 64, 'files': [self.row]}]}]
        self.plan = patch.object(MODULE, 'selection', return_value={'usr/bin/fixture': 'runtime/bin/fixture'})
        self.plan.start()

    def tearDown(self):
        self.plan.stop()
        self.tmp.cleanup()

    def test_real_payload_is_inert_and_replay_does_not_overwrite(self):
        output = self.root / 'out'
        result = MODULE.materialize(self.receipts, output)
        self.assertFalse(result['runtime_executed'])
        self.assertEqual((output / 'runtime/bin/fixture').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            MODULE.materialize(self.receipts, output)
        self.assertEqual((output / 'runtime/bin/fixture').read_bytes(), b'inert executable bytes\n')

    def test_changed_source_rejected_before_output(self):
        (self.pkg / 'usr/bin/fixture').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            MODULE.materialize(self.receipts, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_actual_source_parent_link_cannot_read_outside_payload(self):
        original = self.pkg / 'usr'
        original.rename(self.root / 'outside')
        original.symlink_to(self.root / 'outside', target_is_directory=True)
        with self.assertRaises(ValueError):
            MODULE.materialize(self.receipts, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_actual_output_parent_link_cannot_write_outside(self):
        outside = self.root / 'outside'
        outside.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            MODULE.materialize(self.receipts, alias / 'out')
        self.assertEqual(list(outside.iterdir()), [])

    def test_conflicting_signed_members_are_not_order_dependent(self):
        import copy
        extra = copy.deepcopy(self.receipts[0])
        extra['packages'][0]['files'][0]['sha256'] = 'b' * 64
        for entries in [self.receipts + [extra], [extra] + self.receipts]:
            with self.assertRaises(ValueError):
                MODULE.catalog(entries)

    def test_signed_link_escape_and_cycle_are_rejected(self):
        for target in ['../../outside', 'loop']:
            entries = {'loop': {'row': {'kind': 'symlink', 'target': target},
                                'package': {'name': 'fixture'}, 'archive_sha256': 'a' * 64}}
            with self.assertRaises(ValueError):
                MODULE.resolve(entries, 'loop')


if __name__ == '__main__':
    unittest.main()
