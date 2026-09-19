from __future__ import annotations

import json
import subprocess
import time
from types import SimpleNamespace
import unittest

from tools.github_project_api import GitHubAPIError, GitHubProjectAPI, parse_response


REPO = "aloerch/ambisgis-platform"


def response(body, status=200, headers=None, returncode=0):
    lines = [f"HTTP/2.0 {status} Test"]
    lines += [f"{name}: {value}" for name, value in (headers or {}).items()]
    return SimpleNamespace(stdout="\r\n".join(lines) + "\r\n\r\n" + json.dumps(body),
                           stderr="untrusted secret-bearing diagnostic", returncode=returncode)


def identity_response(scopes="read:project"):
    return response({"id": 10, "node_id": "U10", "login": "aloerch", "type": "User"},
                    headers={"X-OAuth-Scopes": scopes} if scopes is not None else {})


def connection(nodes, cursor=None):
    return {"nodes": nodes, "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}}


class QueueRunner:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class TransportTests(unittest.TestCase):
    def test_parser_accepts_arrays_and_final_proxy_status(self):
        stdout = "HTTP/1.1 200 Connection established\r\n\r\n" + response([{"id": 1}], headers={"ETag": '"abc"'}).stdout
        self.assertEqual(parse_response(stdout), (200, {"etag": '"abc"'}, [{"id": 1}]))

    def test_parser_rejects_missing_status_and_non_json_without_leaking(self):
        for text in ('{"secret":"never print"}', 'HTTP/2 502 Broken\n\nsecret <html>'):
            with self.subTest(text=text), self.assertRaises(GitHubAPIError) as caught:
                parse_response(text)
            self.assertNotIn("secret", str(caught.exception))

    def test_read_query_uses_json_stdin_and_fixed_host_without_shell(self):
        runner = QueueRunner(identity_response(), response({"data": {"user": {"projectsV2": connection([])}}}))
        api = GitHubProjectAPI(runner=runner)
        self.assertEqual(api.projects("aloerch"), [])
        args, kwargs = runner.calls[1]
        self.assertEqual(args[:4], ["gh", "api", "--hostname", "github.com"])
        self.assertEqual(args[args.index("--method") + 1], "POST")
        self.assertEqual(args[-2:], ["--input", "-"])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(json.loads(kwargs["input"])["variables"]["owner"], "aloerch")

    def test_identity_returns_only_safe_scope_names(self):
        runner = QueueRunner(identity_response("repo, read:project, repo"))
        identity = GitHubProjectAPI(runner=runner).identity()
        self.assertEqual(identity["_oauth_scopes"], ["read:project", "repo"])
        self.assertEqual(set(identity), {"id", "node_id", "login", "type", "_oauth_scopes"})

    def test_project_enumeration_refuses_public_only_scope_before_graphql(self):
        for scopes in ("repo, gist", "", "admin:org"):
            runner = QueueRunner(identity_response(scopes))
            with self.subTest(scopes=scopes), self.assertRaises(GitHubAPIError) as caught:
                GitHubProjectAPI(runner=runner).projects("aloerch")
            self.assertEqual(caught.exception.category, "permission")
            self.assertEqual(len(runner.calls), 1)
            self.assertEqual(runner.calls[0][0][9], "user")

    def test_project_enumeration_accepts_read_or_write_scope_without_extra_identity_read(self):
        for scopes in ("project", "repo, read:project"):
            runner = QueueRunner(identity_response(scopes), response({"data": {"user": {"projectsV2": connection([])}}}))
            api = GitHubProjectAPI(runner=runner)
            api.identity()
            with self.subTest(scopes=scopes):
                self.assertEqual(api.projects("aloerch"), [])
                self.assertEqual(len(runner.calls), 2)

    def test_absent_scope_header_is_unknown_not_empty_oauth_scope(self):
        runner = QueueRunner(identity_response(None))
        self.assertIsNone(GitHubProjectAPI(runner=runner).identity()["_oauth_scopes"])

    def test_unknown_authorization_cannot_be_treated_as_complete_enumeration(self):
        runner = QueueRunner(identity_response(None))
        with self.assertRaises(GitHubAPIError) as caught:
            GitHubProjectAPI(runner=runner).projects("aloerch")
        self.assertEqual(caught.exception.category, "permission")
        self.assertIn("cannot be verified", str(caught.exception))
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0][9], "user")

    def test_malformed_scope_header_never_echoes_raw_header(self):
        runner = QueueRunner(identity_response("Bearer credential-value"))
        with self.assertRaises(GitHubAPIError) as caught:
            GitHubProjectAPI(runner=runner).identity()
        self.assertNotIn("credential-value", str(caught.exception))

    def test_default_guard_blocks_all_mutation_families_without_request(self):
        runner = QueueRunner()
        api = GitHubProjectAPI(runner=runner)
        operations = [
            lambda: api.create_project("U1", "AmbisGIS — Product Development"),
            lambda: api.update_project("P1", True, "marker"),
            lambda: api.link_repository("P1", "R1"),
            lambda: api.create_field("P1", {"name": "Task ID", "type": "TEXT"}),
            lambda: api.create_issue(REPO, "title", "body", []),
            lambda: api.update_issue_body(REPO, 1, "body"),
            lambda: api.create_label(REPO, "ambisgis-managed"),
            lambda: api.add_item("P1", "I1"),
            lambda: api.set_field("P1", "ITEM1", {"id": "F1", "dataType": "TEXT"}, "FND-01"),
            lambda: api.add_dependency(REPO, 1, 45),
            lambda: api.create_view("P1", {"name": "Backlog", "layout": "TABLE"}),
            lambda: api.update_view_filter("V1", "is:issue"),
        ]
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaisesRegex(GitHubAPIError, "read-only"):
                operation()
        self.assertEqual(runner.calls, [])

    def test_graphql_classification_cannot_label_mutation_as_read(self):
        api = GitHubProjectAPI(runner=QueueRunner())
        with self.assertRaisesRegex(GitHubAPIError, "classification"):
            api._graphql("mutation Evil { anything }", mutation=False)

    def test_partial_graphql_data_is_never_used_or_retried(self):
        runner = QueueRunner(identity_response(), response({"data": {"user": {}}, "errors": [{"message": "SECRET", "type": "FORBIDDEN"}]}))
        with self.assertRaises(GitHubAPIError) as caught:
            GitHubProjectAPI(runner=runner).projects("aloerch")
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(len(runner.calls), 2)

    def test_graphql_errors_with_cli_failure_keep_category_and_hide_diagnostics(self):
        for kind, expected in (("UNPROCESSABLE", "graphql"), ("FORBIDDEN", "permission"), ("RATE_LIMITED", "rate_limit")):
            runner = QueueRunner(response({"data": {}, "errors": [{"message": "SECRET", "type": kind}]}, returncode=1))
            with self.subTest(kind=kind), self.assertRaises(GitHubAPIError) as caught:
                GitHubProjectAPI(runner=runner)._graphql("query Check { viewer { login } }")
            self.assertEqual(caught.exception.category, expected)
            self.assertNotIn("SECRET", str(caught.exception))
            self.assertEqual(len(runner.calls), 1)

    def test_explicit_permission_error_is_not_missing_or_retried(self):
        for status in (401, 403, 404):
            runner = QueueRunner(response({"message": "SECRET"}, status, returncode=1))
            with self.subTest(status=status), self.assertRaises(GitHubAPIError) as caught:
                GitHubProjectAPI(runner=runner).repository(REPO)
            self.assertEqual(caught.exception.status, status)
            self.assertNotIn("SECRET", str(caught.exception))
            self.assertEqual(len(runner.calls), 1)

    def test_read_retries_are_bounded_and_honor_short_retry_after(self):
        runner = QueueRunner(response({}, 429, {"Retry-After": "2"}, 1),
                             response({}, 503, returncode=1), response({"login": "aloerch"}))
        sleeps = []
        api = GitHubProjectAPI(runner=runner, sleep=sleeps.append)
        self.assertEqual(api.identity()["login"], "aloerch")
        self.assertEqual(sleeps, [2, 2])
        self.assertEqual(len(runner.calls), 3)

    def test_long_rate_limit_is_reported_without_shortening_wait(self):
        runner = QueueRunner(response({}, 429, {"Retry-After": "120"}, 1))
        sleeps = []
        with self.assertRaises(GitHubAPIError) as caught:
            GitHubProjectAPI(runner=runner, sleep=sleeps.append).identity()
        self.assertEqual(caught.exception.category, "rate_limit")
        self.assertEqual(caught.exception.retry_after, 120)
        self.assertEqual(sleeps, [])

    def test_primary_rate_limit_waits_until_reset_instead_of_retrying_early(self):
        runner = QueueRunner(response({}, 403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(time.time()) + 600)}, 1))
        sleeps = []
        with self.assertRaises(GitHubAPIError) as caught:
            GitHubProjectAPI(runner=runner, sleep=sleeps.append).identity()
        self.assertEqual(caught.exception.category, "rate_limit")
        self.assertGreater(caught.exception.retry_after, 590)
        self.assertEqual(sleeps, [])

    def test_timeout_read_retries_but_uncertain_mutation_never_retries(self):
        timeout = subprocess.TimeoutExpired("gh", 45, output="SECRET", stderr="SECRET")
        reader = QueueRunner(timeout, response({"login": "aloerch"}))
        self.assertEqual(GitHubProjectAPI(runner=reader, sleep=lambda _: None).identity()["login"], "aloerch")
        writer = QueueRunner(timeout)
        with self.assertRaises(GitHubAPIError) as caught:
            GitHubProjectAPI(read_only=False, runner=writer).create_issue(REPO, "x", "y", [])
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(len(writer.calls), 1)

    def test_mutation_http_failure_does_not_retry(self):
        runner = QueueRunner(response({}, 503, returncode=1))
        with self.assertRaises(GitHubAPIError):
            GitHubProjectAPI(read_only=False, runner=runner).create_label(REPO, "ambisgis-managed")
        self.assertEqual(len(runner.calls), 1)

    def test_unrelated_repository_and_owner_rejected_before_request(self):
        runner = QueueRunner()
        api = GitHubProjectAPI(read_only=False, runner=runner)
        for full in ("aloerch/weaveatlas", "aloerch/osgs-neu", "other/ambisgis-platform", REPO + "/../weaveatlas"):
            with self.subTest(full=full), self.assertRaises(GitHubAPIError):
                api.create_issue(full, "x", "y", [])
        with self.assertRaises(GitHubAPIError):
            api.projects("another-owner")
        self.assertEqual(runner.calls, [])


