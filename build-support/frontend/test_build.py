import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build

class InputIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.archive=self.root/'a.tgz';self.archive.write_bytes(b'retained bytes')
        self.sri='sha512-'+base64.b64encode(hashlib.sha512(self.archive.read_bytes()).digest()).decode()
    def lock(self,resolved='file:vendor/a.tgz'):
        return {'lockfileVersion':3,'packages':{'':{},'node_modules/a':{'resolved':resolved,'integrity':self.sri}}}
    def test_local_lock_accepts_verified_bytes(self):
        build.validate_lock(self.lock(),self.root)
    def test_corrupted_archive_rejected(self):
        self.archive.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'integrity mismatch'):build.validate_lock(self.lock(),self.root)
    def test_remote_registry_rejected(self):
        with self.assertRaisesRegex(ValueError,'Non-retained'):build.validate_lock(self.lock('https://registry.npmjs.org/a.tgz'),self.root)
    def test_git_prepare_download_rejected(self):
        with self.assertRaisesRegex(ValueError,'Non-retained'):build.validate_lock(self.lock('git+ssh://git@github.com/a/b#master'),self.root)
    def test_archive_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unsafe'):build.validate_lock(self.lock('file:vendor/../a.tgz'),self.root)
    def test_unexpected_link_rejected(self):
        lock=self.lock();lock['packages']['node_modules/a']={'link':True,'resolved':'../../cache'}
        with self.assertRaisesRegex(ValueError,'Unexpected local link'):build.validate_lock(lock,self.root)
    def test_missing_integrity_rejected(self):
        lock=self.lock();lock['packages']['node_modules/a']['integrity']=''
        with self.assertRaisesRegex(ValueError,'Missing'):build.validate_lock(lock,self.root)
    def test_manifest_tuple_rejected(self):
        with self.assertRaisesRegex(ValueError,'tuple changed'):build.verify_inputs(self.root,{'client_commit':'bad','mapstore_commit':build.MAPSTORE,'files':[]})
    def test_incomplete_manifest_rejected(self):
        manifest={'client_commit':build.CLIENT,'mapstore_commit':build.MAPSTORE,'files':[{'path':'a.tgz','sha256':'bad'}]}
        with self.assertRaisesRegex(ValueError,'Incomplete'):build.verify_inputs(self.root,manifest)
    def test_empty_manifest_rejected(self):
        manifest={'client_commit':build.CLIENT,'mapstore_commit':build.MAPSTORE,'files':[]}
        with self.assertRaisesRegex(ValueError,'Incomplete'):build.verify_inputs(self.root,manifest)
    def test_parent_symlink_rejected(self):
        (self.root/'linked').symlink_to(self.root,target_is_directory=True)
        manifest={'client_commit':build.CLIENT,'mapstore_commit':build.MAPSTORE,'files':[]}
        with self.assertRaisesRegex(ValueError,'Symlink'):build.verify_inputs(self.root,manifest)
    def test_duplicate_input_records_rejected(self):
        row={'path':'a.tgz','sha256':build.sha(self.archive),'bytes':self.archive.stat().st_size}
        manifest={'client_commit':build.CLIENT,'mapstore_commit':build.MAPSTORE,'files':[row,row]}
        with self.assertRaisesRegex(ValueError,'Duplicate'):build.verify_inputs(self.root,manifest)
    def test_existing_output_is_not_owned(self):
        state={}; (self.root/'success.json').write_text('{}')
        before=build.inventory(self.root)
        with self.assertRaisesRegex(ValueError,'Fresh output'):build.build(self.root,self.root,state)
        self.assertFalse(state.get('owns_output'))
        self.assertEqual(before,build.inventory(self.root))
    def complete_manifest(self):
        required=('client.bundle','mapstore.bundle','node.tar.xz','package-lock.json','vendor/project.tar.gz','vendor/patcher.tar.gz','vendor/nomnom.tar.gz')
        for name in required:
            p=self.root/name;p.parent.mkdir(exist_ok=True);p.write_bytes(b'valid bytes')
        return {'client_commit':build.CLIENT,'mapstore_commit':build.MAPSTORE,'files':build.inventory(self.root)}
    def test_complete_manifest_checks_same_size_corruption(self):
        manifest=self.complete_manifest();build.verify_inputs(self.root,manifest)
        (self.root/'node.tar.xz').write_bytes(b'wrong bytes')
        with self.assertRaisesRegex(ValueError,'Input changed'):build.verify_inputs(self.root,manifest)
    def test_complete_manifest_checks_size(self):
        manifest=self.complete_manifest();(self.root/'node.tar.xz').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'Input changed'):build.verify_inputs(self.root,manifest)
    def test_audit_rejects_unsafe_tar_metadata(self):
        import io,tarfile,audit_inputs
        p=self.root/'bad.tar.gz'
        with tarfile.open(p,'w:gz') as t:
            data=b'{"name":"fake"}';entry=tarfile.TarInfo('../package.json');entry.size=len(data);t.addfile(entry,io.BytesIO(data))
        with self.assertRaisesRegex(ValueError,'Unsafe archive'):audit_inputs.inspect(p)
    def test_changed_root_manifest_rejected(self):
        (self.root/'manifest.json').write_text('{}')
        specification=self.root/'inputs.json';specification.write_text(json.dumps({'references':[{'path':'manifest.json','sha256':'wrong'}]}))
        with self.assertRaisesRegex(ValueError,'reviewed input'):build.verify_reviewed_inputs(self.root,specification,self.archive)
    def test_changed_lock_rejected_even_with_reviewed_manifest(self):
        manifest=self.root/'manifest.json';manifest.write_text('{}')
        specification=self.root/'inputs.json';specification.write_text(json.dumps({'references':[{'path':'manifest.json','sha256':build.sha(manifest)}]}))
        (self.root/'package-lock.json').write_bytes(b'changed lock')
        with self.assertRaisesRegex(ValueError,'reviewed dependency'):build.verify_reviewed_inputs(self.root,specification,self.archive)
        (self.root/'package-lock.json').write_bytes(self.archive.read_bytes())
        build.verify_reviewed_inputs(self.root,specification,self.archive)
    def test_source_manifest_guards_fail_on_changed_candidate(self):
        (self.root/'package.json').write_text(json.dumps({'devDependencies':{'@mapstore/project':'unreviewed'}}))
        with self.assertRaisesRegex(ValueError,'source guard'):build.guard_packages(self.root)
    def test_command_failure_does_not_get_success(self):
        with self.assertRaisesRegex(ValueError,'failed'):build.run(['/usr/bin/false'],self.root,{},self.root,'failing')
        self.assertEqual(json.loads((self.root/'failing-command.json').read_text())['exit_code'],1)
        self.assertFalse((self.root/'success.json').exists())
    def test_successful_exit_without_network_proof_fails(self):
        with patch('build.subprocess.run') as run:
            run.return_value.returncode=0
            (self.root/'bad-network.json').write_text(json.dumps({'status':'refused','command_exit_code':0}))
            with self.assertRaisesRegex(ValueError,'Network runner'):build.run(['true'],self.root,{},self.root,'bad',True)
    def test_output_inventory_detects_changed_bytes(self):
        before=build.inventory(self.root);self.archive.write_bytes(b'changed');after=build.inventory(self.root)
        self.assertNotEqual(before,after)

if __name__=='__main__':unittest.main()
