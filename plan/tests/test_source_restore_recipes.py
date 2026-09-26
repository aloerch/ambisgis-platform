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

    def test_qgis_replay_receipt_identifies_generated_bytes_not_tooling(self):
        source=self.root/'qgis';platform=self.root/'platform';workspace=self.root/'workspace'
        output=self.root/'output';output.mkdir()
        def put(root,name,data):
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            return {'path':name,'sha256':recipes.sha(path),'bytes':len(data)}
        generated_name='python/plugins/grassprovider/description/algorithms.json'
        generated=json.dumps([{'name':'one'}],indent=2).encode()
        generated_row=put(workspace/'build-worktrees/qgis-candidate/build-06/sources/qgis-3.44.14',generated_name,generated)
        parser=b'''class ParsedDescription:
    name = 'one'
    @staticmethod
    def parse_description_file(path, translate=False):
        return ParsedDescription()
    def as_dict(self):
        return {'name': self.name}
'''
        parser_row=put(source,'python/plugins/grassprovider/parsed_description.py',parser)
        put(source,'python/plugins/grassprovider/description/one.txt',b'one')
        helper_dir=platform/'build-support/qgis'
        tooling=[put(helper_dir,'common.py',b'# source fixture\n'),
            put(helper_dir,'resource_selection.py',b'def trim_catalogue(data, roots, schemes=()):\n    return data, []\n')]
        resource='resources/cpt-city-qgis-min/selected.svg'
        row=put(source,resource,b'selected palette');row['path']='share/qgis/'+resource
        final=[row]
        notice_prefix='share/qgis/doc/ambisgis-resource-selection/'
        for target,name in [('default-icons-LICENSE.TXT','images/themes/default/LICENSE.TXT'),
                ('QGIS-Vera-COPYRIGHT.TXT','tests/testdata/font/QGIS-Vera/COPYRIGHT.TXT'),
                ('QGIS-Vera-README.txt','tests/testdata/font/QGIS-Vera/QGIS-Vera-README.txt')]:
            row=put(source,name,target.encode());row['path']=notice_prefix+target;final.append(row)
        readme=("Private proposed QGIS resource profile. Exactly 0 optional SVG palettes are omitted.\n"
            "The old source/stage remain custody records, not approved distribution bundles.\n"
            "ColorBrewer: This product includes color specifications and designs developed by Cynthia Brewer (http://colorbrewer.org/).\n"
            "Its exact acknowledgement, naming and notice terms remain in resources/cpt-city-qgis-min/cb/COPYING.xml.\n"
            "Other inherited resource/support/icon/font obligations remain; these additions are not legal clearance.\n"
            "Omitted collection metadata/notices are retained here outside the active palette archive.\n"
            "Saved projects can retain serialized symbol/shader colors, but omitted named ramps cannot be selected or reloaded.\n"
            "Reclassification from such a ramp requires an explicit user choice; full saved-project compatibility is not claimed.\n")
        final.append({'path':notice_prefix+'README.txt','sha256':hashlib.sha256(readme.encode()).hexdigest()})
        documents={'qgis-generated-source':{'added':[generated_row],'generator_identities':{parser_row['path']:parser_row['sha256']}},
            'java-gmt-qgis-membership':{'exclusions':{},'omitted_collection_roots':[]},
            'java-gmt-qgis-output':{'files':final},
            'java-gmt-qgis-selection':{'catalogue_changes':[],
                'executed_recipe':{'files_before':{'resource_selection.py':tooling[-1]}}},
            'qgis-selection-result':{'catalogue_changes':[],'relocated_metadata':[]},
            'java-gmt-qgis-stage-tooling':{'files':tooling}}
        class Selected:
            def document(self,name):
                return documents[name]
        selected=Selected();selected.platform=platform;selected.workspace=workspace
        result=recipes.replay_qgis(selected,{'qgis':source},output)
        self.assertNotEqual(generated_row['sha256'],tooling[-1]['sha256'])
        self.assertEqual(result['generated']['sha256'],recipes.sha(output/result['generated']['path']))
        self.assertEqual(result['generated']['sha256'],generated_row['sha256'])



if __name__ == '__main__':
    unittest.main()
