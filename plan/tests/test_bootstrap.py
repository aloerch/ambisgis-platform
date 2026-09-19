from __future__ import annotations
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.bootstrap_repositories import (
    ApiError, BootstrapError, GitHubCLI, execute, parse_http_output,
    validate_manifest, verify_target,
)
ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / 'repositories.json').read_text())


def repository(full: str, repo_id: int = 100, *, parent: str | None = None):
    result = {'full_name': full, 'id': repo_id, 'private': False,
              'fork': parent is not None, 'archived': False, 'disabled': False,
              'default_branch': 'main'}
    if parent:
        result['parent'] = {'full_name': parent}
    return result


class FakeClient:
    def __init__(self):
        self.calls = []
        self.login = 'aloerch'
        self.repos = {s['upstream']: repository(s['upstream'], i + 1)
                      for i, s in enumerate(MANIFEST['repositories']) if s['upstream']}
        self.branch_ready = True
        self.block = None
        self.next_id = 1000

    def request(self, method, endpoint, payload=None, *, missing_ok=False):
        self.calls.append((method, endpoint, copy.deepcopy(payload)))
        if endpoint == self.block:
            raise ApiError('Explicit permission failure', 403)
        if method == 'GET' and endpoint == 'user':
            return {'login': self.login, 'type': 'User'}
        if method == 'GET' and '/branches/' in endpoint:
            return {'commit': {'sha': 'a' * 40}} if self.branch_ready else None
        if method == 'GET' and endpoint.startswith('repos/'):
            value = self.repos.get(endpoint[len('repos/'):])
            if value is None and not missing_ok:
                raise ApiError('Not found', 404)
            return copy.deepcopy(value)
        if method == 'POST':
            parent = endpoint[len('repos/'):-len('/forks')] if endpoint.endswith('/forks') else None
            full = f"aloerch/{payload['name']}"
            if full in self.repos:
                raise ApiError('Already exists', 422)
            self.next_id += 1
            self.repos[full] = repository(full, self.next_id, parent=parent)
            return copy.deepcopy(self.repos[full])
        raise AssertionError((method, endpoint))


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.receipt = Path(self.tmp.name) / 'receipt.json'
        self.client = FakeClient()

    def run_tool(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return execute(self.client, MANIFEST, 'aloerch', self.receipt,
                           sleep=lambda _: None, **kwargs)

    def test_dry_run_has_only_get_and_no_local_receipt(self):
        plan = self.run_tool()
        self.assertEqual(len(plan), 15)
        self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))
        self.assertFalse(self.receipt.exists())

    def test_apply_creates_exact_fifteen_public_targets(self):
        self.run_tool(apply=True)
        posts = [c for c in self.client.calls if c[0] == 'POST']
        self.assertEqual(len(posts), 15)
        self.assertEqual({c[2]['name'] for c in posts}, {s['name'] for s in MANIFEST['repositories']})
        self.assertTrue(all(not r['private'] for k, r in self.client.repos.items() if k.startswith('aloerch/')))
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(len(receipt['managed_repositories']), 15)
        self.assertTrue(all(x['status'] == 'ready' for x in receipt['managed_repositories'].values()))

    def test_repeated_apply_does_not_mutate_existing(self):
        self.run_tool(apply=True)
        self.client.calls.clear()
        self.run_tool(apply=True)
        self.assertFalse(any(m == 'POST' for m, _, _ in self.client.calls))

    def test_wrong_identity_never_posts(self):
        self.client.login = 'another-account'
        with self.assertRaises(BootstrapError): self.run_tool(apply=True)
        self.assertFalse(any(m == 'POST' for m, _, _ in self.client.calls))

    def test_unmanaged_new_repository_collision(self):
        self.client.repos['aloerch/ambisgis-platform'] = repository('aloerch/ambisgis-platform')
        with self.assertRaisesRegex(BootstrapError, 'Collision'): self.run_tool(apply=True)
        self.assertFalse(any(m == 'POST' for m, _, _ in self.client.calls))

    def test_matching_existing_fork_is_left_unchanged(self):
        self.client.repos['aloerch/ambisgis-geoserver'] = repository('aloerch/ambisgis-geoserver', parent='geoserver/geoserver')
        plan = self.run_tool()
        self.assertEqual(dict((s['name'], a) for s, a in plan)['ambisgis-geoserver'], 'leave_unchanged')

    def test_wrong_fork_parent_fails_full_preflight_before_any_create(self):
        self.client.repos['aloerch/ambisgis-mapstore'] = repository('aloerch/ambisgis-mapstore', parent='other/repo')
        with self.assertRaises(BootstrapError): self.run_tool(apply=True)
        self.assertFalse(any(m == 'POST' for m, _, _ in self.client.calls))

    def test_private_target_rejected(self):
        r = repository('aloerch/ambisgis-platform'); r['private'] = True
        self.client.repos['aloerch/ambisgis-platform'] = r
        with self.assertRaises(BootstrapError): self.run_tool()

    def test_manifest_rejects_unrelated_existing_repo_name(self):
        m = copy.deepcopy(MANIFEST); m['repositories'][0]['name'] = 'weaveatlas'
        with self.assertRaises(BootstrapError): validate_manifest(m, 'aloerch')

    def test_manifest_rejects_changed_upstream(self):
        m = copy.deepcopy(MANIFEST); m['repositories'][-1]['upstream'] = 'other/project'
        with self.assertRaises(BootstrapError): validate_manifest(m, 'aloerch')

    def test_explicit_403_is_not_treated_as_missing(self):
        self.client.block = 'repos/aloerch/ambisgis-platform'
        with self.assertRaises(ApiError): self.run_tool(apply=True)
        self.assertFalse(any(m == 'POST' for m, _, _ in self.client.calls))

    def test_readiness_failure_keeps_partial_receipt(self):
        self.client.branch_ready = False
        with self.assertRaisesRegex(BootstrapError, 'readiness'): self.run_tool(apply=True, attempts=1)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt['managed_repositories']['aloerch/ambisgis-platform']['status'], 'created_pending_readiness')

    def test_pending_readiness_is_rechecked_on_rerun(self):
        self.client.branch_ready = False
        with self.assertRaises(BootstrapError): self.run_tool(apply=True, attempts=1)
        self.client.branch_ready = True
        self.client.calls.clear()
        self.run_tool(apply=True)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt['managed_repositories']['aloerch/ambisgis-platform']['status'], 'ready')
        self.assertEqual(len([c for c in self.client.calls if c[0] == 'POST']), 14)

    def test_receipt_id_mismatch_blocks_adoption(self):
        self.run_tool(apply=True)
        self.client.repos['aloerch/ambisgis-platform']['id'] += 10
        self.client.calls.clear()
        with self.assertRaisesRegex(BootstrapError, 'Collision'): self.run_tool(apply=True)
        self.assertFalse(any(m == 'POST' for m, _, _ in self.client.calls))

    def test_receipt_symlink_rejected(self):
        destination = Path(self.tmp.name) / 'outside.json'; destination.write_text('{}')
        self.receipt.symlink_to(destination)
        with self.assertRaises(BootstrapError): self.run_tool(apply=True)
        self.assertEqual(destination.read_text(), '{}')

    def test_case_insensitive_parent_comparison(self):
        spec = MANIFEST['repositories'][-1]
        verify_target(repository('aloerch/ambisgis-mapstore', parent='GEOSOLUTIONS-IT/MAPSTORE2'), 'aloerch', spec)


