import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from owned_successor import artifact_origins, export_owned, git, inventory_digest


class OwnedSuccessorIdentity(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.repo=self.root/'repo';self.repo.mkdir()
        subprocess.run(['git','init','--quiet',str(self.repo)],check=True)
        (self.repo/'pom.xml').write_text('selected source\n')
        (self.repo/'.gitattributes').write_text('kept.txt export-ignore\n')
        (self.repo/'kept.txt').write_text('must be exported despite archive attribute\n')
        (self.repo/'build.sh').write_text('#!/bin/sh\nexit 0\n');(self.repo/'build.sh').chmod(0o755)
        git(self.repo,'add','.')
        git(self.repo,'-c','user.name=AmbisGIS test fixture','-c','user.email=test@example.invalid','commit','-qm','fixture')
        self.selection={'commit':git(self.repo,'rev-parse','HEAD').decode().strip(),
                        'tree':git(self.repo,'rev-parse','HEAD^{tree}').decode().strip()}

    def test_every_blob_and_executable_mode_exported(self):
        result=export_owned(self.repo,self.selection,self.root/'source')
        self.assertEqual(4,result['files'])
        self.assertEqual((self.repo/'kept.txt').read_bytes(),(self.root/'source/kept.txt').read_bytes())
        self.assertTrue((self.root/'source/build.sh').stat().st_mode&0o111)

    def test_mutable_ref_rejected(self):
        with self.assertRaisesRegex(ValueError,'immutable'):
            export_owned(self.repo,{**self.selection,'commit':'HEAD'},self.root/'source')

    def test_wrong_tree_rejected_before_output(self):
        with self.assertRaisesRegex(ValueError,'tree identity'):
            export_owned(self.repo,{**self.selection,'tree':'0'*40},self.root/'source')
        self.assertFalse((self.root/'source').exists())

    def test_selected_old_commit_survives_changed_default_api(self):
        (self.repo/'pom.xml').write_text('incompatible simulated donor API\n');git(self.repo,'add','.')
        git(self.repo,'-c','user.name=AmbisGIS test fixture','-c','user.email=test@example.invalid','commit','-qm','simulated donor drift')
        export_owned(self.repo,self.selection,self.root/'source')
        self.assertEqual('selected source\n',(self.root/'source/pom.xml').read_text())

    def test_source_symlink_rejected(self):
        (self.repo/'escape').symlink_to('/tmp');git(self.repo,'add','.')
        git(self.repo,'-c','user.name=AmbisGIS test fixture','-c','user.email=test@example.invalid','commit','-qm','invalid source link')
        selection={'commit':git(self.repo,'rev-parse','HEAD').decode().strip(),
                   'tree':git(self.repo,'rev-parse','HEAD^{tree}').decode().strip()}
        with self.assertRaisesRegex(ValueError,'unsafe selected'):
            export_owned(self.repo,selection,self.root/'source')

    def test_output_collision_preserved(self):
        out=self.root/'source';out.mkdir();(out/'owner').write_text('keep')
        with self.assertRaises(FileExistsError):export_owned(self.repo,self.selection,out)
        self.assertEqual('keep',(out/'owner').read_text())

    def test_core_jar_cannot_be_relabelled_from_unbuilt_bytes(self):
        source=self.root/'source';target=source/'app/target';target.mkdir(parents=True)
        with zipfile.ZipFile(target/'app.war','w') as war:war.writestr('WEB-INF/lib/gt-main.jar',b'old donor binary')
        with self.assertRaisesRegex(ValueError,'not produced'):
            artifact_origins(source)

    def test_inventory_digest_is_stable_and_sensitive(self):
        self.assertEqual(inventory_digest({'a':'one','b':'two'}),inventory_digest({'b':'two','a':'one'}))
        self.assertNotEqual(inventory_digest({'a':'one'}),inventory_digest({'a':'changed'}))
