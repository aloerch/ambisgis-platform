from pathlib import Path
import tempfile
import unittest

from successor_native import checked_newline_pair, selection_for_source


class NativeSuccessorGuards(unittest.TestCase):
    def test_arbitrary_or_already_converted_fixture_rejected(self):
        for data in (b'',b'synthetic\n'*20,b'synthetic\r\n'*20):
            with self.assertRaisesRegex(ValueError,'raw-Git'):
                checked_newline_pair(data)

    def test_missing_native_source_never_adopted(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((ValueError,FileNotFoundError)):
                selection_for_source(Path(directory))


if __name__ == '__main__':
    unittest.main()
