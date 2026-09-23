"""Real Git recovery and confinement checks; no mocked successful restorations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[2] / "build-support/source_restore/common.py"
spec = importlib.util.spec_from_file_location("source_restore_common_tests", MODULE)
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


class CustodyTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ambisgis-source-restore-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def repository(self, name="producer", *, notices=True):
        repo = self.root / name
        repo.mkdir()
        common.git(repo, "init", "--template=", "--initial-branch=main")
        if notices:
            (repo / "LICENSE").write_text("Synthetic test source. Copyright test author.\n")
        (repo / "source.txt").write_text("first selected implementation\n")
        self.commit(repo, "Initial synthetic source")
        return repo

    def commit(self, repo, message):
        common.git(repo, "add", "--all")
        common.git(repo, "-c", "user.name=Source restoration test",
                   "-c", "user.email=source-restore-test@example.invalid",
                   "commit", "-m", message)
        return common.git(repo, "rev-parse", "HEAD").decode().strip()

    def archive(self, repo, name="retained.bundle", *revisions):
        bundle = self.root / name
        common.git(repo, "bundle", "create", str(bundle), *(revisions or ("--all",)))
        return bundle


class SourcePathIntegrityTests(CustodyTestCase):
    def test_verified_blob_rejects_changed_bytes_and_missing_asset(self):
        blob = self.root / "asset.bin"
        blob.write_bytes(b"known source input")
        digest = common.sha(blob)
        self.assertEqual(common.verified_file(self.root, "asset.bin", digest), blob)
        blob.write_bytes(b"corrupt source inp")
        with self.assertRaisesRegex(ValueError, "Changed input bytes"):
            common.verified_file(self.root, "asset.bin", digest)
        with self.assertRaises((ValueError, FileNotFoundError)):
            common.verified_file(self.root, "missing-schema.xsd", digest)

    def test_wrong_size_and_invalid_digest_fail_closed(self):
        blob = self.root / "blob"
        blob.write_bytes(b"abc")
        with self.assertRaisesRegex(ValueError, "Changed input size"):
            common.verified_file(self.root, "blob", common.sha(blob), 4)
        with self.assertRaisesRegex(ValueError, "Invalid SHA256"):
            common.verified_file(self.root, "blob", "not a digest")

    def test_fresh_output_reuse_is_rejected_without_overwrite(self):
        output = common.fresh(self.root, "output")
        marker = output / "preserved"
        marker.write_text("earlier evidence")
        with self.assertRaisesRegex(ValueError, "Output already exists"):
            common.fresh(self.root, "output")
        self.assertEqual(marker.read_text(), "earlier evidence")

    def test_traversal_and_ambiguous_paths_are_rejected(self):
        for relative in ("../escape", "/tmp/escape", "a/../escape", "a//b",
                         "./escape", "a\\b", "a/", "", "bad\x00path"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                common.confined(self.root, relative, exists=False)

    def test_symlink_parent_and_symlink_root_are_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "alias"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            common.fresh(self.root, "alias/escaped-output")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            common.fresh(link, "escaped-output")
        self.assertFalse((outside / "escaped-output").exists())

    def test_symlink_input_cannot_substitute_valid_blob(self):
        target = self.root / "target"
        target.write_bytes(b"valid source")
        (self.root / "alias").symlink_to(target)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            common.verified_file(self.root, "alias", common.sha(target))


class SourceBundleRecoveryTests(CustodyTestCase):
    def test_fresh_recovery_retains_ancestry_refs_notices_and_independent_objects(self):
        repo = self.repository()
        base = common.git(repo, "rev-parse", "HEAD").decode().strip()
        common.git(repo, "tag", "synthetic-base", base)
        (repo / "source.txt").write_text("approved second implementation\n")
        selected = self.commit(repo, "Approved product change")
        bundle = self.archive(repo)
        header = common.bundle_header(bundle)
        recovered = self.root / "recovered"
        actual = common.restore_bundle(bundle, recovered, selected, header["refs"])
        self.assertEqual(actual["prerequisites"], [])
        self.assertEqual(common.git(recovered, "rev-parse", "HEAD").decode().strip(), selected)
        common.git(recovered, "merge-base", "--is-ancestor", base, selected)
        self.assertEqual(common.git(repo, "rev-parse", "HEAD^{tree}"),
                         common.git(recovered, "rev-parse", "HEAD^{tree}"))
        self.assertEqual((recovered / "source.txt").read_text(), "approved second implementation\n")
        self.assertEqual(common.git(recovered, "rev-parse", "refs/custody/tags/synthetic-base")
                         .decode().strip(), base)
        audit = common.audit_assets(recovered)
        self.assertIn("LICENSE", [x["path"] for x in audit["notice_paths"]])
        self.assertEqual(audit["lfs_pointers"], [])
        common.independent(recovered)
        self.assertTrue(all(p.stat().st_nlink == 1 for p in
                            (recovered / ".git/objects").rglob("*") if p.is_file()))
        # The recovery must survive removal of the producer and retained bundle.
        renamed = repo.with_name("producer-unavailable")
        repo.rename(renamed)
        bundle.rename(bundle.with_suffix(".unavailable"))
        common.git(recovered, "fsck", "--full")
        self.assertEqual(common.git(recovered, "show", base + ":source.txt"),
                         b"first selected implementation\n")

    def test_product_delta_restores_with_its_retained_predecessor(self):
        repo = self.repository()
        base = common.git(repo, "rev-parse", "HEAD").decode().strip()
        retained_base = self.archive(repo, "base.bundle")
        (repo / "source.txt").write_text("approved recovered product implementation\n")
        selected = self.commit(repo, "Reviewed local product delta")
        delta = self.archive(repo, "product.bundle", "main", "^" + base)
        output = self.root / "restored-chain"
        common.restore_bundle(retained_base, output, base)
        self.assertEqual(common.bundle_header(delta)["prerequisites"], [base])
        common.git(output, "bundle", "verify", str(delta))
        common.git(output, "bundle", "unbundle", str(delta))
        common.git(output, "checkout", "--detach", selected)
        common.git(output, "merge-base", "--is-ancestor", base, selected)
        self.assertEqual(common.git(output, "rev-parse", "HEAD^{tree}"),
                         common.git(repo, "rev-parse", "HEAD^{tree}"))
        repo.rename(self.root / "producer-unavailable")
        retained_base.rename(self.root / "base-unavailable")
        delta.rename(self.root / "delta-unavailable")
        common.independent(output)
        common.git(output, "fsck", "--full")
        self.assertEqual((output / "source.txt").read_text(),
                         "approved recovered product implementation\n")

    def test_product_delta_fails_when_required_base_commit_is_absent(self):
        repo = self.repository()
        base = common.git(repo, "rev-parse", "HEAD").decode().strip()
        (repo / "source.txt").write_text("product change\n")
        self.commit(repo, "Product delta")
        delta = self.archive(repo, "product.bundle", "main", "^" + base)
        empty = self.root / "without-predecessor"
        empty.mkdir()
        common.git(empty, "init", "--template=", "--initial-branch=empty")
        with self.assertRaisesRegex(ValueError, "prerequisite"):
            common.git(empty, "bundle", "verify", str(delta))
        self.assertFalse((empty / "success.json").exists())

    def test_corrupt_product_delta_fails_after_correct_predecessor_restore(self):
        repo = self.repository()
        base = common.git(repo, "rev-parse", "HEAD").decode().strip()
        retained_base = self.archive(repo, "base.bundle")
        (repo / "source.txt").write_text("product change\n")
        self.commit(repo, "Product delta")
        delta = self.archive(repo, "product.bundle", "main", "^" + base)
        data = bytearray(delta.read_bytes())
        data[-15] ^= 0xFF
        delta.write_bytes(data)
        output = self.root / "restored-base"
        common.restore_bundle(retained_base, output, base)
        with self.assertRaises(ValueError):
            common.git(output, "bundle", "unbundle", str(delta))
        self.assertEqual(common.git(output, "rev-parse", "HEAD").decode().strip(), base)
        self.assertFalse((output / "success.json").exists())

    def test_repository_parent_symlink_is_rejected_before_output_write(self):
        repo = self.repository()
        selected = common.git(repo, "rev-parse", "HEAD").decode().strip()
        bundle = self.archive(repo)
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "alias"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            common.restore_bundle(bundle, link / "recovered", selected)
        self.assertFalse((outside / "recovered").exists())

    def test_corrupt_bundle_fails_without_success_receipt(self):
        repo = self.repository()
        selected = common.git(repo, "rev-parse", "HEAD").decode().strip()
        bundle = self.archive(repo)
        data = bytearray(bundle.read_bytes())
        data[-15] ^= 0xFF
        bundle.write_bytes(data)
        output = self.root / "failed-recovery"
        with self.assertRaises(ValueError):
            common.restore_bundle(bundle, output, selected)
        self.assertFalse((output / "success.json").exists())

    def test_real_incremental_bundle_requires_explicit_predecessor_chain(self):
        repo = self.repository()
        base = common.git(repo, "rev-parse", "HEAD").decode().strip()
        (repo / "source.txt").write_text("second revision\n")
        selected = self.commit(repo, "Second revision")
        incremental = self.archive(repo, "incremental.bundle", "main", "^" + base)
        self.assertIn(base, common.bundle_header(incremental)["prerequisites"])
        output = self.root / "recovered"
        with self.assertRaisesRegex(ValueError, "predecessor"):
            common.restore_bundle(incremental, output, selected)
        self.assertFalse(output.exists())

    def test_wrong_selected_revision_is_rejected(self):
        bundle = self.archive(self.repository())
        output = self.root / "wrong-revision"
        with self.assertRaises(ValueError):
            common.restore_bundle(bundle, output, "f" * 40)
        self.assertFalse((output / "success.json").exists())

    def test_changed_bundle_ref_identity_is_rejected_before_output(self):
        repo = self.repository()
        selected = common.git(repo, "rev-parse", "HEAD").decode().strip()
        bundle = self.archive(repo)
        output = self.root / "changed-ref"
        with self.assertRaisesRegex(ValueError, "Bundle refs changed"):
            common.restore_bundle(bundle, output, selected, {"refs/heads/other": selected})
        self.assertFalse(output.exists())

    def test_existing_repository_cannot_be_overwritten(self):
        repo = self.repository()
        selected = common.git(repo, "rev-parse", "HEAD").decode().strip()
        bundle = self.archive(repo)
        marker = repo / "owner-file"
        marker.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "collision"):
            common.restore_bundle(bundle, repo, selected)
        self.assertEqual(marker.read_text(), "preserve")

    def test_environment_config_injection_does_not_change_restoration(self):
        repo = self.repository()
        selected = common.git(repo, "rev-parse", "HEAD").decode().strip()
        bundle = self.archive(repo)
        output = self.root / "recovered"
        with patch.dict(os.environ, {"GIT_OBJECT_DIRECTORY": "/nonexistent/injected",
                                     "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(repo / ".git/objects"),
                                     "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "filter.lfs.smudge",
                                     "GIT_CONFIG_VALUE_0": "exit 99"}):
            common.restore_bundle(bundle, output, selected)
        common.independent(output)

    def test_alternates_and_hardlinked_object_stores_are_rejected(self):
        repo = self.repository()
        selected = common.git(repo, "rev-parse", "HEAD").decode().strip()
        output = self.root / "recovered"
        common.restore_bundle(self.archive(repo), output, selected)
        alternate = output / ".git/objects/info/alternates"
        alternate.write_text(str(repo / ".git/objects") + "\n")
        with self.assertRaisesRegex(ValueError, "alternates"):
            common.independent(output)
        alternate.unlink()
        object_file = next(p for p in (output / ".git/objects").rglob("*") if p.is_file())
        os.link(object_file, self.root / "shared-object")
        with self.assertRaisesRegex(ValueError, "hardlinked"):
            common.independent(output)

    def test_symlink_object_store_root_is_rejected(self):
        repo = self.repository()
        objects = repo / ".git/objects"
        moved = self.root / "external-objects"
        objects.rename(moved)
        objects.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            common.independent(repo)


class SourceAssetCoverageTests(CustodyTestCase):
    def test_missing_notices_are_not_successful_asset_custody(self):
        repo = self.repository(notices=False)
        with self.assertRaisesRegex(ValueError, "copyright/license"):
            common.audit_assets(repo)

    def test_missing_and_corrupt_lfs_payloads_fail(self):
        repo = self.repository()
        payload = b"required LFS source asset"
        digest = hashlib.sha256(payload).hexdigest()
        (repo / "asset.dat").write_text("version https://git-lfs.github.com/spec/v1\n"
                                       "oid sha256:" + digest + "\nsize " + str(len(payload)) + "\n")
        self.commit(repo, "Add required LFS pointer")
        with self.assertRaisesRegex(ValueError, "Missing required LFS"):
            common.audit_assets(repo)
        retained = self.root / "retained-lfs"
        retained.write_bytes(payload)
        audit = common.audit_assets(repo, {digest: retained})
        self.assertEqual(audit["lfs_pointers"][0]["sha256"], digest)
        retained.write_bytes(b"corrupt LFS asset")
        with self.assertRaisesRegex(ValueError, "Invalid LFS"):
            common.audit_assets(repo, {digest: retained})

    def test_unsupported_lfs_pointer_is_rejected(self):
        repo = self.repository()
        (repo / "asset.dat").write_text("version https://git-lfs.github.com/spec/v1\ninvalid\n")
        self.commit(repo, "Add malformed pointer")
        with self.assertRaisesRegex(ValueError, "Malformed/unsupported LFS"):
            common.audit_assets(repo)

    def test_source_symlink_escape_is_rejected(self):
        repo = self.repository()
        (repo / "escaping-source").symlink_to("../outside")
        self.commit(repo, "Add unsafe source symlink")
        with self.assertRaisesRegex(ValueError, "Source symlink escape"):
            common.audit_assets(repo)

    def test_internal_source_symlink_is_allowed(self):
        repo = self.repository()
        (repo / "source-alias").symlink_to("source.txt")
        self.commit(repo, "Add confined source symlink")
        self.assertGreater(common.audit_assets(repo)["tracked_entries"], 0)


class SourceReceiptVerificationTests(CustodyTestCase):
    def load_cli(self):
        cli_path = Path(__file__).resolve().parents[1] / "tools/restore_sources.py"
        cli_spec = importlib.util.spec_from_file_location("source_restore_cli_tests", cli_path)
        cli = importlib.util.module_from_spec(cli_spec)
        cli_spec.loader.exec_module(cli)
        return cli

    def test_cli_import_does_not_reuse_another_components_common_module(self):
        import sys
        import types
        with patch.dict(sys.modules, {"common": types.ModuleType("unrelated_common")}):
            cli = self.load_cli()
            self.assertEqual(cli.sha(Path(__file__)), common.sha(Path(__file__)))

    def generated_fixture(self):
        cli = self.load_cli()
        run = self.root / "generated-run"
        (run / "derived/evidence").mkdir(parents=True)
        artifact = run / "derived/generated/qgis/algorithms.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text('[{"name":"synthetic"}]')
        expected = {"path":"algorithms.json", "sha256":common.sha(artifact), "bytes":artifact.stat().st_size}
        evidence = run / "derived/evidence/qgis-generated-source.json"
        common.save(evidence, {"added":[expected]})
        candidate = {"records":[{"id":"qgis-generated-source", "sha256":common.sha(evidence), "bytes":evidence.stat().st_size}]}
        recipes = {"qgis":{"generated":{"path":"generated/qgis/algorithms.json", "sha256":expected["sha256"], "records":1}}}
        common.save(run / "recipes.json", recipes)
        return cli, run, artifact, candidate, recipes

    def test_generated_output_is_checked_against_bound_producer_evidence(self):
        cli, run, artifact, candidate, recipes = self.generated_fixture()
        self.assertEqual(cli.verify_generated_metadata(run, {}, candidate), [])
        artifact.write_text('[{"name":"tampered!"}]')
        with self.assertRaisesRegex(ValueError, "Changed input"):
            cli.verify_generated_metadata(run, {}, candidate)

    def test_unrecorded_generated_summary_mismatch_is_rejected(self):
        cli, run, artifact, candidate, recipes = self.generated_fixture()
        recipes["qgis"]["generated"]["sha256"] = "0" * 64
        (run / "recipes.json").write_text(json.dumps(recipes))
        with self.assertRaises((ValueError, FileNotFoundError)):
            cli.verify_generated_metadata(run, {"recipes_sha256":"f" * 64}, candidate)

    def test_receipt_cannot_drop_duplicate_or_substitute_accepted_roots(self):
        cli = self.load_cli()
        candidate_path = Path(__file__).resolve().parents[1] / "candidates/fnd-02-candidate.json"
        candidate = json.loads(candidate_path.read_text())
        roots = [{"id": r["id"], "repository": r["repository"],
                  "repository_id": r["repository_id"], "base_commit": r["commit"],
                  "relative_path": "repos/" + r["id"]} for r in candidate["roots"]]
        cli.receipt_identity(candidate, {"roots": roots})
        for altered in (roots[:-1], roots + [dict(roots[0])]):
            with self.subTest(shape=len(altered)), self.assertRaisesRegex(ValueError, "exactly once"):
                cli.receipt_identity(candidate, {"roots": altered})
        for field, replacement in (("repository_id", -1), ("repository", "aloerch/unrelated"),
                                   ("base_commit", "f" * 40), ("relative_path", "../outside")):
            altered = [dict(r) for r in roots]
            altered[0][field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "identity differs"):
                cli.receipt_identity(candidate, {"roots": altered})

    def test_empty_root_receipt_cannot_report_success(self):
        cli_path = Path(__file__).resolve().parents[1] / "tools/restore_sources.py"
        cli_spec = importlib.util.spec_from_file_location("source_restore_cli_tests", cli_path)
        cli = importlib.util.module_from_spec(cli_spec)
        cli_spec.loader.exec_module(cli)
        run = self.root / "run"
        run.mkdir()
        common.save(run / "recovery.json", {
            "candidate_sha256": cli.MANIFEST_SHA256,
            "roots": [], "recovered_files": [], "scope": "incomplete receipt",
            "remaining_blockers": [],
        })
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)):
            cli.verify_run(self.root, run)


if __name__ == "__main__":
    unittest.main()
