"""Guard regressions; actual successful producer verification is a native run."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from successor_runtime_inputs import EXPECTED, packaged_classpath, regular


class SuccessorInputs(unittest.TestCase):
    def test_rejects_unrelated_successful_or_historical_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for value in ({'result_exit_code':0},{'result_exit_code':0,'target':'webapp','stage':'package'},
                          {'result_exit_code':0,'build_exit_code':0,'purpose':'new owned source producer',
                           'source_files_unchanged':True,'source_successor':{}}):
                (root/'result.json').write_text(json.dumps(value))
                with self.assertRaises(ValueError):packaged_classpath(root,root/'output')
                self.assertFalse((root/'output').exists())

    def test_changed_identity_or_unverified_tree_fails_before_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            value={'result_exit_code':0,'build_exit_code':0,'purpose':'new owned source producer',
                   'source_files_unchanged':True,'source_successor':copy.deepcopy(EXPECTED),
                   'preparation':{'owned_roots':copy.deepcopy(EXPECTED)}}
            for row in value['preparation']['owned_roots'].values():row['tree_verified']=True
            value['preparation']['owned_roots']['geotools']['tree_verified']=False
            (root/'result.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError):packaged_classpath(root,root/'output')
            value['preparation']['owned_roots']['geotools']['tree_verified']=True
            value['source_successor']['geotools']['commit']='0'*40
            (root/'result.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError):packaged_classpath(root,root/'output')
            self.assertFalse((root/'output').exists())

    def test_regular_artifact_cannot_escape_through_parent_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'real').mkdir();(root/'real/a').write_text('bytes')
            (root/'link').symlink_to(root/'real',target_is_directory=True)
            for relative in ('../escape','/etc/hosts','link/a'):
                with self.subTest(relative=relative):
                    with self.assertRaises(ValueError):regular(root,relative)
            self.assertEqual(regular(root,'real/a'),root/'real/a')


if __name__=='__main__':unittest.main()
