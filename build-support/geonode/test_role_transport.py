import json
from pathlib import Path
import tempfile
import unittest
from transport_faults import controlled_role_transport, role_fault_mode

class RoleTransportTests(unittest.TestCase):
    def control(self, root, mode):
        path=Path(root)/'role-transport-fault.json'
        path.write_text(json.dumps({'mode':mode})); path.chmod(0o600)
        return path

    def test_role_credential_fault_never_changes_token_verifier(self):
        for mode in ('missing-credential','wrong-credential'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                self.control(root, mode)
                seen=[]
                def native(env,start):
                    seen.append(env.copy()); start('200 OK',[]); return [b'native-token-result']
                app=controlled_role_transport(native,{'output':root})
                env={'PATH_INFO':'/api/o/v4/tokeninfo','HTTP_AUTHORIZATION':'Basic client-value'}
                self.assertEqual(app(env,lambda *a:None),[b'native-token-result'])
                self.assertEqual(seen,[env])

    def test_credential_failure_executes_native_endpoint_with_altered_transport_only(self):
        for mode in ('missing-credential','wrong-credential'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                self.control(root,mode)
                seen=[]
                def native(env,start):
                    seen.append(env.copy()); start('401 Unauthorized',[]); return [b'actual-denial']
                app=controlled_role_transport(native,{'output':root})
                env={'PATH_INFO':'/api/users/test-user','HTTP_AUTHORIZATION':'ApiKey correct','marker':'retained'}
                self.assertEqual(app(env,lambda *a:None),[b'actual-denial'])
                self.assertEqual(seen[0]['marker'],'retained')
                self.assertNotEqual(seen[0].get('HTTP_AUTHORIZATION'),env['HTTP_AUTHORIZATION'])
                self.assertEqual(env['HTTP_AUTHORIZATION'],'ApiKey correct')

    def test_malformed_fault_cannot_turn_native_failure_into_success(self):
        with tempfile.TemporaryDirectory() as root:
            self.control(root,'malformed')
            def native(env,start): start('403 Forbidden',[]); return [b'actual-denial']
            statuses=[]
            app=controlled_role_transport(native,{'output':root})
            self.assertEqual(app({'PATH_INFO':'/api/roles'},lambda status,*a:statuses.append(status)),[b'actual-denial'])
            self.assertEqual(statuses,['403 Forbidden'])

    def test_fault_control_rejects_symlink_world_readable_and_extra_keys(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.control(root,'truncate'); path.chmod(0o644)
            with self.assertRaises(ValueError):role_fault_mode(root)
            path.chmod(0o600);path.write_text('{"mode":"delay","identity":"admin"}')
            with self.assertRaises(ValueError):role_fault_mode(root)
            path.unlink();path.symlink_to(Path(root)/'missing')
            with self.assertRaises(ValueError):role_fault_mode(root)
