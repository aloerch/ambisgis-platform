"""Adversarial local eligibility tests; these are not product acceptance."""
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools import delivery_gate as gate

BASE, HEAD = "a" * 40, "b" * 40
REPO = "aloerch/ambisgis-platform"
FILES = ["plan/tools/delivery_gate.py", "plan/tests/test_delivery_gate.py"]


def fixture():
    policy = {"repository": REPO, "repository_id": 1376927351, "pr": 72,
              "required_checks": [{"name": "package-and-schema", "kind": "check", "app_id": 42},
                                  {"name": "delegated-review", "kind": "status", "creator": "aloerch"}],
              "required_tests": [{"command": ["python3", "-m", "unittest"], "kind": "package"}]}
    evidence = {"repository": REPO, "repository_id": 1376927351, "pr": 72, "base_sha": BASE,
                "head_sha": HEAD, "files_sha256": gate.files_digest(FILES),
                "review": {"mechanism": "separate-agent", "reviewer": "review-session", "implementer": "author-session",
                           "findings": [], "concerns": [], "prior_acceptance_sha": BASE, "scrutinized_controls": FILES,
                           "checked_boundaries": ["scope", "source", "rights", "secrets", "destructive-actions"],
                           "transcript": {"path": "review.txt", "sha256": "c" * 64}},
                "tests": [{"command": ["python3", "-m", "unittest"], "kind": "package", "exit_code": 0,
                           "skipped": 0, "mocked": False, "log": {"path": "tests.txt", "sha256": "d" * 64}}]}
    repo = {"id": 1376927351, "full_name": REPO, "owner": {"login": "aloerch"}}
    pr = {"number": 72, "state": "open", "draft": False, "merged": False, "mergeable": True,
          "user": {"login": "aloerch"}, "base": {"ref": "ambisgis/main", "sha": BASE, "repo": repo},
          "head": {"ref": "delivery/change", "sha": HEAD, "repo": repo}, "changed_files": 2}
    state = {"user": {"login": "aloerch"}, "repository": repo, "pr": pr, "base_sha": BASE,
             "files": FILES, "required": [], "threads": [], "reviews": [],
             "checks": [{"id": 1, "name": "package-and-schema", "app": {"id": 42}, "head_sha": HEAD,
                         "status": "completed", "conclusion": "success"}],
             "statuses": [{"id": 2, "context": "delegated-review", "creator": {"login": "aloerch"}, "state": "success"}]}
    return policy, evidence, state


