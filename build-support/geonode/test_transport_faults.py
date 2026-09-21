import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from transport_faults import controlled_transport, fault_mode


class TransportTests(unittest.TestCase):
    def test_uncontrolled_request_passes_native_application(self):
        calls = []
        def native(env, start):
            calls.append(env)
            start('200 OK', [('Content-Length', '2')])
            return [b'{}']
        with tempfile.TemporaryDirectory() as directory:
            app = controlled_transport(native, {'output': directory})
            self.assertEqual(app({'PATH_INFO': '/api/o/v4/tokeninfo'}, lambda *x: None), [b'{}'])
            self.assertEqual(len(calls), 1)

    def test_fault_runs_native_authentication_first_and_preserves_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'transport-fault.json'
            path.write_text(json.dumps({'mode': 'truncate'})); path.chmod(0o600)
            calls = []
            def denied(env, start):
                calls.append('native-authentication')
                start('403 Forbidden', [('Content-Length', '6')])
                return [b'denied']
            app = controlled_transport(denied, {'output': directory})
            self.assertEqual(app({'PATH_INFO': '/api/o/v4/tokeninfo'}, lambda *x: None), [b'denied'])
            self.assertEqual(calls, ['native-authentication'])

    def test_public_or_symlink_control_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'transport-fault.json'
            path.write_text('{"mode":"delay"}'); path.chmod(0o644)
            with self.assertRaises(ValueError): fault_mode(directory)
            path.unlink(); path.symlink_to(Path(directory) / 'missing')
            with self.assertRaises(ValueError): fault_mode(directory)


if __name__ == '__main__': unittest.main()