class PaginationTests(unittest.TestCase):
    def test_projects_paginate_and_include_closed(self):
        runner = QueueRunner(identity_response(),
            response({"data": {"user": {"projectsV2": connection([{"id": "P1", "closed": False}], "next")}}}),
            response({"data": {"user": {"projectsV2": connection([{"id": "P2", "closed": True}])}}}))
        projects = GitHubProjectAPI(runner=runner).projects("aloerch")
        self.assertEqual([p["id"] for p in projects], ["P1", "P2"])
        self.assertIsNone(json.loads(runner.calls[1][1]["input"])["variables"]["after"])
        self.assertEqual(json.loads(runner.calls[2][1]["input"])["variables"]["after"], "next")
        self.assertNotIn("is:open", json.loads(runner.calls[1][1]["input"])["query"])

    def test_graphql_repeated_missing_cursor_and_duplicate_nodes_fail(self):
        for first, second in [
            (connection([{"id": "P1"}], "next"), connection([{"id": "P2"}], "next")),
            ({"nodes": [{"id": "P1"}], "pageInfo": {"hasNextPage": True, "endCursor": None}}, None),
            (connection([{"id": "P1"}], "next"), connection([{"id": "P1"}])),
        ]:
            results = [response({"data": {"user": {"projectsV2": value}}}) for value in (first, second) if value is not None]
            with self.subTest(first=first), self.assertRaises(GitHubAPIError):
                GitHubProjectAPI(runner=QueueRunner(identity_response(), *results)).projects("aloerch")

    def test_failure_on_later_page_does_not_return_partial_collection(self):
        runner = QueueRunner(identity_response(), response({"data": {"user": {"projectsV2": connection([{"id": "P1"}], "next")}}}),
                             response({"data": {"user": None}, "errors": [{"message": "denied"}]}))
        with self.assertRaises(GitHubAPIError):
            GitHubProjectAPI(runner=runner).projects("aloerch")

    def test_rest_issues_follow_link_and_exclude_pull_requests(self):
        link = f'<https://api.github.com/repos/{REPO}/issues?state=all&sort=created&direction=asc&per_page=100&page=2>; rel="next"'
        runner = QueueRunner(response([{"id": 1}, {"id": 2, "pull_request": {}}], headers={"Link": link}),
                             response([{"id": 3, "state": "closed"}]))
        self.assertEqual([i["id"] for i in GitHubProjectAPI(runner=runner).issues(REPO)], [1, 3])
        self.assertIn("state=all", runner.calls[1][0][9])

    def test_rest_links_cannot_redirect_host_repo_or_filters(self):
        paths = ["https://evil.test/repos/" + REPO + "/labels?per_page=100&page=2",
                 "https://api.github.com/repos/aloerch/weaveatlas/labels?per_page=100&page=2",
                 "https://api.github.com/repos/" + REPO + "/labels?per_page=100&page=2&state=open"]
        for path in paths:
            runner = QueueRunner(response([{"id": 1}], headers={"Link": f'<{path}>; rel="next"'}))
            with self.subTest(path=path), self.assertRaises(GitHubAPIError):
                GitHubProjectAPI(runner=runner).labels(REPO)
            self.assertEqual(len(runner.calls), 1)

    def test_rest_labels_and_dependencies_paginate(self):
        for suffix, method in (("labels", lambda api: api.labels(REPO)),
                               ("issues/4/dependencies/blocked_by", lambda api: api.dependencies(REPO, 4))):
            link = f'<https://api.github.com/repos/{REPO}/{suffix}?per_page=100&page=2>; rel="next"'
            runner = QueueRunner(response([{"id": 1}], headers={"Link": link}), response([{"id": 2}]))
            with self.subTest(suffix=suffix):
                self.assertEqual(len(method(GitHubProjectAPI(runner=runner))), 2)

    def test_project_fully_paginates_all_nested_collections_and_values(self):
        calls = []
        def runner(args, **kwargs):
            payload = json.loads(kwargs["input"])
            query, variables = payload["query"], payload["variables"]
            calls.append((query, variables))
            if query.startswith("query Project("):
                return response({"data": {"node": {"id": "P1", "title": "Project"}}})
            second = variables["after"] is not None
            index = 2 if second else 1
            cursor = None if second else "next"
            if query.startswith("query ItemValues"):
                name = "Priority" if second else "Delivery"
                value = {"__typename": "ProjectV2ItemFieldSingleSelectValue", "name": "High" if second else "In review",
                         "optionId": "O" + str(index), "field": {"id": "F" + str(index), "name": name}}
                return response({"data": {"node": {"fieldValues": connection([value], cursor)}}})
            for field in ("fields", "repositories", "items", "views"):
                if field + "(first:" in query:
                    entry = {"id": field + str(index)}
                    if field == "items":
                        self.assertIn("archivedStates:[ARCHIVED,NOT_ARCHIVED]", query)
                        entry.update({"isArchived": second, "content": {"id": "I" + str(index)}})
                        entry["fieldValues"] = connection([{
                            "__typename": "ProjectV2ItemFieldSingleSelectValue", "name": "In review",
                            "optionId": "O1", "field": {"id": "F1", "name": "Delivery"}}], "next")
                    if field == "fields":
                        entry.update({"name": "Field" + str(index), "dataType": "TEXT"})
                    return response({"data": {"node": {field: connection([entry], cursor)}}})
            self.fail("Unrecognized query")
        project = GitHubProjectAPI(runner=runner).project("P1")
        self.assertEqual(len(calls), 11)
        for field in ("fields", "repositories", "items", "views"):
            self.assertEqual(len(project[field]), 2)
        self.assertTrue(project["items"][1]["isArchived"])
        self.assertEqual(project["items"][0]["values"], {"Delivery": "In review", "Priority": "High"})

    def test_single_item_embeds_first_values_page_without_extra_request(self):
        value = {"__typename": "ProjectV2ItemFieldTextValue", "text": "FND-01", "field": {"id": "F1", "name": "Task ID"}}
        runner = QueueRunner(response({"data": {"node": {"id": "ITEM1", "isArchived": False, "fieldValues": connection([value])}}}))
        item = GitHubProjectAPI(runner=runner).item("ITEM1")
        self.assertEqual(item["values"], {"Task ID": "FND-01"})
        self.assertEqual(item["field_values"], [value])
        self.assertEqual(len(runner.calls), 1)

    def test_items_include_many_embedded_values_without_request_per_item(self):
        items = [{"id": f"ITEM{i}", "isArchived": False, "fieldValues": connection([])} for i in range(66)]
        runner = QueueRunner(response({"data": {"node": {"items": connection(items)}}}))
        result = GitHubProjectAPI(runner=runner).items("P1")
        self.assertEqual(len(result), 66)
        self.assertEqual(len(runner.calls), 1)

    def test_null_project_is_error_not_a_missing_project_creation_signal(self):
        runner = QueueRunner(response({"data": {"node": None}}))
        with self.assertRaises(GitHubAPIError):
            GitHubProjectAPI(runner=runner).project("P1")


