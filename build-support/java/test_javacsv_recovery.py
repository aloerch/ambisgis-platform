"""Synthetic fixtures verify binary-safe historical extraction and tamper rejection."""
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import javacsv_recovery as subject
from javacsv_probe import native_result

class RecoveryTests(unittest.TestCase):
    def test_reverse_delta_preserves_binary_cr_nul_and_unterminated_line(self):
        source = b'first\r\nremove\x00\nlast\r'
        patch_bytes = b'd2 1\na2 1\nnew\x00@\n'
        self.assertEqual(subject.reverse_delta(source, patch_bytes), b'first\r\nnew\x00@\nlast\r')

    def test_reverse_delta_handles_insertion_before_first_line(self):
        self.assertEqual(subject.reverse_delta(b'a\nb\n', b'a0 1\nstart\nd2 1\n'), b'start\na\n')

    def test_invalid_delta_ranges_and_truncation_fail(self):
        for delta in (b'd0 1\n', b'd2 1\n', b'a1 2\nonly one\n', b'a1 0\n', b'x1 1\n'):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                subject.reverse_delta(b'a\n', delta)

    def test_escaped_at_and_historical_revision_are_recovered(self):
        rcs = b'head 1.2;\n\n1.2\ndate 2007.01.01.00.00.00;\n1.1\ndate 2006.01.01.00.00.00;\n\ndesc\n@@\n\n1.2\nlog\n@new@\ntext\n@email@@host\nnew\n@\n\n1.1\nlog\n@old@\ntext\n@d2 1\n@\n'
        self.assertEqual(subject.revision(rcs, '1.1'), (b'email@host\n', '2006.01.01.00.00.00'))
        with self.assertRaises(ValueError): subject.revision(rcs, '1.0')

    def test_capsule_is_deterministic_and_keeps_original_source_bytes(self):
        files = {'src/A.java': b'original\r\n', 'COPYING': b'notice'}
        one, two = subject.capsule(files), subject.capsule(dict(reversed(list(files.items()))))
        self.assertEqual(one, two)
        with tarfile.open(fileobj=io.BytesIO(one), mode='r:gz') as archive:
            self.assertEqual(archive.extractfile('src/A.java').read(), files['src/A.java'])
            self.assertTrue(all(x.uid == 0 and x.mtime == 0 for x in archive.getmembers()))

    def test_native_result_requires_full_suite_without_failures_or_ignores(self):
        self.assertTrue(native_result('AMBISGIS_JUNIT_RESULT run=105 failures=0 ignored=0')['complete_success'])
        for line in ('run=0 failures=0 ignored=0', 'run=105 failures=16 ignored=0', 'run=104 failures=0 ignored=1'):
            self.assertFalse(native_result('AMBISGIS_JUNIT_RESULT ' + line)['complete_success'])

    def test_absent_or_duplicate_native_summary_is_not_a_pass(self):
        line = 'AMBISGIS_JUNIT_RESULT run=105 failures=0 ignored=0'
        for text in ('', line + '\n' + line):
            with self.assertRaises(ValueError): native_result(text)

    def test_tampered_inputs_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'snapshot').write_bytes(b'wrong')
            (root/'artifact').write_bytes(b'wrong')
            with self.assertRaises(ValueError):
                subject.recover(root/'snapshot', root/'artifact', root/'output')
            self.assertFalse((root/'output').exists())

if __name__ == '__main__': unittest.main()
