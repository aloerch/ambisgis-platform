"""Finite session/cleanup unit oracles; never a native authorization result."""
import io
import json
import unittest

import catalog_permission_probe as probe


class MemoryPolicy:
    """Protocol test state only. The actual driver uses NativePolicy exclusively."""
    def __init__(self):
        self.identity={'resource_uuid':'synthetic'};self.baseline={'granted':False}
        self.granted=False;self.changes=[];self.fail_change=False;self.fail_restore=False
    def change(self, grant):
        self.granted=grant;self.changes.append(grant)
        if self.fail_change:raise ValueError('failure after mutation')
        return {'granted':grant,'policy_sha256':probe.fingerprint({'granted':grant})}
    def restore(self):
        if self.fail_restore:raise ValueError('restoration failure')
        self.granted=False
        return {'complete':True,'before_sha256':probe.fingerprint(self.baseline),'after_sha256':probe.fingerprint(self.baseline)}


class PolicySessionTests(unittest.TestCase):
    def execute(self, lines, policy=None):
        policy=policy or MemoryPolicy();output=io.StringIO()
        code=probe.run(io.StringIO(lines),output,lambda:policy)
        return code,[json.loads(row) for row in output.getvalue().splitlines()],policy

    def test_allow_deny_allow_sequence_restores_original_policy(self):
        code,rows,policy=self.execute(''.join(json.dumps({'action':a})+'\n' for a in ('grant','revoke','grant','finish')))
        self.assertEqual(code,0);self.assertEqual(policy.changes,[True,False,True]);self.assertFalse(policy.granted)
        self.assertEqual([r['event'] for r in rows],['ready','grant','revoke','grant','cleanup'])
        self.assertTrue(rows[-1]['complete']);self.assertTrue(rows[-1]['sequence_complete'])

    def test_eof_wrong_order_and_invalid_actions_restore_after_grant(self):
        bad=['','{"action":"grant"}\n','{"action":"grant","resource":"other"}\n',
             '{"action":"revoke","action":"grant"}\n','{"action":"grant","principal":1}\n',
             '{"action":"eval","program":"ignored"}\n','x'*129]
        for line in bad:
            with self.subTest(line=line):
                code,rows,policy=self.execute('{"action":"grant"}\n'+line)
                self.assertEqual(code,1);self.assertFalse(policy.granted)
                self.assertTrue(rows[-1]['complete']);self.assertFalse(rows[-1]['sequence_complete'])

    def test_parent_finish_after_partial_sequence_still_restores(self):
        code,rows,policy=self.execute('{"action":"grant"}\n{"action":"finish"}\n')
        self.assertEqual(code,0);self.assertFalse(policy.granted)
        self.assertTrue(rows[-1]['complete']);self.assertFalse(rows[-1]['sequence_complete'])

    def test_exception_after_mutation_restores_and_cannot_pass(self):
        policy=MemoryPolicy();policy.fail_change=True
        code,rows,policy=self.execute('{"action":"grant"}\n',policy)
        self.assertEqual(code,1);self.assertFalse(policy.granted);self.assertTrue(rows[-1]['complete'])

    def test_restore_failure_is_incomplete_without_exception_text(self):
        policy=MemoryPolicy();policy.fail_restore=True
        code,rows,_=self.execute('{"action":"grant"}\n{"action":"finish"}\n',policy)
        self.assertEqual(code,1);self.assertFalse(rows[-1]['complete'])
        self.assertNotIn('restoration failure',json.dumps(rows))


if __name__=='__main__':unittest.main()
