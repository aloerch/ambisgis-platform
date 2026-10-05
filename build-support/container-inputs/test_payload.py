#!/usr/bin/env python3
"""Verify extraction never grants payload paths or links filesystem authority."""
import hashlib
from pathlib import Path
import stat
import tempfile
import unittest

from payload import materialize


def cpio(rows):
    result = bytearray()
    for name, mode, content in [*rows, ('TRAILER!!!', 0, b'')]:
        encoded = name.encode() + b'\0'
        values = [1, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(encoded), 0]
        result.extend(b'070701' + ''.join(f'{value:08x}' for value in values).encode())
        result.extend(encoded)
        result.extend(b'\0' * (-len(result) % 4))
        result.extend(content)
        result.extend(b'\0' * (-len(result) % 4))
    return bytes(result)


def signed(rows):
    return {'payload': {'filedigestalgo': 8}, 'files': [
        {'path': '/' + name, 'fileflags': 0, 'filemodes': mode,
         'filesizes': len(data), 'filedigests': hashlib.sha256(data).hexdigest(),
         'filelinktos': data.decode() if stat.S_ISLNK(mode) else ''}
        for name, mode, data in rows]}


class PayloadGuards(unittest.TestCase):
    def test_regular_executable_is_inert_and_privileged_modes_removed(self):
        rows = [('usr/bin/program', stat.S_IFREG | 0o6755, b'not executable here')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize(cpio(rows), signed(rows), root)
            self.assertEqual((root / rows[0][0]).stat().st_mode & 0o7777, 0o600)

    def test_symlinks_are_data_even_when_target_escapes(self):
        rows = [('usr/bin/link', stat.S_IFLNK | 0o777, b'/etc/shadow')]
        with tempfile.TemporaryDirectory() as directory:
            records = materialize(cpio(rows), signed(rows), Path(directory))
            self.assertEqual(records[0]['target'], '/etc/shadow')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_changed_bytes_and_missing_or_duplicate_members_rejected(self):
        rows = [('usr/file', stat.S_IFREG | 0o644, b'correct')]
        for altered in ([('usr/file', stat.S_IFREG | 0o644, b'changed')], [], rows * 2):
            with self.subTest(altered=altered), tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                materialize(cpio(altered), signed(rows), Path(directory))

    def test_traversal_and_devices_rejected(self):
        for name, mode in [('../escape', stat.S_IFREG | 0o644), ('/absolute', stat.S_IFREG | 0o644), ('device', stat.S_IFCHR | 0o600)]:
            rows = [(name, mode, b'')]
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                materialize(cpio(rows), signed(rows), Path(directory))

    def test_existing_file_and_symlink_ancestor_rejected(self):
        rows = [('usr/file', stat.S_IFREG | 0o644, b'data')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'usr').mkdir()
            (root / 'usr/file').write_text('user data')
            with self.assertRaises(FileExistsError):
                materialize(cpio(rows), signed(rows), root)
            self.assertEqual((root / 'usr/file').read_text(), 'user data')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'target').mkdir()
            (root / 'usr').symlink_to('target', target_is_directory=True)
            with self.assertRaises(ValueError):
                materialize(cpio(rows), signed(rows), root)


if __name__ == '__main__':
    unittest.main()
