# FND-02 database slice — resumption record

**Historical checkpoint below.** PR #51 was subsequently merged by the owner at
`a3c2e2e696ea11bdc10c2ad202a240fbd0137f45`. The separate
[Jupyter slice handoff](jupyter-slice-handoff.md) now controls resumption; this
merge accepted the database development checkpoint only. Preserve these original
build reports and commands. No database native rebuild occurred in the Jupyter slice.

The bounded owned PostgreSQL/PostGIS build slice is reviewable. FND-02 remains
**In progress**; [PR #51](https://github.com/aloerch/ambisgis-platform/pull/51)
remains open and unmerged. Merge requires explicit owner approval for this PR.
Repository: `aloerch/ambisgis-platform` (ID 1376927351).
Branch: `fnd-02/source-evidence`. Implemented/tested code commit:
`9c8b32bcce74870473d947d2ed6810b6c5041e2f`; subsequent commits contain evidence
and handoff only. Verify the live PR head with the commands below.
The approved integration base is PR #50 merge
`3e7581a06b000856ea9b27468cc415612c28b4b0`.

Actual feature worktree is `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-source`.
The initial `/home/revelberry/Projects/AmbisGIS_Codex_Plan` directory is a separate
checkout with no remote. Preserve existing source no-checkout clones, worktrees
and all three build runs. No native source/default/workflow was changed.

Exact candidates: PostgreSQL 15.19 at `2ff1375b5dd8bf09d8cb0e795974528180fd75ca`;
PostGIS 3.5.7 at `9816f82458db774e62906cfb2c4f01f8b262c862`; earlier fixture
3.5.6 at `9aa71a8e5059959929825926db5ebefafde471db`.
Twenty pinned archives / 320,548,182 bytes and 93 notices are retained in
`/home/revelberry/Projects/AmbisGIS/source-archives/postgis-slice`.
Dependency versions, feature flags, licensing questions, failures and omissions
are in [slice evidence](postgis-slice-evidence.md) and the linked manifest/audit.

Final `build-worktrees/postgis-slice/run-003` has 103 zero-exit build commands,
217 PostgreSQL core + 1 fuzzystrmatch tests, target PostGIS CUnit 413 tests /
51,347 assertions, and 672 + 672 SQL regressions with zero failures or skips.
Actual earlier-version upgrade: 13 old + 13 upgraded + 13 fresh spatial checks,
with geometry/raster/topology witnesses preserved. Final linkage-guard smoke:
13 additional checks. All owned clusters stopped; no builds/tests are left running.
175 package tests, 22 harness tests and four schema/example checks passed.
This is experimental candidate evidence with documented dependency-test gaps;
it does not approve licenses, baselines, a production security profile, FND-07,
FND-08, P1 or whole-product independence/repair acceptance.

Run-003 records relative to `build-worktrees/postgis-slice/`:

- Earlier fixture: `run-003/databases/database-dqiotqr3/prepare-upgrade-kva1evgy/report.json`.
- Real upgrade: `run-003/databases/database-dqiotqr3/finish-upgrade-klpvwwyz/report.json`.
- SQL suites: `run-003/regressions/database-lze8n9do/regression-22146fi8/report.json`.
- Final smoke: `run-003/databases/database-i77hsodz/smoke-m_jrcky1/report.json`.
- Full snapshots: `run-00{1,2,3}-evidence-final.json`; completed output archive:
  `run-003-prefix.tar.gz` (local absolute-path build, not a relocatable release).
- Seven `offline-run003-*.json` receipts record successful commands and inherited
  seccomp IPv4/IPv6 denial. Host tools/libraries and local UNIX services remain
  outside complete source/isolation closure. The failed `offline-run002.json`
  is retained as a failed attempt. Run-001's exploratory failures remain recorded.

[Machine evidence](../verification/postgis-slice.json) contains hashes and actual
counts. Full logs, extracted sources, build artifacts and databases remain local,
outside Git. Do not replay `finish-upgrade` on the completed fixture: its SQL
extensions are now 3.5.7. Use a fresh run and the two-phase recipe for another
real earlier-version upgrade.

## Exact resume checks

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
cd "$TASK_ROOT/ambisgis-platform-source"
git status --short
git log -1 --format='%H %s'
git remote -v
/tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh pr view 51 --repo aloerch/ambisgis-platform --json state,headRefName,headRefOid,baseRefName,reviews,comments
python3 build-support/postgis/acquisition.py --custody "$TASK_ROOT/source-archives/postgis-slice"
python3 -m unittest discover -s build-support/postgis -p 'test_*.py' -v
cd plan
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 -m unittest discover -s tests -v
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 tools/validate_package.py --require-schemas
```

For a fresh native reproduction, use [the exact build/upgrade/regression/offline
commands](../../build-support/postgis/README.md), selecting unused `run-004`.
No system installation is required; the current host toolchain remains an
explicit unretained dependency. Inspect running processes and build locks first.

Next ready engineering action stays in FND-02: inspect the retained Jupyter
histories and their declared runtime requirements before proposing the unresolved
tuple entries, then continue the owned Java/client dependency audit/builds.
Read current issue discussion and claim that work before implementation:

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
/tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh issue view 3 --repo aloerch/ambisgis-platform --comments
git -C "$TASK_ROOT/ambisgis-jupyterhub" for-each-ref --sort=-version:refname --format='%(refname) %(objectname)' refs/tags
git -C "$TASK_ROOT/ambisgis-jupyterlab" for-each-ref --sort=-version:refname --format='%(refname) %(objectname)' refs/tags
```

GOV-02 remains separately **Blocked**: owner must verify saved grouping, sorting,
filters, roadmap Start date/Target date fields, and Delivery rather than built-in
Status in each actual saved view. The exact five-view steps are in
[the operations guide](project-importer.md#views-and-remaining-ui-verification).
View names/layouts alone are insufficient. Preserve human planning values and
issue discussion; do not reapply seed state or rerun GOV-01.
