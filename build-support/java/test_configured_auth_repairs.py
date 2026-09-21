import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import configured_auth_repairs as repairs


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


class ConfiguredDiagnosticRepairTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.original = 'log(secret); log(secret);\n'
        self.repaired = 'log(category); log(category);\n'
        (self.source / 'source.java').write_text(self.original)
        self.fixture = self.root / 'fixtures'
        self.fixture.mkdir()
        (self.fixture / 'Test.java').write_text('@Test fixture')
        self.spec = {'sources': [{'path': 'source.java', 'purpose': 'redaction',
             'before_sha256': sha(self.original), 'after_sha256': sha(self.repaired),
             'replacements': [{'before':'secret','after':'category','count':2}]}],
             'fixtures':[{'file':'Test.java','path':'tests/Test.java','sha256':sha('@Test fixture'),'test_count':1}]}
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps(self.spec))
        for target, value in [('MANIFEST',self.manifest),('FIXTURES',self.fixture)]:
            mocked=patch.object(repairs,target,value);mocked.start();self.addCleanup(mocked.stop)

    def update(self):
        self.manifest.write_text(json.dumps(self.spec))

    def test_baseline_injects_native_tests_without_repair(self):
        receipt = repairs.prepare(self.source, repair=False)
        self.assertEqual((self.source/'source.java').read_text(),self.original)
        self.assertEqual(receipt['repairs'],[])
        self.assertEqual(receipt['native_test_count'],1)
        self.assertFalse(receipt['authentication_decision_changed'])

    def test_packaging_repairs_sources_without_test_injection(self):
        receipt = repairs.prepare(self.source,repair=True,tests=False)
        self.assertEqual((self.source/'source.java').read_text(),self.repaired)
        self.assertFalse((self.source/'tests').exists())
        self.assertEqual(receipt['native_test_count'],0)

    def test_later_source_mismatch_prevents_all_mutation(self):
        (self.source/'other.java').write_text('different')
        self.spec['sources'].append(dict(self.spec['sources'][0],path='other.java'))
        self.update()
        with self.assertRaisesRegex(ValueError,'exact source'):repairs.prepare(self.source,repair=True)
        self.assertEqual((self.source/'source.java').read_text(),self.original)
        self.assertFalse((self.source/'tests').exists())

    def test_existing_test_prevents_prior_source_repair(self):
        (self.source/'tests').mkdir();(self.source/'tests/Test.java').write_text('human work')
        with self.assertRaisesRegex(ValueError,'overwrite'):repairs.prepare(self.source,repair=True)
        self.assertEqual((self.source/'source.java').read_text(),self.original)
        self.assertEqual((self.source/'tests/Test.java').read_text(),'human work')

    def test_fixture_hash_mismatch_prevents_prior_source_repair(self):
        (self.fixture/'Test.java').write_text('changed')
        with self.assertRaisesRegex(ValueError,'fixture changed'):repairs.prepare(self.source,repair=True)
        self.assertEqual((self.source/'source.java').read_text(),self.original)

    def test_replacement_count_and_output_guard_prevent_mutation(self):
        for field,value,pattern in [('count',1,'ambiguous'),('after','other','predicted')]:
            with self.subTest(field=field):
                self.spec['sources'][0]['replacements'][0][field]=value;self.update()
                with self.assertRaisesRegex(ValueError,pattern):repairs.prepare(self.source,repair=True)
                self.assertEqual((self.source/'source.java').read_text(),self.original)
                self.spec['sources'][0]['replacements'][0]={'before':'secret','after':'category','count':2}

    def test_symlink_does_not_modify_retained_source(self):
        retained=self.root/'retained.java';retained.write_text(self.original)
        (self.source/'source.java').unlink();(self.source/'source.java').symlink_to(retained)
        with self.assertRaisesRegex(ValueError,'symlinks'):repairs.prepare(self.source,repair=True)
        self.assertEqual(retained.read_text(),self.original)

    def test_unsafe_path_rejected(self):
        self.spec['sources'][0]['path']='../source.java';self.update()
        with self.assertRaisesRegex(ValueError,'unsafe'):repairs.prepare(self.source,repair=True)


if __name__ == '__main__':unittest.main()
