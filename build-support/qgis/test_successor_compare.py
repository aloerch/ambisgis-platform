import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import successor_compare as comparison
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

    def test_qt_utf16_path_attribution_does_not_hide_changed_behavior(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root);left=base/'left';right=base/'right'
            for encoding in ('utf-16-le','utf-16-be'):
                left.write_bytes('behavior one /attempt-001/source'.encode(encoding))
                right.write_bytes('behavior one /attempt-002/source'.encode(encoding))
                report=path_diagnostic(left,right,Path('/attempt-001'),Path('/attempt-002'))
                self.assertEqual(report['diagnostic_only_equivalence'],'attempt absolute path')
                self.assertEqual(sum(report['utf16_attempt_path_occurrences'].values()),1)
                self.assertFalse(report['raw_bytes_equal'])
                right.write_bytes('behavior two /attempt-002/source'.encode(encoding))
                self.assertTrue(path_diagnostic(left,right,Path('/attempt-001'),Path('/attempt-002'))['unexplained_difference'])

    def test_missing_or_tampered_network_evidence_rejected(self):
        proof={'command_exit_code':0,'status':'completed','command':['cmake'],
               'kernel_state':{'no_new_privs':1,'seccomp_mode':2},
               'probes':[{'family':family,'passed':True} for family in ('AF_INET','AF_INET6','AF_UNIX','AF_UNIX')]}
        verify_network(proof,['cmake'])
        for key,value in (('status','started'),('command_exit_code',1),('command',['curl']),('kernel_state',{}),('probes',[])):
            bad=copy.deepcopy(proof);bad[key]=value
            with self.assertRaises(ValueError):verify_network(bad,['cmake'])

    def test_compare_fails_closed_after_retaining_unexplained_difference(self):
        # Synthetic command-level guard regression, not product build evidence.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);first=root/'first';second=root/'second'
            manifests={}
            for attempt,payload in ((first,'behavior one'),(second,'behavior two')):
                prefix=attempt/'compile/prefix';prefix.mkdir(parents=True)
                artifact=prefix/'artifact';artifact.write_text(payload)
                manifests[attempt]=(prefix,{'files':[{'path':'artifact','sha256':comparison.sha(artifact),'bytes':len(payload)}]})
                for name in ('configure','compile','stage','staged-crs-sync','native-test-compile',
                             'desktop-linkage','server-linkage','generated-source-reproduce'):
                    log=attempt/'compile'/(name+'.log');log.write_text('synthetic unit fixture')
                    command={'argv':['wrapper','--','cmake'],'exit_code':0,'log_sha256':comparison.sha(log)}
                    (attempt/'compile'/(name+'-command.json')).write_text(json.dumps(command))
                    proof={'command_exit_code':0,'status':'completed','command':['cmake'],
                        'kernel_state':{'no_new_privs':1,'seccomp_mode':2},
                        'probes':[{'family':family,'passed':True} for family in ('AF_INET','AF_INET6','AF_UNIX','AF_UNIX')]}
                    (attempt/'compile'/(name+'-network.json')).write_text(json.dumps(proof))
                for name in ('started.json','result.json'):(attempt/name).write_text('{}')
            before={'commit':'a','api_sha256':'before'}
            baseline=root/'before.json';baseline.write_text(json.dumps(before))
            drift=root/'drift.json';drift.write_text(json.dumps({'fixture_before':before,
                'fixture_after':{'commit':'b','api_sha256':'after'},'floating_positive_control':{'changed':True}}))
            sequence=[baseline,first/'started.json',first/'result.json',drift,second/'started.json',second/'result.json']
            for index,path in enumerate(sequence):os.utime(path,ns=((index+1)*10**9,(index+1)*10**9))
            output=root/'comparison.json'
            with patch.object(comparison,'verify_build',side_effect=lambda path:manifests[path]),\
                 patch.object(comparison,'selected_inputs',return_value={'commit':'synthetic'}):
                with self.assertRaisesRegex(ValueError,'unexplained output'):
                    comparison.compare(first,second,drift,output)
                self.assertEqual(json.loads(output.read_text())['product']['output_comparison']['unexplained_entries'],1)
                manifests[second][1]['files'][0]['path']='added-artifact'
                membership=root/'membership.json'
                with self.assertRaisesRegex(ValueError,'unexplained output'):
                    comparison.compare(first,second,drift,membership)
                differences=json.loads(membership.read_text())['product']['output_comparison']
                self.assertEqual(differences['unexplained_entries'],2)
                self.assertEqual(differences['added_paths'],['added-artifact'])
                self.assertEqual(differences['removed_paths'],['artifact'])
                os.utime(baseline,ns=(10**12,10**12))
                with self.assertRaisesRegex(ValueError,'fixture must precede'):
                    comparison.compare(first,second,drift,root/'bad-chronology.json')


if __name__ == '__main__':
    unittest.main()
