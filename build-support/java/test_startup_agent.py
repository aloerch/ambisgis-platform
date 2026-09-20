from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import compatibility

class StartupAgentTests(unittest.TestCase):
    def fixture(self,root):
        path=root/compatibility.TEST_AGENT_PATH;path.parent.mkdir(parents=True)
        with zipfile.ZipFile(path,'w') as jar:jar.writestr('META-INF/MANIFEST.MF','Premain-Class: net.bytebuddy.agent.Installer\n')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        return path,digest,[{'maven_path':compatibility.TEST_AGENT_PATH,'sha256':digest}]
    def test_only_pinned_retained_agent_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path,digest,rows=self.fixture(root)
            with patch('compatibility.TEST_AGENT_SHA256',digest):
                result=compatibility.startup_test_agent(root,rows)
            self.assertEqual(result['java_option'],'-javaagent:'+str(path))
            self.assertFalse(result['native_assertions_changed'])
    def test_missing_or_wrong_retained_identity_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path,digest,rows=self.fixture(root)
            for data in ([],rows):
                with self.subTest(data=data),self.assertRaisesRegex(ValueError,'missing'):
                    compatibility.startup_test_agent(root,data)
    def test_changed_agent_bytes_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path,digest,rows=self.fixture(root);path.write_bytes(b'changed')
            with patch('compatibility.TEST_AGENT_SHA256',digest),self.assertRaisesRegex(ValueError,'changed'):
                compatibility.startup_test_agent(root,rows)

if __name__=='__main__':unittest.main()
