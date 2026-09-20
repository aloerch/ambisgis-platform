import hashlib
from pathlib import Path
import tempfile
import unittest
import compatibility

class RuntimeRepositoryTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'retained';local=root/'local';source.mkdir();local.mkdir()
        path='a/b/1/b-1.jar';p=source/path;p.parent.mkdir(parents=True);p.write_bytes(b'verified-input')
        rows=[{'maven_path':path,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]
        return rows,source,local
    def test_missing_provider_staged_with_origin_and_verified_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows,source,local=self.fixture(root)
            report=compatibility.prime_runtime_repository(rows,source,local,root)
            p=local/rows[0]['maven_path']
            self.assertEqual(p.read_bytes(),b'verified-input')
            self.assertIn('b-1.jar>ambisgis-custody=',(p.parent/'_remote.repositories').read_text())
            self.assertEqual(report['copied'],1)
            self.assertFalse(report['network_acquisition'])
    def test_publisher_sidecar_is_retained_without_overwriting_normalized_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows,source,local=self.fixture(root)
            sidecar=source/(rows[0]['maven_path']+'.sha1');sidecar.write_bytes(b'publisher checksum with filename')
            rows.append({'maven_path':rows[0]['maven_path']+'.sha1','sha256':hashlib.sha256(sidecar.read_bytes()).hexdigest()})
            normalized=local/rows[1]['maven_path'];normalized.parent.mkdir(parents=True);normalized.write_bytes(b'normalized')
            report=compatibility.prime_runtime_repository(rows,source,local,root)
            self.assertEqual(normalized.read_bytes(),b'normalized')
            self.assertEqual(sidecar.read_bytes(),b'publisher checksum with filename')
            self.assertEqual(report['files'],1)
    def test_existing_different_bytes_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows,source,local=self.fixture(root)
            p=local/rows[0]['maven_path'];p.parent.mkdir(parents=True);p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'conflicts'):
                compatibility.prime_runtime_repository(rows,source,local,root)
            self.assertEqual(p.read_bytes(),b'wrong')
    def test_symlinked_parent_is_refused_before_creating_outside_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows,source,local=self.fixture(root)
            outside=root/'outside';outside.mkdir();(local/'a').symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'parent is a symlink'):
                compatibility.prime_runtime_repository(rows,source,local,root)
            self.assertEqual(list(outside.iterdir()),[])
    def test_retained_drift_prevents_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows,source,local=self.fixture(root)
            (source/rows[0]['maven_path']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):
                compatibility.prime_runtime_repository(rows,source,local,root)
            self.assertFalse((local/rows[0]['maven_path']).exists())

if __name__=='__main__':unittest.main()
