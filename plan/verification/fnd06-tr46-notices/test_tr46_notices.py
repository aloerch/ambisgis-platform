# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual retained archive tests. TR46_ARCHIVE is required; no silent skips."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / 'build-support/koop/tr46_notices.py'
spec = importlib.util.spec_from_file_location('tr46_notices', MODULE)
notices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices)


class NoticeSupplementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = Path(os.environ['TR46_ARCHIVE'])
        cls.original = cls.archive.read_bytes()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def clone_bundle(self):
        target = self.root / 'bundle'
        shutil.copytree(notices.BUNDLE, target)
        return target

    def test_complete_real_archive_source_and_data_coverage(self):
        result, _, generated, original = notices.verify(self.archive)
        self.assertEqual(original, self.original)
        self.assertEqual(len(result['members']), 5)
        self.assertEqual(result['mapping_rows'], 8179)
        self.assertEqual(len(generated), 260049)
        self.assertEqual(result['mapping_sha256'], 'b6b39724dca9011113a08d9d6910204062b58169e98952acdfbd19bf2c31bbff')
        self.assertEqual(result['unchanged_source_entries'], 13)

    def test_actual_staging_and_self_contained_verifier(self):
        output = self.root / 'staged'
        result = notices.stage(self.archive, output)
        self.assertEqual(result, notices.verify_stage(output, self.archive))
        for name in notices.NOTICE_FILES:
            self.assertEqual((output / 'software/notices/tr46-0.0.3' / name).read_bytes(),
                             (output / 'documentation/notices/tr46-0.0.3' / name).read_bytes())
        source = output / 'source/tr46-0.0.3'
        done = subprocess.run([sys.executable, str(source / 'tr46_notices.py'), 'verify-stage',
            '--archive', str(source / 'original-npm-archive.tgz'),
            '--bundle', str(source / 'supplement'), '--output', str(output)],
            capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), result)
        self.assertEqual(self.archive.read_bytes(), self.original)

    def test_two_new_stages_have_identical_complete_bytes(self):
        a, b = self.root / 'a', self.root / 'b'
        self.assertEqual(notices.stage(self.archive, a), notices.stage(self.archive, b))
        self.assertEqual({p.relative_to(a): p.read_bytes() for p in a.rglob('*') if p.is_file()},
                         {p.relative_to(b): p.read_bytes() for p in b.rglob('*') if p.is_file()})

    def test_existing_destination_is_never_overwritten(self):
        existing = self.root / 'existing'; existing.mkdir()
        sentinel = existing / 'keep'; sentinel.write_text('user data')
        with self.assertRaisesRegex(ValueError, 'must be new'):
            notices.stage(self.archive, existing)
        self.assertEqual(sentinel.read_text(), 'user data')
        self.assertEqual(list(existing.iterdir()), [sentinel])

    def test_output_symlink_and_ancestor_rejected_before_write(self):
        outside = self.root / 'outside'; outside.mkdir()
        link = self.root / 'link'; link.symlink_to(outside, target_is_directory=True)
        for target in (link, link / 'new'):
            with self.assertRaisesRegex(ValueError, 'symlink'):
                notices.stage(self.archive, target)
        self.assertEqual(list(outside.iterdir()), [])

    def test_archive_hash_tamper_rejected_before_output_creation(self):
        bad = self.root / 'archive.tgz'; changed = bytearray(self.original); changed[-1] ^= 1
        bad.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'archive hash'):
            notices.stage(bad, self.root / 'output')
        self.assertFalse((self.root / 'output').exists())

    def test_notice_and_rewritten_manifest_cannot_authorize_changes(self):
        bundle = self.clone_bundle()
        notice = bundle / 'MIT-LICENSE.txt'; notice.write_text('truncated notice')
        with self.assertRaises(ValueError):
            notices.stage(self.archive, self.root / 'output', bundle)
        manifest = bundle / 'input-manifest.json'; value = json.loads(manifest.read_text())
        value['files']['MIT-LICENSE.txt'] = {'bytes': notice.stat().st_size,
                                          'sha256': hashlib.sha256(notice.read_bytes()).hexdigest()}
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'unreviewed input manifest'):
            notices.stage(self.archive, self.root / 'output', bundle)
        self.assertFalse((self.root / 'output').exists())

    def test_missing_extra_and_symlink_bundle_members_rejected(self):
        bundle = self.clone_bundle()
        extra = bundle / 'extra'; extra.mkdir()
        with self.assertRaisesRegex(ValueError, 'membership'):
            notices.verify(self.archive, bundle)
        extra.rmdir()
        original = (bundle / 'NOTICE.txt').read_bytes(); (bundle / 'NOTICE.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'membership'):
            notices.verify(self.archive, bundle)
        outside = self.root / 'outside'; outside.write_bytes(original)
        (bundle / 'NOTICE.txt').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            notices.verify(self.archive, bundle)

    def test_rewritten_stage_manifest_cannot_authorize_notice_loss(self):
        output = self.root / 'staged'; notices.stage(self.archive, output)
        relative = 'documentation/notices/tr46-0.0.3/UNICODE-LICENSE.txt'
        path = output / relative; path.write_text('lost full license')
        receipt = output / 'stage-manifest.json'; value = json.loads(receipt.read_text())
        value['files'][relative] = {'bytes': path.stat().st_size,
                                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        receipt.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'staged content differs'):
            notices.verify_stage(output, self.archive)

    def test_stage_extra_file_symlink_and_changed_receipt_rejected(self):
        output = self.root / 'staged'; notices.stage(self.archive, output)
        extra = output / 'extra'; extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'membership'):
            notices.verify_stage(output, self.archive)
        extra.unlink()
        extra.symlink_to(self.archive)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            notices.verify_stage(output, self.archive)
        extra.unlink()
        receipt = output / 'stage-manifest.json'; value = json.loads(receipt.read_text())
        value['verification']['archive_sha256'] = '0' * 64; receipt.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'stage manifest differs'):
            notices.verify_stage(output, self.archive)

    def test_archive_parser_rejects_link_traversal_duplicate_and_oversized(self):
        for case in ('link', 'traversal', 'duplicate', 'oversized'):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w:gz') as tar:
                info = tarfile.TarInfo('package/../escape' if case == 'traversal' else 'package/index.js')
                data = b'x' * (300001 if case == 'oversized' else 1)
                if case == 'link':
                    info.type = tarfile.SYMTYPE; info.linkname = '/outside'; tar.addfile(info)
                else:
                    info.size = len(data); tar.addfile(info, io.BytesIO(data))
                    if case == 'duplicate':
                        tar.addfile(info, io.BytesIO(data))
            with self.subTest(case=case), self.assertRaises(ValueError):
                notices.read_archive(stream.getvalue())

    def test_unicode_conversion_rejects_invalid_codepoint_bounds(self):
        for source in (b'110000 ; valid\n', b'0020..0000 ; valid\n', b'gg ; valid\n'):
            with self.assertRaises(ValueError):
                notices.reconstruct_mapping(source)

    def test_tree_recomputation_rejects_forged_leaf_and_nested_tree(self):
        original = json.loads((notices.BUNDLE / 'provenance/selected-tree.json').read_bytes())
        expected = '7b86f219be315cb2c5b99768c2b1642cf2b262ae'
        notices.tree_entries(original, expected)
        for path in ('index.js', 'scripts'):
            changed = json.loads(json.dumps(original))
            next(row for row in changed['tree'] if row['path'] == path)['sha'] = '0' * 40
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'tree content differs'):
                notices.tree_entries(changed, expected)

    def test_api_tree_sha_is_not_mistaken_for_the_root_tree_hash(self):
        tree = json.loads((notices.BUNDLE / 'provenance/selected-tree.json').read_bytes())
        self.assertEqual(tree['sha'], 'a8009f9ce80ff5dbe71dd71e203afe4e4c878d28')
        with self.assertRaisesRegex(ValueError, 'tree content differs'):
            notices.tree_entries(tree, tree['sha'])


if __name__ == '__main__':
    unittest.main()
