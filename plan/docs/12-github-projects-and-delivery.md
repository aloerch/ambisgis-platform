# 12 — GitHub Projects and AI-assisted delivery governance

## 1. Project model and Azure DevOps comparison

Use a current **GitHub Project (Projects v2)** owned by `aloerch`, titled **AmbisGIS — Product Development**. This is the cross-repository planning surface, not a repository and not a runtime component. GitHub Projects provides table, board and roadmap views of issues/pull requests with custom metadata and automation. An Azure DevOps Project is a broader container for services and access; GitHub Projects is closer to the work-tracking/backlog portion of that experience. [S48, S53]

Link all fifteen approved repositories. Keep one umbrella Project with filtered component views instead of one disconnected board per fork. Initial task issues live in the owning repository recorded in `backlog.json`; those owners are the four new first-party repositories. Source-fork changes link to their controlling issue and may get fork-local issues where appropriate. Enable Issues on newly created forks only through reviewed project setup when needed, never as an unrelated change to an existing repository.

Project visibility is explicitly **public**, matching the intended open product. Only synthetic examples and publishable plans belong there. No tokens, internal infrastructure, employer data or undisclosed security reports. A private security-reporting mechanism is separate.

## 2. Files, live state and authority

`backlog.json` defines task identity, requirement links, dependencies, acceptance criteria, owning repository and planned tests. `requirements.json`, contracts, ADRs and specifications remain version-controlled engineering authority. Initial task IDs remain stable across title/brand changes.

GitHub Issues holds discussion, assignees, review links and test evidence. The Project holds current delivery state, priority, iteration and release selection. The JSON backlog's initial `status: not_started` is a seed, not permission to reset a live task. After provisioning, changes to live progress come from verified events or deliberate status updates, not a re-import of the design.

The importer maintains a local receipt with owner ID, project node ID/number/URL, repository IDs, task ID to issue node/number/URL mappings, project item IDs and managed-content hashes. A separate publishable export can contain non-secret remote IDs and URLs; credentials are never included. Export issues, project configuration, relevant evidence and source metadata regularly so GitHub is not the only recoverable copy of the engineering history.

## 3. Project schema

The machine-readable desired schema is `project.json`. Retain built-in title, repository, assignee, labels and milestone metadata. Add the following product-specific fields:

| Field | Type | Purpose |
|---|---|---|
| Task ID | Text | Stable key such as FND-07 or DB-06. |
| Delivery | Single select | Backlog, Ready, In progress, In review, Verified, Merged, Released, Blocked, Cancelled. |
| Phase | Single select | P0 through P7. |
| Component | Single select | Platform, Database, Server, Desktop, Web apps, Notebooks, Governance, Security/Release. |
| Priority | Single select | Critical, High, Normal, Low; do not confuse with the P0 phase. |
| Risk | Single select | Low, Medium, High, Critical. |
| Review gate | Single select | Standard PR, Human approval, Security, Data migration, License/Brand, Release. |
| Target release | Text | Product-wide release designation, initially unscheduled. |
| Evidence | Text | Link to evidence record or PR; not a fabricated pass marker. |
| Start date / Target date | Date | Roadmap scheduling after estimation. Initially unset. |

Use a distinct `Delivery` field rather than silently changing GitHub's built-in Status options and workflows. Either hide the built-in Status in the custom views or explicitly map it as a derived coarse state. It must not become a second delivery authority. Optional iteration planning can be configured after P0 scope evidence; do not invent sprint dates.

GitHub CLI's documented field-creation types are TEXT, SINGLE_SELECT, DATE and NUMBER. Do not invent a `gh project field-create --data-type ITERATION` flag. Check the current GraphQL/UI capabilities for iteration/view configuration at execution. [S50–S51]

## 4. Required views

**Product backlog — table:** all non-cancelled task issues; group by Phase and sort by Priority/Task ID. Show dependencies, risk and review gate.

**Execution board — board:** group by Delivery; show Ready, In progress, In review, Verified and Blocked, with other states available. Work in progress is governed by assignee/task claims rather than an arbitrary number of agents.

**Release roadmap — roadmap:** group by Target release or Phase and use Start date/Target date. Empty dates remain empty until planning evidence supports them; phases alone are not invented calendar estimates.

**Review and approvals — table:** filter to review-ready or blocked tasks with human/security/migration/license gates; show PR and Evidence.

**Source and security maintenance — table:** retain source-custody/build/patch tasks and subsequent dependency vulnerabilities; sensitive vulnerabilities stay off this public board.

Component-specific views are filtered views of the same Project. A saved view must actually exist and be verified before GOV-02 is closed. If the currently available supported APIs cannot create a view, provide the exact UI operation for the owner and keep that subtask incomplete; do not guess undocumented mutations or pretend configuration succeeded.

## 5. Issue structure and hierarchy

Each task issue has a stable title prefix `[TASK-ID]`, a unique machine marker, version-controlled specification links, requirement IDs, dependency task IDs and issue links, deliverables, acceptance checkboxes, test identifiers, risk and review policy. Use `tools/export_project_seed.py` to produce the initial issue bodies without network access.

Once issue URLs are known, create native blocked-by/blocking relations corresponding to the dependency graph. GitHub documents dependency creation/editing and CLI flags; the installed CLI version must support the selected operation. Otherwise use a documented API supported at execution or retain explicit linked dependency text with a tracked automation gap. Preserve `backlog.json` as the complete authoritative graph. [S64]

Phase epics may be created in the umbrella repository and linked to children, but they are grouping issues, not duplicates of task work. Close an epic only when its acceptance demonstration passes. Sub-issues/hierarchy may be used where supported by the execution environment; a unavailable feature must not erase dependencies or acceptance criteria.

