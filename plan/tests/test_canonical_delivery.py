"""Actual minimal-store integrity guards; full-history evidence stays distinct."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('canonical_delivery', Path(__file__).parents[1] / 'tools/verify_canonical_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class CanonicalDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name); self.source = root / 'source'; self.source.mkdir()
        self.call(self.source, 'init', '--template=')
        (self.source / 'LICENSE').write_text('Original notice\n')
        (self.source / 'code').write_text('source\n')
        self.call(self.source, 'add', '.'); self.call(self.source, 'commit', '-m', 'base')
        self.call(self.source, 'branch', 'ambisgis/main')
        self.repo = root / 'tip.git'
        self.call(root, 'clone', '--bare', '--depth=1', '--single-branch', '--branch', 'ambisgis/main', self.source.as_uri(), str(self.repo))
        commit = self.call(self.repo, 'rev-parse', delivery.REF)
        tree = self.call(self.repo, 'rev-parse', delivery.REF + '^{tree}')
        self.row = dict(root_id='fixture', repository_id=1, repository='aloerch/fixture', proposed_commit=commit, proposed_tree=tree)
        self.history = dict(root_id='fixture', repository_id=1, repository='aloerch/fixture', commit=commit, tree=tree,
                            status='verified', fsck_exit_code=0, history_commits=1, changed_paths=[], gitlinks=[],
                            notices=[dict(path='LICENSE', entry=delivery.previous.tree_entry(self.repo, delivery.REF, 'LICENSE'))])

    def call(self, repo, *args):
        return subprocess.check_output(['git', '-c', 'user.name=Canonical test', '-c', 'user.email=test@example.invalid',
            '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def test_exact_source_tree_and_notices(self):
        r = delivery.verify_tip(self.repo, self.row, self.history)
        self.assertEqual(r['source_entries'], 2)
        self.assertEqual(r['notice_paths_verified'], 1)
        self.assertEqual(r['fsck_exit_code'], 0)

    def test_wrong_tree(self):
        with self.assertRaisesRegex(ValueError, 'tree mismatch'):
            delivery.verify_tip(self.repo, dict(self.row, proposed_tree='0' * 40), self.history)

    def test_wrong_history_identity(self):
        with self.assertRaisesRegex(ValueError, 'Historical recovery identity'):
            delivery.verify_tip(self.repo, self.row, dict(self.history, repository_id=2))

    def test_bad_prior_receipt(self):
        for key, value in [('status', 'failed'), ('fsck_exit_code', 1), ('commit', '0' * 40)]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Historical recovery identity'):
                delivery.verify_tip(self.repo, self.row, dict(self.history, **{key: value}))

    def test_changed_notice(self):
        h = copy.deepcopy(self.history); h['notices'][0]['entry'] = '100644 blob ' + '0' * 40
        with self.assertRaisesRegex(ValueError, 'Original notice'):
            delivery.verify_tip(self.repo, self.row, h)

    def test_extra_ref(self):
        self.call(self.repo, 'update-ref', 'refs/heads/unexpected', self.row['proposed_commit'])
        with self.assertRaisesRegex(ValueError, 'Unexpected refs'):
            delivery.verify_tip(self.repo, self.row, self.history)

    def test_alternate_refused(self):
        (self.repo / 'objects/info/alternates').write_text(str(self.source / '.git/objects') + '\n')
        with self.assertRaisesRegex(ValueError, 'Shared object'):
            delivery.verify_tip(self.repo, self.row, self.history)

    def test_wrong_shallow_boundary(self):
        (self.repo / 'shallow').write_text('0' * 40 + '\n')
        with self.assertRaisesRegex(ValueError, 'shallow boundary'):
            delivery.verify_tip(self.repo, self.row, self.history)

    def test_missing_source_blob_fails_integrity(self):
        # Unpack objects and remove a required source payload from the otherwise exact tree.
        bare = self.repo.parent / 'broken.git'; bare.mkdir()
        self.call(bare, 'init', '--bare', '--template=')
        source_objects = self.source / '.git/objects'
        import shutil
        shutil.copytree(source_objects, bare / 'objects', dirs_exist_ok=True)
        self.call(bare, 'update-ref', delivery.REF, self.row['proposed_commit'])
        (bare / 'shallow').write_text(self.row['proposed_commit'] + '\n')
        blob = self.call(bare, 'rev-parse', delivery.REF + ':code')
        (bare / 'objects' / blob[:2] / blob[2:]).unlink()
        with self.assertRaises(RuntimeError):
            delivery.verify_tip(bare, self.row, self.history)
