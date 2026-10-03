import copy
from pathlib import Path
import tempfile
import unittest

from successor_compare import path_diagnostic, verify_network


class SuccessorComparisonGuards(unittest.TestCase):
    def test_path_equivalence_is_not_raw_equality(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root); left=base/'left';right=base/'right'
            left.write_text('compiled prefix /attempt-001/compile/prefix')
            right.write_text('compiled prefix /attempt-002/compile/prefix')
            report=path_diagnostic(left,right,Path('/attempt-001'),Path('/attempt-002'))
            self.assertFalse(report['raw_bytes_equal'])
            self.assertEqual(report['diagnostic_only_equivalence'],'attempt absolute path')
            right.write_text('changed product behavior /attempt-002/compile/prefix')
            report=path_diagnostic(left,right,Path('/attempt-001'),Path('/attempt-002'))
            self.assertTrue(report['unexplained_difference'])

    def test_missing_or_tampered_network_evidence_rejected(self):
        proof={'command_exit_code':0,'status':'completed','command':['cmake'],
               'kernel_state':{'no_new_privs':1,'seccomp_mode':2},
               'probes':[{'family':family,'passed':True} for family in ('AF_INET','AF_INET6','AF_UNIX','AF_UNIX')]}
        verify_network(proof,['cmake'])
        for key,value in (('status','started'),('command_exit_code',1),('command',['curl']),('kernel_state',{}),('probes',[])):
            bad=copy.deepcopy(proof);bad[key]=value
            with self.assertRaises(ValueError):verify_network(bad,['cmake'])


if __name__ == '__main__':
    unittest.main()