Milestones are repository-scoped. Use a Project `Target release` field for cross-repository product releases; optional repository milestones map to it, not the other way around. [S63]

## 6. Safe provisioning algorithm — implement in GOV-01

The package includes a tested local seed exporter, **not a live Project provisioner**. Codex implements `tools/bootstrap_github_project.py` as GOV-01 with these behaviors:

1. Validate manifests and the acyclic dependency graph. Check GitHub identity and the fifteen repository IDs against the repository bootstrap receipt. Read project/issue/field state completely with pagination. For GraphQL read-only preflight, HTTP POST is normal; distinguish queries from mutations rather than claiming every read uses HTTP GET.
2. Default to dry-run: list intended creates and managed updates without remote mutations or local creation receipts. Detect rate limits, authentication errors and partial GraphQL errors. Missing permission is not evidence that a Project does not exist.
3. Resolve by a recorded Project node ID. Without a receipt, search owned Projects for the exact title/marker; an existing ambiguous or unverified match is a collision requiring inspection, not a reason to adopt it or create a duplicate. Check closed Projects as well.
4. Under an explicit `--apply`, create only the named Project if missing, set public visibility and description, record ID immediately and link verified approved repositories. No unrelated Project or repository is eligible for mutation.
5. Create/reconcile custom fields by exact name and type. Read back field/option IDs. Unknown type conflicts stop; they do not delete fields or overwrite human data. Do not assume numeric Project number equals GraphQL node ID or item ID.
6. For each stable Task ID, enumerate candidate issues in its owning repository and verify the machine marker. Create the issue if absent; on timeout re-read before retry. Add the issue to the Project once and set initial fields only for newly seeded items. Store IDs after each successful operation.
7. In a second pass attach dependency links after all task issue URLs are known. For changed specifications update only the bounded machine-managed body block with optimistic concurrency/content-hash checks; preserve user text, comments, assignment, Delivery, dates and manual priority.
8. Read back visibility, fields, links, issue count, markers and dependency edges. Report actual completion, partial work and blocked UI steps. A repeated run with unchanged input must perform no duplicate creations and no progress reset. Never delete a Project/issue, force-push, reopen closed work, archive evidence or escalate scopes automatically.

Tests cover wrong owner, missing scope, duplicate titles/markers, wrong issue repo, pagination, HTTP/GraphQL partial failure, response lost after create, schema mismatch, interrupted import, task body edits and unchanged rerun. A receipt is operational state, not a secret credential or proof against a malicious administrator.

## 7. Documented command building blocks

These are building blocks for the idempotent importer, **not a blind repeatable setup script**. Query existing state and receipt IDs before each corresponding mutation. [S49–S51]

```bash
# Read the identity and current authorization; never print tokens.
gh auth status
gh api user --jq .login

# After checking collisions and obtaining explicit apply authorization:
gh project create --owner aloerch \
  --title 'AmbisGIS — Product Development' --format json

# Use the actual returned project number, not an assumed number.
# PROJECT_NUMBER must be set from the verified creation/read response.
gh project field-create "$PROJECT_NUMBER" --owner aloerch \
  --name 'Task ID' --data-type TEXT --format json

gh project field-create "$PROJECT_NUMBER" --owner aloerch \
  --name 'Delivery' --data-type SINGLE_SELECT \
  --single-select-options 'Backlog,Ready,In progress,In review,Verified,Merged,Released,Blocked,Cancelled' \
  --format json
```

The owner may need to authorize project access locally with `gh auth refresh -s project`. Codex must not execute an authorization escalation without the owner's participation, request the token in chat, or commit a token. Separate repository creation permissions from Project permissions; one does not establish the other. The CLI/API also has permission distinctions for query-only access. [S49–S50]

## 8. Ongoing automation and agent conduct

Every Codex session reads root `AGENTS.md`, the relevant specifications, its live issue and current dependency evidence. It claims one Ready task, records the branch/worktree and moves Delivery to In progress. Parallel agents use separate worktrees and non-overlapping scope; one integrator owns shared schemas/migrations. An agent cannot mark a dependency complete merely because code was written or a draft PR exists.

Delivery transitions require evidence: **In review** means a reviewable PR and actual test output; **Verified** means required checks and approvals passed; **Merged** means the approved change landed in the appropriate owned product branch; **Released** means the accepted change is included in an actual product release manifest. A task may be Merged for substantial time before release. Cancellation is never counted as successful delivery. Local progress remains exportable during a GitHub outage.

GitHub Actions may synchronize issue/PR events, but repository `GITHUB_TOKEN` is not sufficient for Projects access. For this personal-account Project use appropriately scoped user authorization where necessary; an organization-owned future Project can use an appropriately permissioned GitHub App. Secrets installation requires deliberate authorization. Never expose Project credentials to untrusted PR code or execute a PR checkout with elevated `pull_request_target` permissions. Prefer local CLI updates initially over introducing an unreviewed privileged automation service. [S52]

A merged PR is not proof that multi-repository product acceptance passed. Release tasks remain gated on source custody, tests, security, licenses, upgrade and recovery evidence. Dependency scanning suggests work; it never auto-merges donor updates into product branches.

## 9. Acceptance and reporting

GOV-01 passes only after safe provisioning/retry tests and verified live Project/issue creation under authorized execution. GOV-02 passes only after required views, field mappings and evidence-preserving transitions are demonstrated. Package preparation does not satisfy either gate.

Each session ends with task ID, repository/branch/commit/PR, tests actually run, failures/skips, remote Project state changes, remaining acceptance criteria and next ready task. A blocked credential or UI step is reported specifically while independent unblocked engineering continues. The Project is a delivery aid, not a reason to weaken the product's source-independence requirements.
