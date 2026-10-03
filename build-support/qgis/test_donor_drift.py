from pathlib import Path
import tempfile
import unittest

import donor_drift


class DonorDriftGuards(unittest.TestCase):
    def test_real_local_positive_control_and_replay_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'fixture'
            before = donor_drift.prepare(root)
            self.assertEqual(before,donor_drift.snapshot(root))
            after = donor_drift.mutate(root)
            self.assertTrue(after['floating_positive_control']['changed'])
            self.assertNotEqual(before['floating']['source_sha256'],
                                after['fixture_after']['floating']['source_sha256'])
            with self.assertRaises(ValueError): donor_drift.mutate(root)

    def test_modified_fixture_and_real_remote_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'fixture'
            donor_drift.prepare(root)
            donor_drift.git(root,'remote','add','unexpected','https://example.invalid/donor.git')
            with self.assertRaisesRegex(ValueError,'remote'):
                donor_drift.mutate(root)

    def test_existing_path_never_adopted(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'fresh'):
                donor_drift.prepare(Path(directory))

    def test_final_transition_preserves_original_receipts_and_rejects_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'fixture'
            donor_drift.prepare(root)
            donor_drift.mutate(root)
            names=('before.json','after.json','drift.json','api-before.json')
            originals={name:(root/name).read_bytes() for name in names}
            final=donor_drift.advance(root)
            self.assertEqual(final['baseline_receipt'],str(root/'after.json'))
            self.assertEqual(final['fixture_before']['floating']['api_schema'],2)
            self.assertEqual(final['fixture_after']['floating']['api_schema'],3)
            self.assertTrue(final['floating_positive_control']['changed'])
            self.assertEqual(originals,{name:(root/name).read_bytes() for name in names})
            with self.assertRaisesRegex(ValueError,'final drift already applied'):
                donor_drift.advance(root)


if __name__ == '__main__':
    unittest.main()
