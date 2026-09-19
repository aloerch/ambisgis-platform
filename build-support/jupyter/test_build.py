import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('jupyter_build',Path(__file__).with_name('build.py'))
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)


class RetainedBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.c=self.root/'custody';self.c.mkdir()
        self.m={'roots':[],'files':[]}
        for name in ['build-requirements.txt','hub-requirements.txt','user-requirements.txt','proxy-package.json','proxy-package-lock.json','wheels/retained.whl']:
            p=self.c/name;p.parent.mkdir(exist_ok=True);p.write_bytes(name.encode())
            self.m['files'].append({'path':name,'size':p.stat().st_size,'sha256':build.digest(p)})

    def test_unlisted_wheel_cannot_enter_consumed_store(self):
        (self.c/'wheels/unlisted.whl').write_bytes(b'unselected package')
        build.verify(self.c,self.m)
        build.copy_verified(self.c,self.root/'selected',self.m,'wheels')
        self.assertEqual([p.name for p in (self.root/'selected').iterdir()],['retained.whl'])

    def test_changed_retained_wheel_fails_before_build(self):
        (self.c/'wheels/retained.whl').write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError,'mismatch'):build.verify(self.c,self.m)

    def test_root_must_match_verified_digest(self):
        self.m['roots']=[{'path':'wheels/retained.whl','sha256':'0'*64}]
        with self.assertRaisesRegex(ValueError,'root is not'):build.verify(self.c,self.m)

    def test_missing_lock_cannot_be_consumed(self):
        self.m['files']=self.m['files'][1:]
        with self.assertRaisesRegex(ValueError,'required lock'):build.verify(self.c,self.m)

    def test_path_traversal_and_duplicates_fail(self):
        for path in ['../escape','/absolute','build-requirements.txt']:
            with self.subTest(path=path):
                manifest=copy.deepcopy(self.m);manifest['files'].append({'path':path})
                with self.assertRaisesRegex(ValueError,'unsafe or duplicate'):build.verify(self.c,manifest)

    def test_symlink_cannot_stand_in_for_input(self):
        p=self.c/'wheels/retained.whl';p.unlink();p.symlink_to(self.c/'hub-requirements.txt')
        with self.assertRaisesRegex(ValueError,'unsafe or missing'):build.verify(self.c,self.m)

    def test_copy_detects_input_changed_after_verify(self):
        build.verify(self.c,self.m)
        (self.c/'wheels/retained.whl').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed while copying'):
            build.copy_verified(self.c,self.root/'selected',self.m,'wheels')


if __name__=='__main__':unittest.main()
