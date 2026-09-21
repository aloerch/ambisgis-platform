import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('frontend_replay',Path(__file__).with_name('replay.py'))
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)

class FrozenReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'platform'
        for name in replay.COMPONENTS:
            p=self.source/'build-support'/name/'input.py';p.parent.mkdir(parents=True);p.write_text(name)
        self.target=self.root/'frozen'

    def test_frozen_copy_retains_actual_identity(self):
        expected=replay.freeze(self.source,self.target)
        replay.verify_frozen(self.target,expected)
        (self.source/'build-support/frontend/input.py').write_text('later mutable edit')
        replay.verify_frozen(self.target,expected)
        self.assertEqual((self.target/'build-support/frontend/input.py').read_text(),'frontend')

    def test_mutation_addition_and_removal_rejected(self):
        expected=replay.freeze(self.source,self.target)
        p=self.target/'build-support/frontend/input.py';original=p.read_text()
        p.write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):replay.verify_frozen(self.target,expected)
        p.write_text(original);extra=self.target/'unexpected';extra.write_text('x')
        with self.assertRaisesRegex(ValueError,'changed'):replay.verify_frozen(self.target,expected)
        extra.unlink();p.unlink()
        with self.assertRaisesRegex(ValueError,'changed'):replay.verify_frozen(self.target,expected)

    def test_reuse_preserves_prior_attempt(self):
        self.target.mkdir();p=self.target/'prior';p.write_text('evidence')
        with self.assertRaises(FileExistsError):replay.freeze(self.source,self.target)
        self.assertEqual(p.read_text(),'evidence')

    def test_source_and_snapshot_symlinks_rejected(self):
        p=self.source/'build-support/frontend/link';p.symlink_to('/etc/hosts')
        with self.assertRaisesRegex(ValueError,'symlink'):replay.freeze(self.source,self.target)
        p.unlink();link=self.target/'link';link.symlink_to('/etc/hosts')
        with self.assertRaisesRegex(ValueError,'symlink'):replay.inventory(self.target)

if __name__=='__main__':unittest.main()
