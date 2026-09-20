import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import huldra_probe


class RecoveredSourceGuards(unittest.TestCase):
    def test_tampered_source_stops_before_toolchain_or_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.tar.gz'
            source.write_bytes(b'changed input')
            with patch.object(huldra_probe.toolchain, 'verify_extracted') as verify:
                result = huldra_probe.probe(source, root, root, root, root / 'run')
            verify.assert_not_called()
            self.assertEqual(result['exit_code'], 1)
            self.assertEqual(result['commands'], [])
            self.assertIn('hash mismatch', result['error']['message'])
            self.assertTrue((root / 'run/result.json').is_file())

    def test_existing_run_and_evidence_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / 'result.json'
            evidence.write_text('prior failed evidence')
            with self.assertRaises(FileExistsError):
                huldra_probe.probe(root, root, root, root, root)
            self.assertEqual(evidence.read_text(), 'prior failed evidence')

    def test_network_receipt_requires_actual_ipv4_and_ipv6_denial(self):
        complete = {'status': 'completed', 'command_exit_code': 0, 'probes': [
            {'family': family, 'operation': 'socket(SOCK_STREAM)', 'errno': 1, 'passed': True}
            for family in ('AF_INET', 'AF_INET6')]}
        huldra_probe.verify_denial(complete, 0)
        for mutate in ('missing', 'allowed', 'exit'):
            bad = json.loads(json.dumps(complete))
            if mutate == 'missing':
                bad['probes'].pop()
            elif mutate == 'allowed':
                bad['probes'][0]['errno'] = 0
            else:
                bad['command_exit_code'] = 1
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                huldra_probe.verify_denial(bad, 0)


if __name__ == '__main__':
    unittest.main()