class HttpTests(unittest.TestCase):
    def test_success_and_crlf(self):
        status, body = parse_http_output('HTTP/2.0 200 OK\r\ncontent-type: application/json\r\n\r\n{"id": 1}\n')
        self.assertEqual((status, body), (200, {'id': 1}))

    def test_final_status_after_proxy_header(self):
        text = 'HTTP/1.1 200 Connection established\n\nHTTP/2.0 404 Not Found\ncontent-type: application/json\n\n{"message":"Not Found"}'
        self.assertEqual(parse_http_output(text)[0], 404)

    def test_missing_status_is_not_an_inferred_404(self):
        with self.assertRaises(ApiError): parse_http_output('{"message":"Not Found"}')

    def test_non_json_response_fails(self):
        with self.assertRaises(ApiError): parse_http_output('HTTP/2.0 502 Bad Gateway\n\n<html>bad</html>')

    def test_404_allowed_only_when_explicit(self):
        def runner(*args, **kwargs):
            return SimpleNamespace(stdout='HTTP/2.0 404 Not Found\n\n{"message":"Not Found"}', stderr='', returncode=1)
        client = GitHubCLI(runner)
        self.assertIsNone(client.request('GET', 'repos/owner/name', missing_ok=True))
        with self.assertRaises(ApiError): client.request('GET', 'user')

    def test_401_never_missing(self):
        def runner(*args, **kwargs):
            return SimpleNamespace(stdout='HTTP/2.0 401 Unauthorized\n\n{"message":"Bad credentials"}', stderr='', returncode=1)
        with self.assertRaises(ApiError): GitHubCLI(runner).request('GET', 'repos/a/b', missing_ok=True)

    def test_cli_arguments_never_use_shell(self):
        calls=[]
        def runner(args, **kwargs):
            calls.append((args,kwargs))
            return SimpleNamespace(stdout='HTTP/2.0 201 Created\n\n{"id":1}', stderr='', returncode=0)
        GitHubCLI(runner).request('POST','user/repos',{'name':'ambisgis-platform'})
        self.assertIsInstance(calls[0][0], list)
        self.assertNotIn('shell', calls[0][1])
        self.assertEqual(json.loads(calls[0][1]['input'])['name'], 'ambisgis-platform')


if __name__ == '__main__': unittest.main()
