"""Synthetic ELF data tests; no compiled artifact or runtime is executed."""
import hashlib
import struct
import unittest

import relocate_proj as r


def fixture(*, duplicate=False, symbol_offset=0):
    data = bytearray(2048)
    ident = b'\x7fELF\x02\x01\x01' + b'\0' * 9
    struct.pack_into('<16sHHIQQQIHHHHHH', data, 0, ident, 3, 62, 1, 0, 64, 1280, 0, 64, 56, 2, 64, 4, 0)
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 4, 0, 0, 0, len(data), len(data), 4096)
    struct.pack_into('<IIQQQQQQ', data, 120, 2, 4, 512, 512, 512, 80, 80, 8)
    strings = b'\0' + r.OLD.encode() + b'\0unrelated\0'
    data[768:768+len(strings)] = strings
    tags = [(1, 1), (1, 1)] if duplicate else [(1, 1), (14, len(r.OLD) + 2)]
    tags += [(5, 768), (10, len(strings)), (0, 0)]
    for index, pair in enumerate(tags): struct.pack_into('<qQ', data, 512 + index*16, *pair)
    struct.pack_into('<IBBHQQ', data, 1024, symbol_offset, 0, 0, 0, 0, 0)
    for index, row in enumerate([
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (0, 3, 2, 768, 768, len(strings), 0, 0, 1, 0),
        (0, 6, 2, 512, 512, 80, 1, 0, 8, 16),
        (0, 11, 2, 1024, 1024, 24, 1, 0, 8, 24)]):
        struct.pack_into('<IIQQQQIIQQ', data, 1280 + index*64, *row)
    return bytes(data)


class Relocation(unittest.TestCase):
    def transform(self, raw, **kwargs):
        return r.transform(raw, r.OLD, kwargs.get('new', r.NEW), hashlib.sha256(raw).hexdigest())

    def test_exact_change_only_in_declared_string_span(self):
        original = fixture(); changed, receipt = self.transform(original)
        start, count = receipt['string_offset'], receipt['replacement_span_bytes']
        self.assertEqual(original[:start], changed[:start])
        self.assertEqual(original[start+count:], changed[start+count:])
        self.assertEqual(receipt['after']['needed'], [r.NEW])
        self.assertEqual(len(changed), len(original))

    def test_wrong_original_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'hash'): r.transform(fixture(), r.OLD, r.NEW, '0'*64)

    def test_duplicate_needed_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unambiguous'): self.transform(fixture(duplicate=True))

    def test_overlapping_symbol_suffix_rejected(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'): self.transform(fixture(symbol_offset=2))

    def test_same_string_used_by_symbol_rejected(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'): self.transform(fixture(symbol_offset=1))

    def test_invalid_elf_architecture_and_long_replacement_rejected(self):
        bad = bytearray(fixture()); struct.pack_into('<H', bad, 18, 183)
        with self.assertRaisesRegex(ValueError, 'x86-64'): self.transform(bytes(bad))
        with self.assertRaisesRegex(ValueError, 'shorter'): self.transform(fixture(), new='x' * 200)

    def test_loader_section_string_table_mismatch_rejected(self):
        bad = bytearray(fixture()); struct.pack_into('<Q', bad, 512 + 2*16 + 8, 769)
        with self.assertRaisesRegex(ValueError, 'string tables differ'): self.transform(bytes(bad))


if __name__ == '__main__': unittest.main()
