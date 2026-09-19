# 10 — Codex execution protocol

## 1. Initial execution environment

Open the extracted package in Visual Studio Code and use the current Codex extension workflow. The local workstation needs Git, GitHub CLI, Python, a supported container runtime and a fresh workspace with enough disk for upstream forks. Codex must inspect installed versions rather than assume a pre-existing environment is suitable. Follow current OpenAI agent-instruction behavior for `AGENTS.md` and directory-scoped instructions. [S37–S38, S65]

No cloud account, paid service, domain purchase, production database, employer network or private repository is needed for initial development. Synthetic data and local containers are sufficient. External source downloads and repository creation are explicit actions; no arbitrary `curl | sh`, broad permission escalation or installation into the user's global Python environment.

## 2. First Codex session

Read `AGENTS.md`, `README.md`, architecture, repository/licensing design, roadmap, `repositories.json`, `requirements.json`, `project.json`, chapters 11/12 and `backlog.json`. Inspect tool availability and GitHub identity. Run package unit tests and validation. Run the repository bootstrap in its default dry-run mode and inspect all targets. The master prompt authorizes explicit creation of only the allow-listed new public repos/forks; execute `--apply` once preflight passes.

Capture the bootstrap receipt locally. Clone only approved targets into a new workspace. Verify repository IDs/remotes before writing. Copy the plan to `ambisgis-platform/plan/` (and place applicable instructions at repository root) on a feature branch, preserving the original package paths for references. Do not duplicate the combined design book as a second editable source; individual `docs/*.md` remain authoritative.

Seed minimal component scaffolds and CI only where the first tasks need them. “Scaffold complete” is not “platform complete.” Preserve upstream source/license files and audit Actions before enabling them. Prepare a PR for the plan/scaffolding, then implement P0 source-custody/owned-build and capability evidence tasks, GOV-01/GOV-02 Project governance and the P1 slice in reviewable branches. Donor branches are preserved as references; the canonical product branch is ambisgis/main, not an automatically synchronized upstream branch.

## 3. Task loop

For each ready task, record task ID, owning repo, dependency evidence, exact acceptance criteria, affected interfaces and intended tests. Create a feature branch/worktree. Make a small implementation plan, then write tests and code. Run the smallest relevant tests, then required integration/contract suites. Inspect the diff for secrets, licensing changes, generated noise and unexpected scope.

Update status with actual commands/results, unresolved issues and next dependency. Open a PR with behavior before/after, migration/recovery notes, screenshots only where useful, tests, and capability changes. Do not mark a task done until merged/reviewed according to its gate. If a test cannot run in the current environment, say exactly which one and why; do not substitute a passing mock and keep the same claim.

Tasks too large for one context are split into child tasks retaining the parent acceptance criteria. A handoff records exact branch/commit, changes, current failure, next command and expected result. It must not rely on the next agent remembering a private conversation.

## 4. Parallel agent boundaries

Useful lanes are platform/catalog/auth, geodatabase correctness, QGIS/publishing, web applications, and notebooks/operations. Each uses a separate Git worktree and task branch. One integration owner controls shared contracts and migration ordering. No two agents independently change the same schema contract or database migration sequence without coordination.

The reviewer gets the acceptance criteria and diff, not a request to endorse the author's reasoning. Reviewers should actively attempt authorization bypasses, stale-state edits, schema breaks and inconsistent publication/recovery paths. Performance and security claims require executable evidence.

## 5. Context and documentation discipline

The authoritative engineering plan is individual specs plus machine-readable tasks/contracts. GitHub issues and the umbrella Project hold live progress, assignment, review and evidence per chapter 12; initial backlog status must never reset live state. `STATUS.md` is current progress, `DECISIONS.md` is a decision index, `adrs/` contains accepted/rejected architectural changes, and task/PR evidence is linked from status. Keep instructions concise enough to load reliably; do not paste the entire design into every AGENTS file.

An ADR records context, options, chosen decision, consequences, migration/compatibility impact, evidence and reversal criteria. Decisions that change engines, public contracts, storage/version semantics, licenses, privacy or scope need an ADR. Do not quietly delete difficult requirements to make tests pass.

## 6. The first useful implementation slice

After P0 gates, implement exactly this journey: initialize a local installation; create two identities; sign in as publisher; upload a small synthetic address layer; generate schema and metadata; publish a private map/feature service; inspect the item in the new shell; query the layer; confirm the second user is denied; grant read access; confirm access; revoke access; confirm new feature/map requests fail; restart and repeat a query.

Required code includes the installer/config generator, catalog extension, policy gateway, GeoServer adapter, one durable publication path, dataset identity schema, a minimal UI and end-to-end tests. This slice does not need dashboards, general branch editing, every raster driver or an ArcGIS facade. It establishes the integration/security spine that later features reuse.

## 7. Human release gates

Human review is required before broad public binary distribution, license/trademark decisions, production credentials/data use, destructive migration/cleanup, security-critical release, and switching a real organization to the product. The bootstrap is already limited to new public repos/forks and does not require production access. Agents must not silently purchase infrastructure, change DNS, contact third parties, disclose private data or auto-merge high-risk migrations.

A human gate is not an excuse to stop all work: prepare a reproducible diff, tests, decision record and exact review question, then continue independent unblocked tasks. Do not promise background completion. Every session ends with concrete repository/commit/test status and the next ready task.


## Revision 2 task evidence

All work must satisfy the independent-product rules in chapter 11, including source custody and consolidation. Read the task issue and dependencies, record live Delivery transitions, and preserve source/issue/Project exports. A future donor update cannot change a release unless a reviewed AmbisGIS change selects it. The first product slice includes owned source builds; the complete release includes the independent repair/rebuild drill.
