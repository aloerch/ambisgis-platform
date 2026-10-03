import io
from pathlib import Path
import tarfile
import tempfile
import unittest

import successor_build as successor


class SuccessorGuards(unittest.TestCase):
    def test_exact_identity_only(self):
        successor.identity(successor.COMMIT,successor.TREE)
        for commit,tree in ((successor.publication.BASE,successor.TREE),('HEAD',successor.TREE),(successor.COMMIT,'0'*40)):
            with self.assertRaisesRegex(ValueError,'identity'): successor.identity(commit,tree)

    def archive(self, rows):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        path=Path(self.tmp.name)/'source.tar'
        with tarfile.open(path,'w') as target:
            for name,data,mode in rows:
                row=tarfile.TarInfo(name);row.size=len(data);row.mode=mode
                target.addfile(row,io.BytesIO(data))
        return path

    def expected(self):
        return {'source.cpp':{'mode':'100644','oid':successor.publication.blob_id(b'owned source')}}

    def test_exact_archive(self):
        archive=self.archive([('qgis-successor/source.cpp',b'owned source',0o644)])
        self.assertEqual(1,successor.verify_archive(archive,self.expected())['source_entries'])

    def test_changed_source_bytes(self):
        archive=self.archive([('qgis-successor/source.cpp',b'other revision',0o644)])
        with self.assertRaisesRegex(ValueError,'differs'):successor.verify_archive(archive,self.expected())

    def test_changed_mode(self):
        archive=self.archive([('qgis-successor/source.cpp',b'owned source',0o755)])
        with self.assertRaisesRegex(ValueError,'differs'):successor.verify_archive(archive,self.expected())

    def test_missing_source(self):
        with self.assertRaisesRegex(ValueError,'differs'):successor.verify_archive(self.archive([]),self.expected())

    def test_extra_source(self):
        archive=self.archive([('qgis-successor/source.cpp',b'owned source',0o644),('qgis-successor/extra.cpp',b'x',0o644)])
        with self.assertRaisesRegex(ValueError,'differs'):successor.verify_archive(archive,self.expected())

    def test_duplicates_and_traversal(self):
        for rows in ([('qgis-successor/source.cpp',b'owned source',0o644)]*2,
                     [('qgis-successor/../escape',b'x',0o644)], [('wrong/source.cpp',b'x',0o644)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                successor.verify_archive(self.archive(rows),self.expected())

    def test_preserved_producer_identity(self):
        self.assertEqual(successor.PRODUCER_SHA,successor.sha(successor.HERE/'build.py'))

    def test_sqlite_discovery_pin_only_on_configure(self):
        original=['cmake','-S','source','-B','build']
        result=successor.configure_command(original,Path('/retained/spatial'))
        self.assertEqual(original+['-Dpkgcfg_lib_PC_SPATIALITE_sqlite3=/retained/spatial/lib/libsqlite3.so'],result)
        self.assertEqual(['cmake','-S','source','-B','build'],original)
        for command in (['cmake','--build','build'],['cmake','--install','build'],['ldd','binary']):
            self.assertEqual(command,successor.configure_command(command,Path('/retained/spatial')))

    def test_duplicate_discovery_pin_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            successor.configure_command(['cmake','-S','source','-Dpkgcfg_lib_PC_SPATIALITE_sqlite3=/usr/lib/host'],Path('/retained/spatial'))


if __name__=='__main__':unittest.main()
