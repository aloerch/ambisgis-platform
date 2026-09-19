"""Narrow, fail-closed GitHub transport for the GOV-01 Project importer.

All credentials remain with the locally authorized ``gh`` process. Queries use
HTTP POST but never mutations unless ``read_only=False``. This adapter performs
bounded retries for reads only; callers reconcile uncertain mutation outcomes.
It does not adopt resources, grant scopes, write receipts or configure workflows.
Personal Project enumeration currently requires verified OAuth scope headers;
other authentication types are unsupported until alternate proof is implemented.

API references inspected 2026-09-19:
https://docs.github.com/en/graphql/reference/projects
https://docs.github.com/en/rest/issues/issue-dependencies
https://docs.github.com/en/rest/issues/issues
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
import json
import math
import re
import subprocess
import time
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

try:
    from .bootstrap_repositories import EXPECTED
except ImportError:  # Direct execution of the importing tool from tools/.
    from bootstrap_repositories import EXPECTED


class GitHubAPIError(RuntimeError):
    """Sanitized transport/capability failure; never contains raw API output."""

    def __init__(self, message: str, status: int | None = None, *,
                 category: str = "api", retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.category = category
        self.retry_after = retry_after


PROJECT_FIELDS = """id number url title public closed shortDescription readme
    owner { id __typename ... on User { login } ... on Organization { login } }
    viewerCanUpdate"""
FIELD_FIELDS = """__typename
    ... on ProjectV2FieldCommon { id name dataType }
    ... on ProjectV2SingleSelectField { options { id name color description } }"""
VALUE_FIELDS = """__typename
    ... on ProjectV2ItemFieldTextValue {
      text field { ... on ProjectV2FieldCommon { id name } } }
    ... on ProjectV2ItemFieldSingleSelectValue {
      name optionId field { ... on ProjectV2FieldCommon { id name } } }
    ... on ProjectV2ItemFieldDateValue {
      date field { ... on ProjectV2FieldCommon { id name } } }
    ... on ProjectV2ItemFieldNumberValue {
      number field { ... on ProjectV2FieldCommon { id name } } }
    ... on ProjectV2ItemFieldIterationValue {
      iterationId field { ... on ProjectV2FieldCommon { id name } } }"""
PAGE_INFO = "pageInfo { hasNextPage endCursor }"
VIEW_FIELDS = "id name layout filter"
MUTATIONS = {
    "createProjectV2", "updateProjectV2", "linkProjectV2ToRepository",
    "createProjectV2Field", "addProjectV2ItemById", "updateProjectV2ItemFieldValue",
    "createProjectV2View", "updateProjectV2View",
}


def parse_response(stdout: str) -> tuple[int, dict[str, str], Any]:
    """Parse the final HTTP header block; JSON may be an object or a list."""
    normalized = stdout.replace("\r\n", "\n")
    matches = list(re.finditer(r"(?m)^HTTP/[0-9.]+\s+(\d{3})[^\n]*\n", normalized))
    if not matches:
        raise GitHubAPIError("GitHub CLI returned no verifiable HTTP status.", category="transport")
    last = matches[-1]
    status = int(last.group(1))
    boundary = normalized.find("\n\n", last.start())
    if boundary < 0:
        raise GitHubAPIError("GitHub returned incomplete HTTP headers.", status, category="transport")
    headers: dict[str, str] = {}
    for line in normalized[last.end():boundary].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    body = normalized[boundary + 2:].strip()
    if not body:
        return status, headers, None
    try:
        return status, headers, json.loads(body)
    except json.JSONDecodeError:
        raise GitHubAPIError("GitHub returned non-JSON content.", status, category="transport") from None


class GitHubProjectAPI:
    def __init__(self, *, read_only: bool = True,
                 runner: Callable[..., Any] = subprocess.run,
                 sleep: Callable[[float], None] = time.sleep,
                 read_attempts: int = 3, max_pages: int = 1000):
        if not 1 <= read_attempts <= 5 or not 1 <= max_pages <= 10000:
            raise ValueError("Invalid bounded retry/pagination limits.")
        self.read_only = read_only
        self.runner = runner
        self.sleep = sleep
        self.read_attempts = read_attempts
        self.max_pages = max_pages
        self._identity_checked = False
        self._oauth_scopes: list[str] | None = None

    @staticmethod
    def _repo(full: str) -> str:
        if not isinstance(full, str) or full not in {f"aloerch/{name}" for name in EXPECTED}:
            raise GitHubAPIError("Repository is outside the approved allow-list.", category="boundary")
        return f"repos/{full}"

    @staticmethod
    def _number(number: int) -> int:
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise GitHubAPIError("Expected a positive GitHub issue number or database ID.", category="schema")
        return number

    def _request(self, method: str, endpoint: str, payload: dict | None = None, *,
                 mutation: bool = False, headers: dict[str, str] | None = None) -> tuple[Any, dict[str, str]]:
        if mutation and self.read_only:
            raise GitHubAPIError("Mutation refused: adapter is read-only.", category="read_only")
        if method not in {"GET", "POST", "PATCH"} or (method != "GET" and endpoint != "graphql" and not mutation):
            raise GitHubAPIError("Unclassified or unsupported HTTP operation.", category="boundary")
        attempts = 1 if mutation else self.read_attempts
        for attempt in range(attempts):
            args = ["gh", "api", "--hostname", "github.com", "--include", "--method", method,
                    "-H", "Accept: application/vnd.github+json", endpoint]
            for name, value in (headers or {}).items():
                if name != "If-Match" or not isinstance(value, str) or "\n" in value or "\r" in value:
                    raise GitHubAPIError("Invalid conditional request header.", category="boundary")
                args += ["-H", f"{name}: {value}"]
            data = None
            if payload is not None:
                args += ["--input", "-"]
                data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            try:
                result = self.runner(args, input=data, text=True, capture_output=True,
                                     timeout=45, check=False)
            except subprocess.TimeoutExpired:
                error = GitHubAPIError("GitHub request timed out; mutation outcome may require inspection.",
                                       category="transport")
                if not mutation and attempt + 1 < attempts:
                    self.sleep(2 ** attempt)
                    continue
                raise error from None
            except OSError:
                raise GitHubAPIError("GitHub CLI could not run; inspect the local installation.",
                                     category="transport") from None
            try:
                status, response_headers, body = parse_response(result.stdout)
            except GitHubAPIError as error:
                if not mutation and error.status in {502, 503, 504} and attempt + 1 < attempts:
                    self.sleep(2 ** attempt)
                    continue
                raise
            retry_after = self._retry_delay(response_headers, attempt)
            limited = status == 429 or (status == 403 and (
                "retry-after" in response_headers or response_headers.get("x-ratelimit-remaining") == "0"))
            # gh exits nonzero for GraphQL application errors even on HTTP 200.
            # Classify those before the CLI exit status; never expose raw errors.
            if endpoint == "graphql" and 200 <= status < 300 and isinstance(body, dict) and body.get("errors"):
                types = {e.get("type") for e in body["errors"] if isinstance(e, dict)} if isinstance(body["errors"], list) else set()
                category = ("rate_limit" if "RATE_LIMITED" in types else
                            "permission" if types & {"FORBIDDEN", "UNAUTHORIZED", "INSUFFICIENT_SCOPES"} else "graphql")
                raise GitHubAPIError("GraphQL returned errors; partial data is not usable.", status,
                                     category=category)
            if not 200 <= status < 300 or result.returncode != 0:
                category = "rate_limit" if limited else ("permission" if status in {401, 403} else "http")
                retryable = limited or status in {502, 503, 504}
                # Do not shorten a server-mandated wait; leave long waits to a later run.
                if not mutation and retryable and attempt + 1 < attempts and retry_after <= 30:
                    self.sleep(retry_after)
                    continue
                raise GitHubAPIError(f"GitHub request failed (HTTP {status}); no scope escalation attempted.",
                                     status, category=category, retry_after=retry_after if limited else None)
            if endpoint == "graphql":
                if not isinstance(body, dict):
                    raise GitHubAPIError("Invalid GraphQL response.", status, category="schema")
                if not isinstance(body.get("data"), dict):
                    raise GitHubAPIError("GraphQL returned no complete data object.", status, category="schema")
                body = body["data"]
            return body, response_headers
        raise AssertionError("Retry loop exhausted unexpectedly")

    @staticmethod
    def _retry_delay(headers: dict[str, str], attempt: int) -> float:
        retry_after = headers.get("retry-after")
        try:
            if retry_after is not None:
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
            elif headers.get("x-ratelimit-remaining") == "0":
                # A primary rate limit must wait until its stated reset time.
                if "x-ratelimit-reset" not in headers:
                    return 60.0
                delay = float(headers["x-ratelimit-reset"]) - time.time()
            else:
                delay = float(2 ** attempt)
        except (TypeError, ValueError, OverflowError):
            return 60.0  # Unknown server guidance: stop, rather than retry early.
        return max(0.0, delay) if math.isfinite(delay) else 60.0

    def _graphql(self, query: str, variables: dict | None = None, *, mutation: bool = False) -> dict:
        operation = query.lstrip().split(None, 1)[0]
        if operation != ("mutation" if mutation else "query"):
            raise GitHubAPIError("GraphQL operation does not match its read/write classification.", category="boundary")
        return self._request("POST", "graphql", {"query": query, "variables": variables or {}}, mutation=mutation)[0]

    @staticmethod
    def _object(value: Any) -> dict:
        if not isinstance(value, dict):
            raise GitHubAPIError("Expected a complete GitHub object; missing is not presumed absent.", category="schema")
        return value

    def _connection(self, query: str, variables: dict, path: tuple[str, ...], *,
                    initial: dict | None = None) -> list[dict]:
        result: list[dict] = []
        seen_cursors: set[str] = set()
        seen_ids: set[str] = set()
        cursor = None
        for page_index in range(self.max_pages):
            if page_index == 0 and initial is not None:
                value: Any = initial
            else:
                value = self._graphql(query, {**variables, "after": cursor})
                for part in path:
                    value = self._object(value).get(part)
            connection = self._object(value)
            nodes = connection.get("nodes")
            page = self._object(connection.get("pageInfo"))
            if not isinstance(nodes, list) or type(page.get("hasNextPage")) is not bool:
                raise GitHubAPIError("Incomplete GraphQL pagination response.", category="pagination")
            for node in nodes:
                node = self._object(node)
                node_id = node.get("id")
                if node_id is not None:
                    if node_id in seen_ids:
                        raise GitHubAPIError("GraphQL pagination repeated a node; rerun a fresh preflight.", category="pagination")
                    seen_ids.add(node_id)
                result.append(node)
            if not page["hasNextPage"]:
                return result
            cursor = page.get("endCursor")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors or not nodes:
                raise GitHubAPIError("GraphQL pagination did not advance safely.", category="pagination")
            seen_cursors.add(cursor)
        raise GitHubAPIError("GraphQL pagination exceeded the configured bound.", category="pagination")

    def _rest_list(self, endpoint: str) -> list[dict]:
        original = endpoint
        separator = "&" if "?" in endpoint else "?"
        endpoint += separator + "per_page=100&page=1"
        visited: set[str] = set()
        ids: set[Any] = set()
        output: list[dict] = []
        for _ in range(self.max_pages):
            if endpoint in visited:
                raise GitHubAPIError("REST pagination repeated a page.", category="pagination")
            visited.add(endpoint)
            body, headers = self._request("GET", endpoint)
            if not isinstance(body, list):
                raise GitHubAPIError("Expected a REST collection.", category="schema")
            for entry in body:
                entry = self._object(entry)
                if "id" in entry:
                    if entry["id"] in ids:
                        raise GitHubAPIError("REST pagination repeated a resource; rerun preflight.", category="pagination")
                    ids.add(entry["id"])
                output.append(entry)
            links = headers.get("link", "")
            next_links = re.findall(r'<([^>]+)>;\s*rel="next"', links)
            if not next_links:
                if 'rel="next"' in links:
                    raise GitHubAPIError("Malformed REST pagination link.", category="pagination")
                return output
            if len(next_links) != 1 or not body:
                raise GitHubAPIError("Ambiguous or nonadvancing REST pagination.", category="pagination")
            parsed = urlsplit(next_links[0])
            base = urlsplit(original)
            query = parse_qs(parsed.query)
            if (parsed.scheme != "https" or parsed.netloc != "api.github.com" or parsed.fragment
                    or parsed.path != "/" + base.path or query.get("per_page") != ["100"]
                    or len(query.get("page", [])) != 1 or not query["page"][0].isdigit()):
                raise GitHubAPIError("REST pagination link changed the approved endpoint.", category="boundary")
            # Original filters must remain unchanged; only the page may advance.
            expected_query = parse_qs(base.query)
            if {k: v for k, v in query.items() if k not in {"page", "per_page"}} != expected_query:
                raise GitHubAPIError("REST pagination changed its filters.", category="pagination")
            endpoint = parsed.path.lstrip("/") + "?" + parsed.query
        raise GitHubAPIError("REST pagination exceeded the configured bound.", category="pagination")

    def identity(self) -> dict:
        body, headers = self._request("GET", "user")
        user = self._object(body)
        # Scope names are authorization metadata, never token material. Absence
        # is distinct from an empty OAuth scope set (other token types omit it).
        raw_scopes = headers.get("x-oauth-scopes")
        scopes = None
        if raw_scopes is not None:
            values = [part.strip() for part in raw_scopes.split(",") if part.strip()]
            if any(not re.fullmatch(r"[a-z][a-z0-9:_-]{0,63}", value) for value in values):
                raise GitHubAPIError("GitHub returned malformed OAuth scope metadata.", category="permission")
            scopes = sorted(set(values))
        self._oauth_scopes = scopes
        self._identity_checked = True
        user["_oauth_scopes"] = scopes
        return user

    def repository(self, full: str) -> dict:
        return self._object(self._request("GET", self._repo(full))[0])

    def projects(self, owner: str) -> list[dict]:
        if owner != "aloerch":
            raise GitHubAPIError("Project owner is outside the authorization boundary.", category="boundary")
        if not self._identity_checked:
            self.identity()
        if self._oauth_scopes is None:
            raise GitHubAPIError(
                "OAuth scope metadata is unavailable; complete personal Project enumeration cannot be verified. This importer currently requires locally authorized gh OAuth access.",
                category="permission")
        if not {"project", "read:project"}.intersection(self._oauth_scopes):
            raise GitHubAPIError(
                "Complete owned Project enumeration requires project or read:project scope; public-only results are insufficient.",
                category="permission")
        # No query or closed-state filter: enumerate all owned Projects.
        query = "query Projects($owner:String!,$after:String) { user(login:$owner) { projectsV2(first:100,after:$after) { nodes { " + PROJECT_FIELDS + " } " + PAGE_INFO + " } } }"
        return self._connection(query, {"owner": owner}, ("user", "projectsV2"))

    def project(self, project_id: str) -> dict:
        query = "query Project($id:ID!) { node(id:$id) { ... on ProjectV2 { " + PROJECT_FIELDS + " } } }"
        project = self._object(self._graphql(query, {"id": project_id}).get("node"))
        if project.get("id") != project_id:
            raise GitHubAPIError("Project node is absent or has the wrong type.", category="schema")
        selections = {
            "fields": FIELD_FIELDS,
            "repositories": "id databaseId nameWithOwner",
            "views": VIEW_FIELDS,
        }
        for name, selection in selections.items():
            query = ("query ProjectConnection($id:ID!,$after:String) { node(id:$id) { ... on ProjectV2 { "
                     + name + "(first:100,after:$after) { nodes { " + selection + " } " + PAGE_INFO + " } } } }")
            project[name] = self._connection(query, {"id": project_id}, ("node", name))
        for field in project["fields"]:
            field.setdefault("options", [])  # Options are a list, not a connection.
        project["items"] = self.items(project_id)
        return project

    @staticmethod
    def _item_selection() -> str:
        return ("""id isArchived type content { __typename
            ... on Issue { id number url repository { nameWithOwner } }
            ... on PullRequest { id number url repository { nameWithOwner } }
            ... on DraftIssue { id } }
            fieldValues(first:100) { nodes { """ + VALUE_FIELDS + " } " + PAGE_INFO + " }")

    def items(self, project_id: str) -> list[dict]:
        query = ("query ProjectItems($id:ID!,$after:String) { node(id:$id) { ... on ProjectV2 { "
                 "items(first:100,after:$after,archivedStates:[ARCHIVED,NOT_ARCHIVED]) { nodes { "
                 + self._item_selection() + " } " + PAGE_INFO + " } } } }")
        items = self._connection(query, {"id": project_id}, ("node", "items"))
        return [self._normalize_item(item) for item in items]

    def item(self, item_id: str) -> dict:
        query = "query ProjectItem($id:ID!) { node(id:$id) { ... on ProjectV2Item { " + self._item_selection() + " } } }"
        item = self._object(self._graphql(query, {"id": item_id}).get("node"))
        if item.get("id") != item_id:
            raise GitHubAPIError("Project item is absent or has the wrong type.", category="schema")
        return self._normalize_item(item)

    def _normalize_item(self, item: dict) -> dict:
        query = ("query ItemValues($id:ID!,$after:String) { node(id:$id) { ... on ProjectV2Item { "
                 "fieldValues(first:100,after:$after) { nodes { " + VALUE_FIELDS + " } " + PAGE_INFO + " } } } }")
        initial = self._object(item.pop("fieldValues", None))
        values = self._connection(query, {"id": item["id"]}, ("node", "fieldValues"), initial=initial)
        item["field_values"] = values
        item["values"] = {}
        keys = {"ProjectV2ItemFieldTextValue": "text", "ProjectV2ItemFieldSingleSelectValue": "name",
                "ProjectV2ItemFieldDateValue": "date", "ProjectV2ItemFieldNumberValue": "number",
                "ProjectV2ItemFieldIterationValue": "iterationId"}
        for value in values:
            key = keys.get(value.get("__typename"))
            if key:
                field_name = self._object(value.get("field")).get("name")
                if not isinstance(field_name, str) or field_name in item["values"] or key not in value:
                    raise GitHubAPIError("Ambiguous or incomplete Project item field values.", category="schema")
                item["values"][field_name] = value[key]
        return item

    def issues(self, full: str) -> list[dict]:
        return [issue for issue in self._rest_list(self._repo(full) + "/issues?state=all&sort=created&direction=asc")
                if "pull_request" not in issue]

    def issue(self, full: str, number: int) -> dict:
        value, headers = self._request("GET", f"{self._repo(full)}/issues/{self._number(number)}")
        value = self._object(value)
        if "pull_request" in value:
            raise GitHubAPIError("Recorded issue resolves to a pull request.", category="schema")
        if "etag" in headers:
            value["_etag"] = headers["etag"]
        return value

    def labels(self, full: str) -> list[dict]:
        return self._rest_list(self._repo(full) + "/labels")

    def dependencies(self, full: str, number: int) -> list[dict]:
        return self._rest_list(f"{self._repo(full)}/issues/{self._number(number)}/dependencies/blocked_by")

    def capabilities(self) -> dict:
        query = """query Capabilities {
          mutations: __type(name:"Mutation") { fields { name } }
          field_types: __type(name:"ProjectV2CustomFieldType") { enumValues { name } }
          project_type: __type(name:"ProjectV2") { fields { name args { name } } }
          view_configuration: __type(name:"ProjectV2ViewConfigurationInput") { inputFields { name } }
          view_layouts: __type(name:"ProjectV2ViewLayout") { enumValues { name } }
        }"""
        data = self._graphql(query)
        def names(key: str, member: str) -> list[str]:
            value = data.get(key)
            if value is None:
                return []
            entries = self._object(value).get(member)
            if not isinstance(entries, list) or any(not isinstance(entry, dict) or not isinstance(entry.get("name"), str) for entry in entries):
                raise GitHubAPIError("Incomplete capability introspection.", category="schema")
            return [entry["name"] for entry in entries]
        mutations = names("mutations", "fields")
        fields = names("field_types", "enumValues")
        project_fields = names("project_type", "fields")
        if not mutations or not fields or not project_fields:
            raise GitHubAPIError("Required Project capabilities could not be inspected.", category="schema")
        item_args = next((entry.get("args", []) for entry in data["project_type"]["fields"] if entry["name"] == "items"), [])
        return {"mutations": mutations, "field_types": fields,
                "create_view": "createProjectV2View" in mutations,
                "update_view": "updateProjectV2View" in mutations,
                "view_configuration_fields": names("view_configuration", "inputFields"),
                "view_layouts": names("view_layouts", "enumValues"),
                "project_items_archived_states": any(arg.get("name") == "archivedStates" for arg in item_args),
                "native_dependencies": "REST /repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by; verify read access"}

    def _mutate(self, operation: str, input_type: str, payload: dict, result_field: str, selection: str) -> dict:
        if operation not in MUTATIONS:
            raise GitHubAPIError("Mutation is outside the adapter allow-list.", category="boundary")
        query = ("mutation Apply($input:" + input_type + "!) { " + operation
                 + "(input:$input) { " + result_field + " { " + selection + " } } }")
        data = self._graphql(query, {"input": payload}, mutation=True)
        return self._object(self._object(data.get(operation)).get(result_field))

    def create_project(self, owner_node: str, title: str) -> dict:
        return self._mutate("createProjectV2", "CreateProjectV2Input", {"ownerId": owner_node, "title": title},
                            "projectV2", PROJECT_FIELDS)

    def update_project(self, project_id: str, public: bool, description: str) -> dict:
        if public is not True:
            raise GitHubAPIError("Only public Project provisioning is authorized.", category="boundary")
        return self._mutate("updateProjectV2", "UpdateProjectV2Input",
                            {"projectId": project_id, "public": public, "shortDescription": description},
                            "projectV2", PROJECT_FIELDS)

    def link_repository(self, project_id: str, repo_node: str) -> dict:
        return self._mutate("linkProjectV2ToRepository", "LinkProjectV2ToRepositoryInput",
                            {"projectId": project_id, "repositoryId": repo_node}, "repository", "id nameWithOwner")

    def create_field(self, project_id: str, spec: dict) -> dict:
        data_type = spec.get("type", spec.get("dataType"))
        if data_type not in {"TEXT", "SINGLE_SELECT", "DATE", "NUMBER"}:
            raise GitHubAPIError("Unsupported custom field type.", category="schema")
        payload = {"projectId": project_id, "name": spec["name"], "dataType": data_type}
        if data_type == "SINGLE_SELECT":
            options = spec.get("options")
            if not isinstance(options, list) or not options or any(not isinstance(value, str) or not value for value in options) or len(set(options)) != len(options):
                raise GitHubAPIError("Single-select field needs unique nonempty option names.", category="schema")
            payload["singleSelectOptions"] = [{"name": option, "description": "", "color": "GRAY"} for option in options]
        result = self._mutate("createProjectV2Field", "CreateProjectV2FieldInput", payload, "projectV2Field", FIELD_FIELDS)
        result.setdefault("options", [])
        return result

    def create_issue(self, full: str, title: str, body: str, labels: list[str]) -> dict:
        return self._object(self._request("POST", self._repo(full) + "/issues",
                                         {"title": title, "body": body, "labels": labels}, mutation=True)[0])

    def update_issue_body(self, full: str, number: int, body: str, etag: str | None = None) -> dict:
        # If-Match is forwarded as an additional guard, not represented as an
        # atomic guarantee; importer must also re-read and compare managed hashes.
        return self._object(self._request("PATCH", f"{self._repo(full)}/issues/{self._number(number)}",
                                         {"body": body}, mutation=True,
                                         headers={"If-Match": etag} if etag is not None else None)[0])

    def create_label(self, full: str, name: str) -> dict:
        return self._object(self._request("POST", self._repo(full) + "/labels",
                                         {"name": name, "color": "5319e7"}, mutation=True)[0])

    def add_item(self, project_id: str, issue_node: str) -> dict:
        return self._mutate("addProjectV2ItemById", "AddProjectV2ItemByIdInput",
                            {"projectId": project_id, "contentId": issue_node}, "item", "id isArchived")

    def set_field(self, project_id: str, item_id: str, field: dict, value: Any) -> dict:
        data_type = field.get("dataType", field.get("type"))
        if data_type == "SINGLE_SELECT":
            options = [option for option in field.get("options", []) if value in {option.get("name"), option.get("id")}]
            if len(options) != 1:
                raise GitHubAPIError("Single-select value does not identify exactly one existing option.", category="schema")
            encoded = {"singleSelectOptionId": options[0]["id"]}
        elif data_type in {"TEXT", "DATE"} and isinstance(value, str):
            encoded = {"text" if data_type == "TEXT" else "date": value}
        elif data_type == "NUMBER" and type(value) in {int, float} and math.isfinite(value):
            encoded = {"number": value}
        else:
            raise GitHubAPIError("Unsupported or invalid initial field value.", category="schema")
        return self._mutate("updateProjectV2ItemFieldValue", "UpdateProjectV2ItemFieldValueInput",
                            {"projectId": project_id, "itemId": item_id, "fieldId": field["id"], "value": encoded},
                            "projectV2Item", "id")

    def add_dependency(self, full: str, number: int, dependency_database_id: int) -> dict:
        return self._object(self._request("POST", f"{self._repo(full)}/issues/{self._number(number)}/dependencies/blocked_by",
                                         {"issue_id": self._number(dependency_database_id)}, mutation=True)[0])

    def create_view(self, project_id: str, spec: dict) -> dict:
        layout = spec["layout"]
        if layout in {"TABLE", "BOARD", "ROADMAP"}:
            layout += "_LAYOUT"
        if layout not in {"TABLE_LAYOUT", "BOARD_LAYOUT", "ROADMAP_LAYOUT"}:
            raise GitHubAPIError("Unsupported Project view layout.", category="schema")
        payload = {"projectId": project_id, "name": spec["name"], "layout": layout}
        if "visibleFieldIds" in spec and layout != "ROADMAP_LAYOUT":
            payload["configuration"] = {"visibleFieldIds": spec["visibleFieldIds"]}
        # Column fields, horizontal grouping, sorting and roadmap dates are
        # desired local settings, not undocumented API inputs to guess.
        return self._mutate("createProjectV2View", "CreateProjectV2ViewInput", payload, "projectV2View", VIEW_FIELDS)

    def update_view_filter(self, view_id: str, filter_text: str) -> dict:
        return self._mutate("updateProjectV2View", "UpdateProjectV2ViewInput",
                            {"viewId": view_id, "filter": filter_text}, "projectV2View", VIEW_FIELDS)
