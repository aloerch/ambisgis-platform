# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import quoteattr

from custody import checked_path, checked_rpm_url, copy_exact, fetch_exact, verify_rpm, source_listing


class CustodyTests(unittest.TestCase):
    def test_source_unit_patch_name_preserves_signed_membership(self):
        def fixture(name):
            digest = hashlib.md5(b'patch').hexdigest()
            revision = hashlib.md5((digest + '  ' + name + '\n').encode()).hexdigest()
            xml = ('<directory srcmd5="' + revision + '"><entry name=' + quoteattr(name)
                   + ' md5="' + digest + '" size="5"/></directory>').encode()
            return xml, revision
        xml, revision = fixture('harden_e2scrub@.service.patch')
        self.assertEqual(source_listing(xml, revision)[0]['name'], 'harden_e2scrub@.service.patch')
        for name in ('../escape', '/absolute', 'sub/file', '_link', '..', 'evil\\file'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                source_listing(*fixture(name))
        with self.assertRaises(ValueError):
            source_listing(xml.replace(b'size="5"', b'size="-1"'), revision)
        with self.assertRaises(ValueError):
            source_listing(xml.replace(b'harden_e2scrub@', b'other'), revision)

    def test_only_exact_snapshot_rpm_origin(self):
        checked_rpm_url('https://download.opensuse.org/history/20260916/tumbleweed/repo/oss/x86_64/pkg-1~rc1-1.x86_64.rpm')
        for url in ['https://download.opensuse.org/tumbleweed/repo/oss/x86_64/pkg.rpm',
                    'https://download.opensuse.org.evil.invalid/history/20260916/tumbleweed/repo/oss/x86_64/pkg.rpm',
                    'https://user@download.opensuse.org/history/20260916/tumbleweed/repo/oss/x86_64/pkg.rpm',
                    'http://download.opensuse.org/history/20260916/tumbleweed/repo/oss/x86_64/pkg.rpm',
                    'https://download.opensuse.org/history/20260916/tumbleweed/repo/oss/x86_64/../pkg.rpm']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                checked_rpm_url(url)

    def test_existing_bytes_reused_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input'
            path.write_bytes(b'retained')
            result = fetch_exact('https://example.invalid/never-contacted', path, 8, 'sha256', hashlib.sha256(b'retained').hexdigest())
            self.assertFalse(result['network'])
            with self.assertRaises(ValueError):
                fetch_exact('https://example.invalid/never-contacted', path, 8, 'sha256', '0' * 64)
            self.assertEqual(path.read_bytes(), b'retained')

    def test_custody_copy_is_creation_only_and_digest_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source', Path(directory) / 'target'
            source.write_bytes(b'input')
            with self.assertRaises(ValueError):
                copy_exact(source, target, 5, 'sha256', '0' * 64)
            self.assertFalse(target.exists())
            digest = hashlib.sha256(b'input').hexdigest()
            copy_exact(source, target, 5, 'sha256', digest)
            with self.assertRaises(FileExistsError):
                copy_exact(source, target, 5, 'sha256', digest)
            self.assertEqual(source.read_bytes(), target.read_bytes())

    def test_parent_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'real').mkdir()
            (base / 'link').symlink_to(base / 'real', target_is_directory=True)
            with self.assertRaises(ValueError):
                checked_path(base / 'link' / 'new-file')

    def test_actual_signed_archive_and_negative_header_identity(self):
        # Missing actual retained evidence fails instead of becoming a skipped
        # success. This helper suite runs with the existing host RPM tools.
        manifest = json.loads(Path(os.environ['CONTAINER_TEST_SELECTION']).read_text())
        root = Path(os.environ['CONTAINER_TEST_REUSE'])
        candidates = [(entry, root / 'rpms' / Path(entry['location']).name)
                      for entry in manifest['packages']]
        entry, path = next((entry, path) for entry, path in candidates if path.is_file())
        result = verify_rpm(path, entry)
        self.assertFalse(result['installed'])
        self.assertRegex(result['signed_header_sha256'], '^[0-9a-f]{64}$')
        changed = copy.deepcopy(entry)
        changed['version'] += '.wrong'
        with self.assertRaises(ValueError):
            verify_rpm(path, changed)


if __name__ == '__main__':
    unittest.main()