class DecisionTests(unittest.TestCase):
    def test_exact_reviewed_tested_head_is_eligible(self):
        self.assertTrue(gate.evaluate(*fixture())["eligible"])

    def test_wrong_identity_author_fork_base_and_incomplete_pr_deny(self):
        mutations = [lambda s: s["repository"].update(id=99), lambda s: s["pr"]["user"].update(login="outside"),
                     lambda s: s["pr"]["head"].update(repo={"id": 99, "full_name": "outside/fork"}),
                     lambda s: s["user"].update(login="outside"), lambda s: s["pr"]["base"].update(ref="main"),
                     lambda s: s["pr"].update(changed_files=3), lambda s: s["pr"].update(mergeable=None),
                     lambda s: s["pr"].update(draft=True), lambda s: s.update(base_sha="e" * 40)]
        for mutate in mutations:
            p, e, s = fixture()
            mutate(s)
            with self.subTest(mutate=mutate), self.assertRaises(gate.Denied):
                gate.evaluate(p, e, s)

    def test_external_policy_cannot_expand_allowlist(self):
        p, e, s = fixture()
        p["repository"] = "aloerch/weaveatlas"
        with self.assertRaises(gate.Denied):
            gate.evaluate(p, e, s)

    def test_changed_bindings_require_new_evidence(self):
        for key, value in [("head_sha", "c" * 40), ("base_sha", "d" * 40), ("files_sha256", "e" * 64)]:
            p, e, s = fixture()
            e[key] = value
            with self.subTest(key=key), self.assertRaises(gate.Denied):
                gate.evaluate(p, e, s)

    def test_missing_pending_failed_stale_wrong_app_skipped_checks_deny(self):
        for updates in [None, {"status": "queued"}, {"conclusion": "failure"}, {"head_sha": BASE},
                        {"app": {"id": 43}}, {"conclusion": "skipped"}]:
            p, e, s = fixture()
            if updates is None:
                s["checks"] = []
            else:
                s["checks"][0].update(updates)
            with self.subTest(updates=updates), self.assertRaises(gate.Denied):
                gate.evaluate(p, e, s)

    def test_new_failure_supersedes_old_success(self):
        for collection, failure in [("checks", {"conclusion": "failure"}), ("statuses", {"state": "pending"})]:
            p, e, s = fixture()
            new = copy.deepcopy(s[collection][0])
            new.update(id=3, **failure)
            s[collection].append(new)
            with self.assertRaises(gate.Denied):
                gate.evaluate(p, e, s)

    def test_live_required_check_unresolved_threads_changes_requested_deny(self):
        for key, value in [("required", [{"context": "security", "app_id": 42}]),
                           ("threads", [{"isResolved": False, "isOutdated": True}]),
                           ("reviews", [{"id": 1, "user": {"login": "reviewer"}, "state": "CHANGES_REQUESTED"}])]:
            p, e, s = fixture()
            s[key] = value
            with self.assertRaises(gate.Denied):
                gate.evaluate(p, e, s)

    def test_findings_concerns_self_review_missing_control_scrutiny_deny(self):
        for key, value in [("findings", [{"severity": "high", "resolved": False}]),
                           ("concerns", ["unexpected-source-or-rights-change"]), ("concerns", ["secret"]),
                           ("reviewer", "author-session"), ("mechanism", "self-review"),
                           ("prior_acceptance_sha", HEAD), ("scrutinized_controls", []), ("checked_boundaries", [])]:
            p, e, s = fixture()
            e["review"][key] = value
            with self.subTest(key=key), self.assertRaises(gate.Denied):
                gate.evaluate(p, e, s)

    def test_missing_unrelated_failed_skipped_mocked_product_tests_deny(self):
        for update in [None, {"command": ["true"]}, {"exit_code": 1}, {"skipped": 1}, {"exit_code": False}]:
            p, e, s = fixture()
            if update is None:
                e["tests"] = []
            else:
                e["tests"][0].update(update)
            with self.assertRaises(gate.Denied):
                gate.evaluate(p, e, s)
        p, e, s = fixture()
        p["required_tests"][0]["kind"] = "database"
        e["tests"][0].update(kind="database", mocked=True)
        with self.assertRaises(gate.Denied):
            gate.evaluate(p, e, s)


class TransportTests(unittest.TestCase):
    def test_partial_graphql_errors_and_raw_diagnostics_deny_without_leak(self):
        for result in [SimpleNamespace(returncode=0, stdout='{"errors":[{"message":"SECRET"}],"data":{}}', stderr="SECRET"),
                       SimpleNamespace(returncode=1, stdout="SECRET", stderr="SECRET")]:
            api = gate.GitHub(runner=lambda *a, **kw: result)
            with self.assertRaises(gate.Denied) as error:
                api.read("graphql", {"query": "query { viewer { login } }"})
            self.assertNotIn("SECRET", str(error.exception))

    def test_only_read_queries_no_shell(self):
        calls = []
        def run(args, **kw):
            calls.append((args, kw))
            return SimpleNamespace(returncode=0, stdout='{"data":{}}', stderr="")
        api = gate.GitHub(runner=run, host_gh=True)
        api.read("graphql", {"query": "query { viewer { login } }"})
        self.assertEqual(calls[0][0][:4], ["flatpak-spawn", "--host", "gh", "api"])
        self.assertNotIn("shell", calls[0][1])
        for endpoint, payload in [("graphql", {"query": "mutation { deleteRepository }"}), ("repos/a/b", {})]:
            with self.assertRaises(gate.Denied):
                api.read(endpoint, payload)

    def test_pagination_complete_and_bounded(self):
        api = gate.GitHub()
        seen = []
        def read(endpoint):
            seen.append(endpoint)
            return list(range(100)) if len(seen) == 1 else [100]
        api.read = read
        self.assertEqual(len(api.pages("some/endpoint")), 101)
        self.assertIn("page=2", seen[1])
        api.read = lambda endpoint: list(range(100))
        with self.assertRaises(gate.Denied):
            api.pages("some/endpoint")


