"""Stage receipts must prove current bytes and the entire member set."""
import json
from pathlib import Path
import tempfile
import unittest
from renderer_artifacts import verify_stage
from runtime_common import sha


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'prefix'; (self.root / 'lib').mkdir(parents=True)
        self.server = self.root / 'lib/libqgis_server.so.1'; self.server.write_bytes(b'owned-test-artifact')
        (self.root / 'lib/libqgis_server.so').symlink_to(self.server.name)
        self.manifest = self.root.parent / 'manifest.json'
        self.value = {'prefix':str(self.root),'source_commit':'a'*40,'source_tree':'b'*40,'files':[
            {'path':'lib/libqgis_server.so.1','bytes':self.server.stat().st_size,'sha256':sha(self.server)},
            {'path':'lib/libqgis_server.so','link':self.server.name}]}
        self.config = {'qgis_prefix':str(self.root),'resource_manifest':str(self.manifest),
                       'successor':{'commit':'a'*40,'tree':'b'*40}}
        self.bind()

    def bind(self):
        self.manifest.write_text(json.dumps(self.value));self.config['resource_manifest_sha256']=sha(self.manifest)

    def test_current_bytes_and_extra_files(self):
        self.assertEqual(verify_stage(self.config)['files_verified'],2)
        self.server.write_bytes(b'changed')
        with self.assertRaises(ValueError):verify_stage(self.config)
        self.server.write_bytes(b'owned-test-artifact');(self.root/'unexpected').write_bytes(b'extra')
        with self.assertRaises(ValueError):verify_stage(self.config)

    def test_manifest_source_and_escape(self):
        self.config['successor']['commit']='c'*40
        with self.assertRaises(ValueError):verify_stage(self.config)
        self.config['successor']['commit']='a'*40
        self.value['files'][0]['path']='../manifest.json';self.bind()
        with self.assertRaises(ValueError):verify_stage(self.config)

    def test_link_and_manifest_tamper(self):
        link=self.root/'lib/libqgis_server.so';link.unlink();link.symlink_to('/etc/hosts')
        with self.assertRaises(ValueError):verify_stage(self.config)
        self.manifest.write_bytes(self.manifest.read_bytes()+b'\n')
        with self.assertRaises(ValueError):verify_stage(self.config)


if __name__ == '__main__':unittest.main()