class MutationAndCapabilityTests(unittest.TestCase):
    def test_dependency_uses_database_id_and_correct_endpoint(self):
        runner = QueueRunner(response({"id": 991}, 201))
        result = GitHubProjectAPI(read_only=False, runner=runner).add_dependency(REPO, 7, 991)
        self.assertEqual(result["id"], 991)
        args, kwargs = runner.calls[0]
        self.assertIn(f"repos/{REPO}/issues/7/dependencies/blocked_by", args)
        self.assertEqual(json.loads(kwargs["input"]), {"issue_id": 991})

    def test_issue_body_only_patch_preserves_other_issue_properties(self):
        runner = QueueRunner(response({"id": 1, "body": "new"}))
        GitHubProjectAPI(read_only=False, runner=runner).update_issue_body(REPO, 7, "new\n$literal", '"revision"')
        args, kwargs = runner.calls[0]
        self.assertEqual(args[args.index("--method") + 1], "PATCH")
        self.assertIn('If-Match: "revision"', args)
        self.assertEqual(json.loads(kwargs["input"]), {"body": "new\n$literal"})

    def test_issue_read_includes_etag_and_rejects_pull_request(self):
        runner = QueueRunner(response({"id": 1}, headers={"ETag": '"hash"'}), response({"id": 2, "pull_request": {}}))
        api = GitHubProjectAPI(runner=runner)
        self.assertEqual(api.issue(REPO, 1)["_etag"], '"hash"')
        with self.assertRaises(GitHubAPIError):
            api.issue(REPO, 2)

    def test_custom_field_creation_supplies_documented_option_inputs(self):
        runner = QueueRunner(response({"data": {"createProjectV2Field": {"projectV2Field": {"id": "F1", "name": "Delivery", "dataType": "SINGLE_SELECT", "options": [{"id": "O1", "name": "Backlog"}]}}}}))
        result = GitHubProjectAPI(read_only=False, runner=runner).create_field("P1", {"name": "Delivery", "type": "SINGLE_SELECT", "options": ["Backlog"]})
        self.assertEqual(result["options"][0]["id"], "O1")
        payload = json.loads(runner.calls[0][1]["input"])["variables"]["input"]
        self.assertEqual(payload["singleSelectOptions"], [{"name": "Backlog", "description": "", "color": "GRAY"}])

    def test_set_select_uses_recorded_option_id_and_rejects_unknown_values(self):
        runner = QueueRunner(response({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITEM1"}}}}))
        field = {"id": "F1", "dataType": "SINGLE_SELECT", "options": [{"id": "O1", "name": "Backlog"}]}
        api = GitHubProjectAPI(read_only=False, runner=runner)
        api.set_field("P1", "ITEM1", field, "Backlog")
        payload = json.loads(runner.calls[0][1]["input"])["variables"]["input"]
        self.assertEqual(payload["value"], {"singleSelectOptionId": "O1"})
        with self.assertRaises(GitHubAPIError):
            api.set_field("P1", "ITEM1", field, "Unknown")
        self.assertEqual(len(runner.calls), 1)

    def test_view_creation_does_not_invent_grouping_or_sort_inputs(self):
        runner = QueueRunner(response({"data": {"createProjectV2View": {"projectV2View": {"id": "V1", "layout": "BOARD_LAYOUT"}}}}))
        GitHubProjectAPI(read_only=False, runner=runner).create_view("P1", {"name": "Execution board", "layout": "BOARD", "group_by": "Delivery"})
        payload = json.loads(runner.calls[0][1]["input"])["variables"]["input"]
        self.assertEqual(payload, {"projectId": "P1", "name": "Execution board", "layout": "BOARD_LAYOUT"})

    def test_roadmap_omits_unsupported_visible_fields_but_table_and_board_keep_them(self):
        for layout in ("ROADMAP", "TABLE", "BOARD"):
            runner = QueueRunner(response({"data": {"createProjectV2View": {"projectV2View": {"id": "V1", "layout": layout + "_LAYOUT"}}}}))
            GitHubProjectAPI(read_only=False, runner=runner).create_view("P1", {"name": "View", "layout": layout, "visibleFieldIds": ["F1", "F2"]})
            payload = json.loads(runner.calls[0][1]["input"])["variables"]["input"]
            with self.subTest(layout=layout):
                if layout == "ROADMAP":
                    self.assertNotIn("configuration", payload)
                else:
                    self.assertEqual(payload["configuration"], {"visibleFieldIds": ["F1", "F2"]})

    def test_capabilities_are_live_introspection_without_mutation(self):
        body = {"mutations": {"fields": [{"name": "createProjectV2"}, {"name": "createProjectV2View"}]},
                "field_types": {"enumValues": [{"name": "TEXT"}, {"name": "SINGLE_SELECT"}]},
                "project_type": {"fields": [{"name": "items", "args": [{"name": "archivedStates"}]}]},
                "view_configuration": {"inputFields": [{"name": "visibleFieldIds"}]},
                "view_layouts": {"enumValues": [{"name": "TABLE_LAYOUT"}]}}
        runner = QueueRunner(response({"data": body}))
        result = GitHubProjectAPI(runner=runner).capabilities()
        self.assertTrue(result["create_view"])
        self.assertFalse(result["update_view"])
        self.assertTrue(result["project_items_archived_states"])
        self.assertEqual(result["view_configuration_fields"], ["visibleFieldIds"])
        self.assertTrue(json.loads(runner.calls[0][1]["input"])["query"].startswith("query "))


if __name__ == "__main__":
    unittest.main()