class TrustedEvidenceTests(unittest.TestCase):
    def test_private_external_transcripts_and_digests_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "review.txt"
            path.write_text("actual separate-context review\n")
            path.chmod(0o600)
            ref = {"path": "review.txt", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            gate.verify_artifact(root, ref)
            path.write_text("PASS")
            with self.assertRaises(gate.Denied):
                gate.verify_artifact(root, ref)
            path.chmod(0o644)
            with self.assertRaises(gate.Denied):
                gate.private_file(path)

    def test_checkout_evidence_and_symlink_escape_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            path = root / "evidence.json"
            path.write_text("{}")
            path.chmod(0o600)
            with self.assertRaises(gate.Denied):
                gate.private_file(path)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.write_text("{}")
            target.chmod(0o600)
            (root / "link").symlink_to(target)
            with self.assertRaises(gate.Denied):
                gate.private_file(root / "link")


class LiveStateParsingTests(unittest.TestCase):
    def snapshot(self, *, move_base=False, protected=False):
        policy, evidence, state = fixture()
        api = gate.GitHub()
        reads = []
        def read(endpoint, payload=None):
            reads.append(endpoint)
            path = f"repos/{REPO}"
            if endpoint == "user":
                return state["user"]
            if endpoint == path:
                return state["repository"]
            if endpoint == f"{path}/pulls/72":
                return copy.deepcopy(state["pr"])
            if endpoint == f"{path}/branches/ambisgis%2Fmain":
                moved = move_base and reads.count(endpoint) == 2
                return {"protected": protected, "commit": {"sha": "c" * 40 if moved else BASE}}
            if endpoint.endswith("/protection"):
                return {"required_status_checks": {"checks": [{"context": "package-and-schema", "app_id": 42}]}}
            if "/rules/branches/" in endpoint:
                return [{"type": "required_status_checks", "parameters": {"required_status_checks": [
                    {"context": "delegated-review", "integration_id": None}]}}]
            if endpoint == "graphql":
                self.assertIn("reviewThreads", payload["query"])
                return {"data": {"repository": {"pullRequest": {"reviewThreads": {
                    "nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
            if "/files?" in endpoint:
                return [{"filename": name} for name in FILES]
            if "/check-runs?" in endpoint:
                return {"check_runs": state["checks"]}
            if "/statuses?" in endpoint:
                return state["statuses"]
            if "/reviews?" in endpoint:
                return []
            self.fail(f"Unexpected endpoint {endpoint}")
        api.read = read
        return api.snapshot(policy)

    def test_parser_collects_live_checks_statuses_effective_rules_and_protection(self):
        for protected in (False, True):
            state = self.snapshot(protected=protected)
            policy, evidence, unused = fixture()
            self.assertTrue(gate.evaluate(policy, evidence, state)["eligible"])
            self.assertEqual(len(state["required"]), 2 if protected else 1)

    def test_base_movement_during_api_reads_denies_snapshot(self):
        with self.assertRaises(gate.Denied):
            self.snapshot(move_base=True)


class BaselineTests(unittest.TestCase):
    def run_checkout(self, *, baseline=None, bootstrap=None, dirty=False):
        policy, evidence, state = fixture()
        if bootstrap is not None:
            policy["bootstrap_gate_sha256"] = bootstrap
        def fake_command(args, **kwargs):
            action = args[3:]
            if action[0] == "remote":
                return f"https://github.com/{REPO}.git\n".encode()
            if action[0] == "rev-parse":
                return HEAD.encode()
            if action[0] == "branch":
                return b"delivery/change\n"
            if action[0] == "status":
                return b" M plan/tools/delivery_gate.py" if dirty else b""
            if action[0] == "ls-tree":
                return gate.GATE_PATH.encode() if baseline is not None else b""
            if action[0] == "show":
                return baseline
            self.fail(f"Unexpected git command: {action}")
        with patch.object(gate, "command", fake_command):
            gate.verify_checkout(Path("/unused"), state, policy)

    def test_initial_bootstrap_requires_explicit_exact_external_digest(self):
        with self.assertRaises(gate.Denied):
            self.run_checkout()
        with self.assertRaises(gate.Denied):
            self.run_checkout(bootstrap="0" * 64)
        self.run_checkout(bootstrap=gate.digest(Path(gate.__file__).read_bytes()))

    def test_existing_gate_cannot_authorize_candidate_even_with_bootstrap_pin(self):
        with self.assertRaises(gate.Denied):
            self.run_checkout(baseline=b"old trusted gate", bootstrap=gate.digest(Path(gate.__file__).read_bytes()))
        self.run_checkout(baseline=Path(gate.__file__).read_bytes())

    def test_dirty_checkout_cannot_reuse_head_evidence(self):
        with self.assertRaises(gate.Denied):
            self.run_checkout(baseline=Path(gate.__file__).read_bytes(), dirty=True)


if __name__ == "__main__":
    unittest.main()
