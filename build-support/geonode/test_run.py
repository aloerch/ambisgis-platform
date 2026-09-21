"""Receipt and diagnostic boundaries for the real-service orchestration."""
import io
from pathlib import Path
import tempfile
import unittest

from run import Capture, redact, save


class DiagnosticsTests(unittest.TestCase):
    def test_source_diagnostic_leak_is_counted_even_after_redaction(self):
        class Process:
            stdout = io.StringIO('positive logger control\ncredential-secret reflected\n')
        with tempfile.TemporaryDirectory() as directory:
            capture = Capture(Process(), Path(directory) / 'runtime.log', lambda: ['credential-secret'])
            capture.finish()
            self.assertEqual(capture.leaks, 1)
            text = capture.path.read_text()
            self.assertIn('positive logger control', text)
            self.assertNotIn('credential-secret', text)
            self.assertIn('[REDACTED_FIXTURE_VALUE]', text)

    def test_source_counters_fail_even_when_source_message_is_already_redacted(self):
        class Process:
            stdout = io.StringIO('{"event":"application_log","message":"[REDACTED]",'
                                 '"source_diagnostic_redactions":1,"source_credential_field_redactions":2,'
                                 '"source_private_key_redactions":1,"source_opaque_value_redactions":5}\n')
        with tempfile.TemporaryDirectory() as directory:
            capture = Capture(Process(), Path(directory) / 'runtime.log', lambda: [])
            capture.finish()
            self.assertEqual(capture.leaks, 0)
            self.assertEqual(capture.security_failures, 4)
            self.assertEqual(capture.source_redactions['source_opaque_value_redactions'], 5)

    def test_duplicate_receipt_refuses_to_overwrite_failed_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            save(path, {'result_exit_code': 1})
            original = path.read_bytes()
            with self.assertRaises(FileExistsError): save(path, {'result_exit_code': 0})
            self.assertEqual(path.read_bytes(), original)

    def test_private_file_is_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private.json'
            save(path, {'secret': 'disposable-test-value'}, private=True)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_longest_secret_redacted_first(self):
        self.assertEqual(redact('abc-secret-other', ['abc', 'abc-secret-other']), '[REDACTED_FIXTURE_VALUE]')


if __name__ == '__main__': unittest.main()
