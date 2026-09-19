# FND-02 Jupyter slice — final resumption record

The bounded owned Jupyter build/runtime slice is reviewable in
[PR #53](https://github.com/aloerch/ambisgis-platform/pull/53), **open and unmerged**.
Repository `aloerch/ambisgis-platform` (ID1376927351); branch
`fnd-02/jupyter-runtime`; implemented/tested code commit
`ee6d2d135fd64e1b9ad5372bd0506fa077af4456`. Subsequent commits update evidence and
handoff only. Verify the actual PR head below rather than treating this code
commit as the latest review head. FND-02 remains **In progress**.

Worktree: `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-jupyter`.
Integration base: PR #51's actual owner merge
`a3c2e2e696ea11bdc10c2ad202a240fbd0137f45`. The original database worktree remains
at `1c3a9b7f85c45cb8f00ac2ebe70041b2fbd755b9`; its reviewed head, archives and
previous runs were preserved. No merge is authorized by this implementation request.

## Exact input and output checkpoint

- Owned Hub6.0.1: `3e516c6f382b481e815ec455befb2f14d80d337b`;
  Lab4.6.3: `e7255a9334c12ad8f9cb15db27584215fab5ece2`. Tag-object identities,
  declared constraints/advisories and build transformations are in the audit.
- Retained Node24.21.0/npm11.19.0, Yarn3.5.0, proxy5.3.0, host Python3.13.15.
  Server2.21.1, ipykernel7.3.0 and client8.10.0 passed actual runtime checks.
- Custody: `/home/revelberry/Projects/AmbisGIS/source-archives/jupyter-slice`;
  manifest SHA256 `fc0b29f213d4613f5a0595bca7e8d179f0b2e8f40fc8ddff9e3d56c771d7d2b5`.
  5,510 files /817,990,927 bytes;146 Python distributions with sdists;
  2,830 JS distribution records;3,522 notices /1,156 unique bodies.
- Build root: `/home/revelberry/Projects/AmbisGIS/build-worktrees/jupyter-slice`.
  Final clean `run-002` passed24 top-level commands under Internet-socket denial;
  nested local PAM commands passed. All prior runs/failures remain retained.
- Hub wheel: `run-002/wheels/jupyterhub-6.0.1-py3-none-any.whl`, SHA256
  `e3c8ddb0b8307e54debddc75af2ffc1fc59d690fa3cf987693da09e404d5a277`.
  Lab wheel: `run-002/wheels/jupyterlab-4.6.3-py3-none-any.whl`, SHA256
  `98c21e3a6a98e011418ad5d586f3679fdfe942254dd1ac1e3d1f4f10147b8d02`.
- Final native report: `run-002/native-tests/report.json`: **329 passed,
  zero failures/errors/skips** (Hub137, Lab69, JSX55, coreutils62, nbformat6).
- Full runtime reports: `runtime-evidence/runtime-ivnhawpn/report.json` and
  `runtime-evidence/runtime-tgw1e3j7/report.json`, both passed standalone and
  Hub/proxy/singleuser flows. Each verified418assets, real kernels/notebook reopen,
  credential denial, local listeners and orderly shutdown without descendants.
- Current tooling:20 Jupyter harness +22 database harness +175 package tests;
  zero skips/failures; strict plan checks and four schema/example checks passed.
  Database native tests were not repeated; older results remain historical.
- `run-002/native-linkage.json` deliberately retains an exit1 diagnostic for an
  unused bundled musl Parcel binary. `native-linkage-selection.json` proves actual
  Node selection of the glibc sibling with no missing linked libraries. Nine host
  libraries and host Python/stdlib/compiler tooling remain unretained.

[Full evidence](jupyter-slice-evidence.md), [machine receipts](../verification/jupyter-slice.json),
[review findings](../verification/jupyter-slice-review.txt),
[build/test/recovery commands](../../build-support/jupyter/README.md).
Local venvs/build prefixes have absolute paths and are not relocatable releases.
No host authentication configuration, inherited workflow, secret, source-fork
default, deployment or release changed. No work remains running.

## Required owner actions

1. **FND-02 / PR #53 — review this bounded checkpoint.** In the PR, examine the
   source/dependency/license inventory, Hub archive-data fix, owned Lab frontend
   provenance, actual native/runtime receipts and documented host/source gaps.
   Decide whether this experimental development slice is acceptable and record
   the review on PR #53. This blocks merging that slice; it does not block the
   independent next FND-02 audit. Resolution is an explicit review and, if the
   owner chooses to merge, verified GitHub merge readback. No approval of a full
   product baseline, licenses/security or P6 is inferred from this checkpoint.
2. **GOV-02 / issue #9 / PR #52 — complete two saved-view checks.** In Project#2
   [Review and approvals (view5)](https://github.com/users/aloerch/projects/2/views/5),
   retain the Delivery filter and use the UI field picker to add Review gate values
   **Human approval, Security, Data migration, License/Brand**, then save. In
   [Release roadmap (view4)](https://github.com/users/aloerch/projects/2/views/4),
   confirm Status is hidden or record its explicit derived mapping from Delivery;
   preserve Phase grouping and accepted date fields. Examine
   [PR #52's accepted evidence and exact limitations](https://github.com/aloerch/ambisgis-platform/blob/gov-02/saved-view-reconciliation/plan/docs/project-view-reconciliation.md).
   Record the exact saved observations or UI limitation in
   [issue #9](https://github.com/aloerch/ambisgis-platform/issues/9). Supported
   filter readback plus attributed roadmap observation proves resolution; it
   permits the task to proceed through review according to Delivery policy.
   These checks block GOV-02 only, not independent engineering. Do not repeat
   already verified settings or rerun the importer.
3. **PR #52 — review the separate governance correction.** Examine Delivery's
   column-field correction and the accepted owner/API evidence, with175 passing
   package tests and schema checks. Record the review there; after the remaining
   view checks, Verified/Merged require actual approvals/merge evidence. The PR
   remains open at `cb871e82f15be7363c3dc0e786923e9572d77d11` on
   `gov-02/saved-view-reconciliation`. This affects governance acceptance only.

No product release decision is ready: canonical full-tuple, file/license,
production security, browser/isolation, source/repair and P1/P6 evidence remain
engineering/review gates with explicit omissions in the evidence document.

## Exact resume checks

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
TASK_GH=/tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh
cd "$TASK_ROOT/ambisgis-platform-jupyter"
git status --short --branch
git remote -v
git log -2 --format='%H %s'
"$TASK_GH" api user --jq .login
"$TASK_GH" pr view 53 --repo aloerch/ambisgis-platform \
  --json state,headRefName,headRefOid,baseRefName,mergeCommit,reviews,comments
"$TASK_GH" issue view 3 --repo aloerch/ambisgis-platform --comments
"$TASK_GH" issue view 9 --repo aloerch/ambisgis-platform --comments
python3 build-support/jupyter/acquisition.py \
  --custody "$TASK_ROOT/source-archives/jupyter-slice"
```

The verified CLI and validation venv exist at the recorded /tmp paths now; check
before reuse, and recover missing tools only from the existing pinned retention
procedures, never global installation or credential printing. Git's inherited
credential helper points to absent `/usr/bin/gh`; the successful push used a
per-command helper override pointing to the verified retained CLI, without
changing global config. No credential is contained in that path/receipt.

To repeat the local runtime without rebuilding, use the README's runtime command
with `TASK_RUN="$TASK_ROOT/build-worktrees/jupyter-slice/run-002"`; every probe
creates fresh disposable state. It verifies the exact saved wheel/PAM receipts
before launch. Native tests need a new `--output` directory if rerun. A clean build
uses unused `run-003` and new offline receipt as documented. Preserve every run.

**Next ready action:** remain in FND-02, claim the Java rendering dependency audit
in live issue#3, then use a separate branch from current `ambisgis/main` (or record
any actual newly established dependency). Retain the exact GeoTools34.5 →
GeoWebCache1.28.5 → GeoServer2.28.5 closure and required GeoNode extensions before
building. The client/MapStore and QGIS work follows the recorded dependency graph.
Do not append that work to PR #53 or treat FND-07/FND-08/P1 as accepted. Java/client
builds were not started in this slice.
