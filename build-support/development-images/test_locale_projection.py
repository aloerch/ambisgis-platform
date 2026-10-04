"""Inert locale projection guards; no locale, RPM, database or engine runs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

import locale_projection as locale


class LocaleProjection(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'payload'
        self.root.mkdir()
        self.contract = json.loads(Path(locale.__file__).with_name('locale-inputs.json').read_text())
        identity = self.contract['identity']
        self.directory = self.root / (identity['name'] + '-' + identity['version'] + '-' + identity['release'] + '.' + identity['arch'])
        self.directory.mkdir()
        self.audit = {'failures': [], 'host_modified': False, 'network_used': False, 'packages': [{
            'identity': identity, 'archive_sha256': self.contract['binary']['sha256'],
            'scripts_executed': False, 'payload': {'filedigestalgo': 8},
            'signed_verification': {
                'signed_header_sha256': self.contract['binary']['signed_header_sha256'],
                'source_build_disturl': self.contract['source']['disturl'],
                'source_rpm': Path(self.contract['source']['path']).name}, 'files': []}]}
        self.receipt = {'failures': [], 'package_code_executed': False, 'symlinks_materialized': False,
                        'host_modified': False, 'packages': [{
                            'identity': identity, 'archive_sha256': self.contract['binary']['sha256'],
                            'directory': str(self.directory), 'files': []}]}
        # Synthetic bytes are intentionally not native locale data. Actual
        # signed bytes are separately tested by the retained projection receipt.
        for name in self.contract['members']:
            raw = ('synthetic category ' + name).encode()
            sha = hashlib.sha256(raw).hexdigest()
            self.contract['members'][name] = {'sha256': sha, 'bytes': len(raw)}
            path = self.directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw); path.chmod(0o600)
            self.audit['packages'][0]['files'].append({
                'path': '/' + name, 'filemodes': stat.S_IFREG | 0o644, 'fileflags': 0,
                'filecaps': '', 'filelinktos': '', 'fileusername': 'root', 'filegroupname': 'root',
                'filedigests': sha, 'filesizes': len(raw)})
            self.receipt['packages'][0]['files'].append({
                'path': name, 'kind': 'file', 'sha256': sha, 'bytes': len(raw),
                'signed_mode': '0o100644', 'materialized_mode': '0600'})
        self.first = next(iter(self.contract['members']))

    def check(self):
        return locale.validate_payload(self.root, self.contract, self.audit, self.receipt)

    def test_exact_twelve_bytes_project_readable_nonexecutables(self):
        rows = self.check()
        self.assertEqual(set(rows), {locale.PREFIX + x for x in locale.CATEGORIES})
        for name, row in rows.items():
            self.assertEqual(row['mode'], 0o644)
            self.assertEqual(row['file']['sha256'], self.contract['members'][name]['sha256'])
            self.assertEqual(row['origin'], self.contract['binary']['sha256'] + ':' + name)

    def test_missing_member_even_when_receipt_claims_it(self):
        (self.directory / self.first).unlink()
        with self.assertRaisesRegex(ValueError, 'membership'): self.check()

    def test_modified_member_with_unchanged_receipt(self):
        (self.directory / self.first).write_bytes(b'wrong bytes')
        with self.assertRaisesRegex(ValueError, 'digest'): self.check()

    def test_extra_unrecorded_category_rejected(self):
        (self.directory / locale.PREFIX / 'unexpected').write_text('unrecorded')
        with self.assertRaisesRegex(ValueError, 'membership'): self.check()

    def test_other_locale_is_not_projected(self):
        path = self.directory / 'usr/lib/locale/en_US.utf8/LC_CTYPE'
        path.parent.mkdir(parents=True); path.write_text('not selected')
        self.assertEqual(len(self.check()), 12)

    def test_symlink_member_rejected_without_following(self):
        path = self.directory / self.first; path.unlink(); path.symlink_to('/not-a-locale-input')
        with self.assertRaisesRegex(ValueError, 'symbolic'): self.check()

    def test_symlink_parent_rejected(self):
        path = self.directory / 'usr/lib/locale'; moved = self.directory / 'saved'
        path.rename(moved); path.symlink_to(moved)
        with self.assertRaises(ValueError): self.check()

    def test_special_member_rejected_without_open(self):
        path = self.directory / self.first; path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaisesRegex(ValueError, 'regular'): self.check()

    def test_extracted_mode_drift_rejected(self):
        (self.directory / self.first).chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'size/mode'): self.check()

    def test_signed_metadata_mismatch_rejected(self):
        original = copy.deepcopy(self.audit)
        for key, value in [('filedigests', '0'*64), ('filesizes', 0), ('filemodes', stat.S_IFREG | 0o755),
                           ('fileflags', 64), ('filecaps', 'cap_setuid=ep'), ('fileusername', 'other')]:
            with self.subTest(field=key):
                self.audit = copy.deepcopy(original); self.audit['packages'][0]['files'][0][key] = value
                with self.assertRaisesRegex(ValueError, 'signed member'): self.check()

    def test_native_source_or_header_mismatch_rejected(self):
        original = copy.deepcopy(self.audit)
        for key in ('signed_header_sha256', 'source_build_disturl', 'source_rpm'):
            with self.subTest(field=key):
                self.audit = copy.deepcopy(original); self.audit['packages'][0]['signed_verification'][key] = 'different'
                with self.assertRaisesRegex(ValueError, 'provenance'): self.check()

    def test_wrong_package_and_archive_rejected(self):
        for container in (self.audit, self.receipt):
            old = container['packages'][0]['archive_sha256']
            container['packages'][0]['archive_sha256'] = '0'*64
            with self.assertRaisesRegex(ValueError, 'identity'): self.check()
            container['packages'][0]['archive_sha256'] = old
        self.receipt['packages'][0]['identity'] = dict(self.contract['identity'], version='different')
        with self.assertRaisesRegex(ValueError, 'identity'): self.check()

    def test_duplicate_header_or_payload_rejected(self):
        for container in (self.audit, self.receipt):
            rows = container['packages'][0]['files']; rows.append(rows[0])
            with self.assertRaisesRegex(ValueError, 'Duplicate'): self.check()
            rows.pop()

    def test_external_package_directory_rejected_before_read(self):
        self.receipt['packages'][0]['directory'] = '/usr/lib/locale'
        with self.assertRaisesRegex(ValueError, 'directory escapes'): self.check()

    def test_missing_and_extra_selection_or_receipt_rejected(self):
        original = copy.deepcopy(self.contract)
        self.contract['members'].pop(self.first)
        with self.assertRaisesRegex(ValueError, 'exactly twelve'): self.check()
        self.contract = original
        self.receipt['packages'][0]['files'].pop()
        with self.assertRaisesRegex(ValueError, 'membership'): self.check()

    def test_failed_or_executed_receipts_rejected(self):
        original = copy.deepcopy(self.receipt)
        for key, value in [('failures', ['failed']), ('package_code_executed', True),
                           ('symlinks_materialized', True), ('host_modified', True)]:
            with self.subTest(field=key):
                self.receipt = copy.deepcopy(original); self.receipt[key] = value
                with self.assertRaises(ValueError): self.check()
        self.receipt = original; self.audit['packages'][0]['scripts_executed'] = True
        with self.assertRaisesRegex(ValueError, 'scripts'): self.check()

    def test_production_entry_rejects_unbound_receipt_before_writes(self):
        (self.root / 'receipt.json').write_text(json.dumps(self.receipt))
        output = self.root.parent / 'notices'
        with self.assertRaisesRegex(ValueError, 'digest'):
            locale.select(self.root, self.root, self.root, {}, output)
        self.assertFalse(output.exists())

    def test_existing_libc_and_complete_notice_custody_required(self):
        bindings, system = {}, {}
        for name in ('usr/lib64/libc.so.6', 'usr/share/licenses/glibc/LICENSES'):
            path = self.root / Path(name).name; path.write_bytes(name.encode())
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            bindings[name] = {'sha256': sha, 'archive_sha256': '1'*64}
            system[name] = {'kind': 'file', 'file': {'path': str(path), 'sha256': sha},
                            'origin': '1'*64 + ':' + name}
        self.assertEqual(len(locale.validate_system(system, bindings)), 2)
        original = copy.deepcopy(system)
        for name in bindings:
            with self.subTest(missing=name):
                system = copy.deepcopy(original); del system[name]
                with self.assertRaisesRegex(ValueError, 'notice binding'): locale.validate_system(system, bindings)
            with self.subTest(archive=name):
                system = copy.deepcopy(original); system[name]['origin'] = 'different archive'
                with self.assertRaisesRegex(ValueError, 'notice binding'): locale.validate_system(system, bindings)
        system = original
        Path(system['usr/share/licenses/glibc/LICENSES']['file']['path']).write_text('truncated')
        with self.assertRaisesRegex(ValueError, 'digest'): locale.validate_system(system, bindings)


if __name__ == '__main__': unittest.main()
