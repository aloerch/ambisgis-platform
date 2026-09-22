"""Guard source-only replay against corrupted inputs and unintended destinations."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location('source_restore_recipes',
    Path(__file__).resolve().parents[2]/'build-support/source_restore/recipes.py')
recipes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recipes)


class SourceRecipeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, names):
        path = self.root/'input.tar'
        with tarfile.open(path,'w') as archive:
            for name, content in names:
                info=tarfile.TarInfo(name);info.size=len(content)
                archive.addfile(info,io.BytesIO(content))
        return path

    def test_archive_path_traversal_rejected_before_writes(self):
        archive = self.archive([('root/good.java',b'source'),('root/../../escape',b'bad')])
        with self.assertRaisesRegex(ValueError,'unsafe archive'):
            recipes.archive_entries(archive,strip=1)
        self.assertFalse((self.root.parent/'escape').exists())

    def test_duplicate_archive_member_rejected(self):
        archive = self.archive([('root/a.java',b'first'),('root/a.java',b'other')])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            recipes.archive_entries(archive,strip=1)

    def test_archive_symlink_rejected(self):
        path=self.root/'input.tar'
        with tarfile.open(path,'w') as archive:
            info=tarfile.TarInfo('root/link');info.type=tarfile.SYMTYPE;info.linkname='/tmp/escape'
            archive.addfile(info)
        with self.assertRaisesRegex(ValueError,'non-regular'):
            recipes.archive_entries(path,strip=1)

    def test_zip_symlink_rejected(self):
        path=self.root/'input.zip'
        with zipfile.ZipFile(path,'w') as archive:
            info=zipfile.ZipInfo('link');info.external_attr=0o120777<<16
            archive.writestr(info,'/tmp/escape')
        with self.assertRaisesRegex(ValueError,'symlink'):
            recipes.archive_entries(path)

    def test_regular_sources_recover_exactly(self):
        archive=self.archive([('root/src/a.java',b'editable'),('root/LICENSE',b'original terms')])
        target=self.root/'recovered'
        recipes.write_entries(target,recipes.archive_entries(archive,strip=1))
        expected={'src/a.java':hashlib.sha256(b'editable').hexdigest(),'LICENSE':hashlib.sha256(b'original terms').hexdigest()}
        self.assertEqual(recipes.compare(target,expected,'source')['files_verified'],2)

    def test_missing_required_source_fails_comparison(self):
        target=self.root/'recovered';target.mkdir()
        with self.assertRaisesRegex(ValueError,'differ or are missing'):
            recipes.compare(target,{'LICENSE':'0'*64},'source')

    def test_unexpected_generated_source_fails_comparison(self):
        target=self.root/'recovered';target.mkdir();(target/'unexpected.class').write_bytes(b'compiled')
        with self.assertRaisesRegex(ValueError,'unexpected source files'):
            recipes.compare(target,{},'source')

    def test_output_collision_rejected(self):
        target=self.root/'recovered';target.mkdir();(target/'keep').write_text('original')
        with self.assertRaises(FileExistsError):
            recipes.write_entries(target,{'new':b'new'})
        self.assertEqual((target/'keep').read_text(),'original')

    def test_changed_input_bytes_rejected(self):
        source=self.root/'source';source.write_bytes(b'original');digest=recipes.sha(source)
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'integrity mismatch'):
            recipes.checked(self.root,'source',digest)

    def test_symlink_parent_escape_rejected(self):
        outside=self.root/'outside';outside.mkdir();source=self.root/'source';source.mkdir()
        (source/'link').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):
            recipes.safe_path(source,'link/new.java')

    def test_wrong_frontend_patch_base_rejected_without_write(self):
        repo=self.root/'client';path=repo/'package.json';repo.mkdir();path.write_text('{"unselected": true}\n')
        class Selected:
            def document(self,name):
                return [{'component':'client','path':'package.json','source_sha256':'0'*64,'selected_sha256':'1'*64}]
        original=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'patch base mismatch'):
            recipes.replay_frontend(Selected(),{'mapstore-client':repo},self.root/'output')
        self.assertEqual(path.read_bytes(),original)

    def test_reusing_materialization_output_never_creates_success(self):
        output=self.root/'output';output.mkdir()
        with self.assertRaisesRegex(ValueError,'fresh recipe output'):
            recipes.materialize_recipes(self.root/'platform',self.root,{},output)
        self.assertFalse((output/'recipes-receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
