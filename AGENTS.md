All design-package paths referenced below are relative to `plan/`. Read `plan/AGENTS.md` and the controlling individual specifications before implementation. Root product code follows the same boundaries.

# AmbisGIS agent instructions

## Mission and controlling requirements

Build an independently maintained GIS product from source-owned forks and consolidated product modules. Do not substitute a rebranded integration stack, thin forks tracking donor releases, or plugin-only reliance on externally maintained engines. Read `README.md`, `REVISION_2_CHANGES.md`, chapters 00/08/09/11/12, `DECISIONS.md`, and the relevant component spec before implementation. Chapter 11 controls source/release authority; chapter 12 controls GitHub work tracking.

Required capabilities remain service/metadata administration, managed geodatabase with branch editing, modern portal/apps, spatial notebooks and QGIS publishing. No blanket ArcGIS parity or scope expansion to Hub/Online/Knowledge. This package is a plan, not a completed GIS distribution.

## Source and architecture

All eleven core donor roots are source-owned forks built into controlled AmbisGIS releases. PostgreSQL/PostGIS/QGIS/Jupyter core custody is mandatory even when algorithms remain initially unchanged. Source modifications and substantive refactors are permitted when justified; upstream extension hooks and upstream patch acceptance are not prerequisites.

Retain one authoritative catalog/metadata/policy model, one geodatabase schema authority, one service registry and one product configuration. Retire or restrict redundant inherited mutating interfaces. An internal adapter between owned modules is acceptable; uncontrolled upstream products as permanent authorities are not.

Own source/build/dependency locks, retained archives, output artifacts and repair capability. No automatic donor synchronization, floating production tags or unrecorded package fetching. Upstream security disclosures are advisory inputs to AmbisGIS's own patch/release process. Independent maintenance is not a waiver of copyright/license/trademark obligations.

Keep native API/versioning contracts authoritative; test ArcGIS compatibility separately. Never advertise unimplemented capabilities. No direct SQL/WFS-T/notebook writes to managed branch tables. Preserve notebook origins/runtime isolation. Publishing remains a durable saga with private staging, idempotency, safe activation and compensation.

## Authorized GitHub boundaries

Only the fifteen entries in `repositories.json`, the user-owned Project in `project.json`, and task issues/PRs necessary for this plan may be created or changed under the start prompt. Verify authenticated owner `aloerch`, repository IDs, remotes, current branch and working directory before writes. Never modify `weaveatlas`, `osgs-neu` or unrelated existing repositories. Do not adopt collisions by title alone.

Repository bootstrap defaults to read-only; `--apply` creates missing approved public repositories/forks only. It does not set branches, enable workflows or create a Project. After source/workflow review, establish `ambisgis/main` from approved donor baselines; it may become the default for these newly created forks. Preserve donor references and shared history. Never force-push or publish into donor package namespaces.

Implement GOV-01's dry-run/idempotent Project importer from the detailed specification. The included seed exporter is not the live provisioner. Project changes need appropriate local authorization; missing permission does not authorize automatic scope escalation. No tokens in chat, receipts, code or logs; no unreviewed workflows, secrets installation, deletion, paid services or production changes. Do not contact upstream maintainers without specific permission.

## Work loop and Project evidence

Select a ready task with actual dependency evidence. Read its live issue, claim the task and use a separate branch/worktree. Define acceptance/failing tests; implement; run actual relevant tests; inspect the diff; update issue/STATUS/ADR evidence and open a PR. One integrator controls shared contracts and migration ordering.

Respect Delivery states: Backlog → Ready → In progress → In review → Verified → Merged → Released, with Blocked/Cancelled separate. Do not equate a generated scaffold, passing mock, closed issue, merged PR or imagined release with product acceptance. Initial JSON status is a seed, never a command to reset live progress. Preserve human discussion, assignments and manual planning during imports.

Do not invent source revisions, dependency pins, field IDs, issue IDs, hashes, API flags or remote actions. If a Project view requires a verified UI step, record it as pending rather than claiming setup succeeded. Continue independent unblocked tasks when a credential/UI review gate is pending.

## Verification and reporting

Run `python3 -m unittest discover -s tests -v` and `python3 tools/validate_package.py --require-schemas` for package checks. They are not GIS product tests. Require real database concurrency, authorization, publication, browser/accessibility, notebook isolation, restore and no-upstream rebuild/repair tests for their tasks. Report failures, skips and unavailable environments explicitly.

Human review gates apply to security, data migrations, licenses/brand, release signing and deployment. End sessions with exact task/repo/branch/commit/PR, tests, remote state changes, remaining acceptance and next ready task. Do not claim background work or silently weaken scope.
