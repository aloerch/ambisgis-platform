"""Real independent Git object checks for source delivery, without GitHub writes."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("ambisgis_delivery", Path(__file__).parents[1] / "tools/verify_source_delivery.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source"
        self.source.mkdir()
        self.call(self.source, "init", "--template=")
        (self.source / "LICENSE").write_text("Original source terms\n")
        (self.source / "code").write_text("before\n")
        self.call(self.source, "add", ".")
        self.call(self.source, "commit", "-m", "base")
        base = self.call(self.source, "rev-parse", "HEAD")
        base_tree = self.call(self.source, "rev-parse", "HEAD^{tree}")
        (self.source / "code").write_text("after\n")
        self.call(self.source, "commit", "-am", "product")
        commit = self.call(self.source, "rev-parse", "HEAD")
        self.repo = root / "remote-recovery.git"
        self.call(root, "clone", "--bare", "--no-local", str(self.source), str(self.repo))
        self.call(self.repo, "update-ref", delivery.REF, commit)
        self.row = {"accepted_base_commit": base, "accepted_base_tree": base_tree,
                    "proposed_commit": commit, "proposed_tree": self.call(self.repo, "rev-parse", commit + "^{tree}"),
                    "changed_paths": ["M\tcode"], "notice_paths": ["LICENSE"]}

    def call(self, repo, *args):
        return subprocess.check_output(["git", "-c", "user.name=Delivery test", "-c", "user.email=test@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def test_exact_history_diff_and_notice_pass(self):
        result = delivery.verify_objects(self.repo, self.row)
        self.assertEqual(result["history_commits"], 2)
        self.assertEqual(result["fsck_exit_code"], 0)
        self.assertEqual(result["changed_paths"], ["M\tcode"])
        self.assertEqual(len(result["notices"]), 1)

    def test_wrong_commit_refused(self):
        self.call(self.repo, "update-ref", delivery.REF, self.row["accepted_base_commit"])
        with self.assertRaisesRegex(ValueError, "Remote commit mismatch"):
            delivery.verify_objects(self.repo, self.row)

    def test_wrong_tree_refused(self):
        row = dict(self.row, proposed_tree=self.row["accepted_base_tree"])
        with self.assertRaisesRegex(ValueError, "Remote tree mismatch"):
            delivery.verify_objects(self.repo, row)

    def test_wrong_change_scope_refused(self):
        with self.assertRaisesRegex(ValueError, "Source diff"):
            delivery.verify_objects(self.repo, dict(self.row, changed_paths=[]))

    def test_missing_notice_refused(self):
        with self.assertRaisesRegex(ValueError, "Missing or ambiguous notice"):
            delivery.verify_objects(self.repo, dict(self.row, notice_paths=["NOT-HERE"]))

    def test_alternate_object_store_refused(self):
        (self.repo / "objects/info/alternates").write_text(str(self.source / ".git/objects") + "\n")
        with self.assertRaisesRegex(ValueError, "Shared object store"):
            delivery.verify_objects(self.repo, self.row)

    def test_shallow_store_refused(self):
        (self.repo / "shallow").write_text(self.row["proposed_commit"] + "\n")
        with self.assertRaisesRegex(ValueError, "Shallow history"):
            delivery.verify_objects(self.repo, self.row)
