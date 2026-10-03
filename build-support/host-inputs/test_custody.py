import io
import hashlib
import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import inventory
import retain
import verify_payload


class InventoryBoundaryTests(unittest.TestCase):
    def row(self, **changes):
        return {'name': 'compiler', 'epoch': '0', 'version': '1', 'release': '1',
                'arch': 'x86_64', 'publisher_digest_algorithm': 'sha256',
                'publisher_digest': 'a' * 64, 'source_rpm': 'compiler-1-1.src.rpm',
                'repository_url': 'https://download.opensuse.org/tumbleweed/repo/oss',
                'location': 'x86_64/compiler-1-1.x86_64.rpm', **changes}

    def test_later_version_cannot_replace_observed_version(self):
        with self.assertRaises(ValueError):
            inventory.exact_record(self.row(), [self.row(version='2')])

    def test_same_version_conflicting_bytes_fail(self):
        with self.assertRaises(ValueError):
            inventory.exact_record(self.row(), [self.row(), self.row(publisher_digest='b' * 64)])

    def test_identical_snapshot_records_keep_both_origins(self):
        result = inventory.exact_record(self.row(), [self.row(), self.row(
            repository_url='https://download.opensuse.org/history/20260916/tumbleweed/repo/oss')])
        self.assertEqual(2, len(result['retrieval_urls']))

    def test_metadata_preserves_same_name_versions_and_architectures(self):
        rows = []
        for version, arch in [('1', 'x86_64'), ('2', 'x86_64'), ('1', 'noarch')]:
            rows.append(f'<package><name>compiler</name><arch>{arch}</arch>'
                        f'<version epoch="0" ver="{version}" rel="1"/>'
                        '<checksum type="sha256">abc</checksum><size package="1"/>'
                        '<location href="x86_64/compiler.rpm"/><format>'
                        '<rpm:sourcerpm>source.rpm</rpm:sourcerpm><rpm:license>MIT</rpm:license>'
                        '</format></package>')
        xml = '<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm">' + ''.join(rows) + '</metadata>'
        result = inventory.parse_packages(io.BytesIO(xml.encode()), ('x86_64', 'noarch'))
        self.assertEqual(3, len(result))
        self.assertEqual(3, len({inventory.key(row) for row in result}))

    def test_metadata_digest_required(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'metadata'; p.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                inventory.checked_metadata({'file': str(p), 'sha256': '0' * 64})

    def observed(self, path, exit_code=0, stdout='', stderr=''):
        return {'toolchain_files': [{'resolved': str(path), 'sha256': inventory.digest(path),
                'linkage': {'exit_code': exit_code, 'stdout': stdout, 'stderr': stderr}}]}

    def test_unresolved_library_and_failed_ldd_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'tool'; p.write_bytes(b'\x7fELF')
            for observation in [self.observed(p, stdout='libfoo => not found'),
                                self.observed(p, exit_code=1, stderr='not a dynamic executable')]:
                with self.assertRaises(ValueError):
                    inventory.selected_paths(observation)

    def test_shebang_exception_explicit_and_tool_hash_checked(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'wrapper'; p.write_bytes(b'#!/bin/sh\nexec pkgconf "$@"\n')
            observation = self.observed(p, exit_code=1, stderr='not a dynamic executable\n')
            self.assertEqual([str(p)], inventory.selected_paths(observation))
            p.write_bytes(b'#!/bin/sh\nchanged\n')
            with self.assertRaises(ValueError): inventory.selected_paths(observation)

    def test_rich_dependencies_are_not_silently_simplified(self):
        self.assertEqual(('if', ('package', None, None), ('condition', None, None)),
                         inventory.simple_rich('(package if condition)'))
        self.assertEqual(('or', ('account-utils', None, None), ('shadow-pw-mgmt', '=', '4.20.2')),
                         inventory.simple_rich('(account-utils or shadow-pw-mgmt = 4.20.2)'))
        for expression in ['(package and condition)', '(a if (b and c))', '(a >= if b)', '(a if b) or c']:
            with self.assertRaises(ValueError): inventory.simple_rich(expression)


class RetentionBoundaryTests(unittest.TestCase):
    def test_rpm_url_is_public_exact_publisher_only(self):
        accepted = 'https://download.opensuse.org/history/20260916/tumbleweed/repo/oss/x86_64/rpm-1.x86_64.rpm'
        self.assertEqual(accepted, retain.checked_url(accepted))
        for url in [accepted.replace('https:', 'http:'), accepted.replace('download.opensuse.org', 'example.org'),
                    accepted.replace('https://', 'https://token@'), accepted + '?token=secret',
                    accepted.replace('/x86_64/', '/x86_64/../')]:
            with self.assertRaises(ValueError): retain.checked_url(url)

    def test_wrong_source_origin_or_unpinned_revision_rejected(self):
        good = 'obs://build.opensuse.org/openSUSE:Factory/standard/' + 'a' * 32 + '-cmake:full'
        self.assertEqual(('openSUSE:Factory', 'a' * 32, 'cmake:full'), retain.obs_identity(good))
        for bad in [good.replace('openSUSE:Factory', 'home:someone'), good.replace('a' * 32, 'latest')]:
            with self.assertRaises(ValueError): retain.obs_identity(bad)

    def listing(self, entries='', revision=None):
        nodes = ET.fromstring('<rows>' + entries + '</rows>')
        if revision is None:
            data = ''.join(n.get('md5') + '  ' + n.get('name') + '\n'
                           for n in sorted(nodes, key=lambda n: n.get('name', '')) if n.tag == 'entry')
            revision = hashlib.md5(data.encode()).hexdigest()
        return f'<directory srcmd5="{revision}">{entries}</directory>'.encode()

    def test_source_listing_revision_and_paths_are_bound(self):
        good = '<entry name="source.tar.xz" md5="' + 'b' * 32 + '" size="42"/>'
        revision = ET.fromstring(self.listing(good)).get('srcmd5')
        self.assertEqual(1, len(retain.source_listing(self.listing(good), revision)))
        for data in [self.listing(good, 'c' * 32), self.listing(good.replace('source.tar.xz', '../escape')),
                     self.listing(good.replace('source.tar.xz', '_link')), self.listing(good + good),
                     self.listing('<linkinfo srcmd5="x"/>')]:
            with self.assertRaises(ValueError): retain.source_listing(data, revision)

    def test_cached_source_listing_cannot_rebind_changed_entries(self):
        good = '<entry name="source.tar.xz" md5="' + 'b' * 32 + '" size="42"/>'
        data = self.listing(good)
        revision = ET.fromstring(data).get('srcmd5')
        changed = data.replace(('b' * 32).encode(), ('c' * 32).encode())
        with self.assertRaisesRegex(ValueError, 'entry set'):
            retain.source_listing(changed, revision)

    def test_retained_replay_uses_no_network_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'input'; p.write_bytes(b'exact')
            wanted = retain.digest(p)
            with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
                result = retain.fetch('https://example.invalid', p, 5, wanted, 'sha256')
                self.assertFalse(result['network'])
                p.write_bytes(b'wrong')
                with self.assertRaises(ValueError): retain.fetch('https://example.invalid', p, 5, wanted, 'sha256')

    def test_symlink_ancestor_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / 'real' / 'child').mkdir(parents=True)
            (root / 'alias').symlink_to(root / 'real', target_is_directory=True)
            with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
                with self.assertRaises(ValueError):
                    retain.fetch('https://example.invalid', root / 'alias' / 'child' / 'file', 1, '0' * 64, 'sha256')

    def test_payload_checker_does_not_read_user_or_host_secrets(self):
        with patch.object(Path, 'lstat', side_effect=AssertionError('read outside scope')):
            for name in ['/root/.gnupg', '/home/person/.ssh/id_rsa', '/etc/shadow']:
                result = verify_payload.inspect_file(Path(name), 0o100600, '', '', 8)
                self.assertEqual('outside-build-file-scope', result['status'])


if __name__ == '__main__':
    unittest.main()
