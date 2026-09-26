# FND-02 acceptance and FND-07 source recovery checkpoint

Repository `aloerch/ambisgis-platform` (ID `1376927351`), branch
`fnd-07/source-baseline-restore`, integration base
`973a5ef383687cd00143c679f832cfb006a57cf0`. Worktree:
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-source-restore`.
Review [PR #69](https://github.com/aloerch/ambisgis-platform/pull/69) is open and unmerged. This checkpoint does not complete FND-07 or FND-08.

## Owner actions

Review this platform PR as acceptance-linkage and source-custody tooling/evidence.
The exact [promotion plan](../verification/source-baseline-restore/promotion-plan.json)
lists all eleven repository IDs, absent target refs/expected old SHAs, original
and proposed commits/trees, retained bundle chains, modified paths and notices.
It proposes `ambisgis/review/fnd-07-baseline-v4` as a new **non-default** source ref.
No public source-fork ref or default was changed.

Separate approval is required before pushing those exact source refs. The
recommended prerequisite is explicit repository Actions disablement on exactly
the eleven source forks. All eleven currently have Actions enabled; an empty
registered-workflow list is not evidence that pushes cannot execute inherited
workflows. The selected trees contain 113 YAML workflow definitions plus two
QGIS disabled files. The audit records default-tree workflows separately. A
fully reviewed workflow execution plan is an alternative to disablement. Neither
choice is implicitly approved by this platform PR. Reverify identity and absent
refs immediately before any later push; a new collision stops promotion.

Later creation/promotion of `ambisgis/main` remains a separate exact decision.
No approval here permits force/mirror push, donor history rewriting, default
changes, new public repositories, archive/binary publication, release, deployment,
or future merges. Existing rights/notices, security and operational gates remain.

## Task status and unchanged acceptance criteria

FND-02 is **owner-accepted and Merged**, with issue #3 correctly left closed.
The [actual owner comment](https://github.com/aloerch/ambisgis-platform/issues/3#issuecomment-5785944488)
was authored by `aloerch` (ID `15285626`) at `2026-09-22T23:20:02Z`.
It independently accepts the exact candidate, C1–C4, NO-ORACLE/headless-Temurin17/
NO-JPEG2000 limits and maintenance rule, including internal rows F02-06/07/08.
It is distinct from the earlier agent-authored handoff under the same account.
The [governance sidecar](../verification/fnd-02-owner-acceptance/acceptance.json)
binds the immutable manifest, owner comment, reviewed PR head and real merge.
The criterion report/checklist are reconciled without changing their original
four criteria/eight pass conditions or the importer-owned issue body.

FND-07 depends on that decision and was [claimed separately](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5786023078).
Project Delivery is **In review**; issue #6 remains open. Its three criteria remain exactly:

| Original criterion | Actual evidence and pending work |
|---|---|
| Every selected core component resolves to an owned source revision and retained baseline. | Eleven core roots restored from verified full-history bundles into independent repositories; accepted modifications replayed and compared to producer evidence; seven new local product commits and four unchanged selected revisions. The platform recipe revision is separately retained. Public product-branch delivery and owner review remain pending. |
| No source transfer implies a copyright reassignment or blanket relicensing. | All 235 inventoried notice-related tracked paths retain their Git blobs/modes. This filename-based inventory is not a claim of semantic notice completeness. Class B sources, original notices and excluded historical material retain their actual rights. ADR 009 and the donor-change ledger explicitly deny reassignment, blanket licensing or redistribution approval. Human review remains required. |
| All required additional assets are enumerated; nulls are explicit blockers, not fabricated hashes. | Selected core gitlinks/LFS were inventoried; the one MapStore submodule is independently materialized, and no selected core LFS pointer is present. Selected source/resource/generation/vendor assets are recovered with exact inventories and hashes; existing dependency manifests remain linked. No unavailable input was silently selected or given an invented hash. Final inventory-scope approval and source delivery remain pending; broader build/bootstrap obligations below are not represented as complete. |

FND-08 still depends on FND-07 and remains unaccepted. This does not complete P0,
source/bootstrap and operational obligations, notices/distribution, security,
signing, deployment or release. Eligibility remains exit 2; no permission field
in the accepted manifest was turned true.

## Exact selected and restored identities

- Accepted candidate `fnd-02-json-nojpeg2000-proposal-4`, revision 4/schema 1:
  SHA256 `0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99`.
- Reviewed PR #68 head: `7c4c6a6ddbc364e520911e06b9a97a7c10bdcfcf`;
  actual merge: `973a5ef383687cd00143c679f832cfb006a57cf0`.
- Accepted WAR: `90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1`.
- Replacement map: `194139a86bb3640d991b4c23bc55b02d66526127bdea6c3d6f025216d41f87f5`.
- First actual source recovery receipt:
  `7852514aed5df0f935aeb146cd2d0bb3d106e22e92fb9b73416439b39b0c4469`.

[The exact source summary](../verification/source-baseline-restore/source-summary.json)
and [promotion plan](../verification/source-baseline-restore/promotion-plan.json)
record each base/product commit, source tree, bundle SHA and product delta
prerequisites. New local commits use honest current metadata identifying the
recovery operation; they do not impersonate historical donor commits/signatures.
The [CHANGES_FROM_DONOR ledger](../../build-support/source_restore/CHANGES_FROM_DONOR.md)
records every changed path and why it differs. The executable workflow derives
selection from the existing candidate and repository manifest; there is no
competing source selection manifest.

## Recovery and asset coverage

`run-001` restores the existing eleven full-history bundles (11,609,671,470 bytes)
plus the accepted platform history. Each bundle is verified in an empty repository
and has zero external object prerequisites. Checkout uses no donor hooks,
external filters/smudge downloads, alternates, shared object stores or hardlinks.
The trusted process and descendants inherit the existing seccomp IPv4/IPv6 socket
denial; no host firewall/global Git configuration or privileges are changed.
AF_UNIX remains available in the established runner, but no proxy/service is used.

Guarded transformations reproduce the accepted Java pre-compilation tree and
GeoNode source repairs; exact accepted archives are compared to PostgreSQL,
PostGIS, QGIS, Hub and Lab source. The frontend's local project/patcher declarations
are replayed, with 2,026 retained local inputs and the frozen lock assembled in an
executable private source view. The independent nested MapStore checkout binds
the client to the product MapStore commit, preserving original gitlink history.

QGIS stays unchanged as editable Git source. Its 307 GRASS records are regenerated
from restored editable descriptions/helpers using retained original emission-order
evidence. Initial materialization reads that hash-bound historical generated
ordering evidence; subsequent bundle-chain recovery uses the retained generated
file and explicit order in the recovered composition. They are generated outputs,
not unexplained new source. The private resource view reproduces 4,282 selected
files, 88 packaging notice files and 1,130 exact palette exclusions. Source-history
custody does not reintroduce those palettes into the selected package.

Class B/vendor recovery includes selected AspectJ/XMLPull, the independently
written JSON adapter, Jackson/FastDoubleParser provenance, headless Marlin,
NO-JPEG2000 ImageIO with four exact accepted SPI resources, GeoFence/MapFish,
frontend helpers and web-ifc plus eight dependency source roots. No additional
public fork was created. Original historical JSON/JJ2000 sources remain excluded
custody material with their original terms and non-distribution status.

The 65,555 rehashed derived/bundle files total 2,492,048,193 bytes. This count mixes
editable source, generated resources, notices, source archives and retained build
inputs/binaries; it is not a count of editable-source files or newly compiled
components. Core trees, vendor sources and required selected assets are separately
classified in the receipts. Database/native/Jupyter/QGIS dependency locks link
fonts/styles/palettes, schemas, CRS resources, native bindings and build helpers;
path-pattern examples in the remote audit are discovery aids, not a second asset
manifest or semantic proof of every resource category.

The second fresh run recovers exact product commits using the original bundles
and explicit verified delta predecessor chains, plus independent nested MapStore
history and byte-verified source/assets. It does not read the original component
working checkouts. See [execution evidence](../verification/source-baseline-restore/evidence.json)
for actual completion and exact receipts, command/tool hashes and network probes.
The frozen corrected verifier passed for all eleven roots in `run-002`; separate
offline recovery of the orchestration also passed, with eight bound files compared.
The accepted platform bundle supplies original recipes; the final platform commit
and separately retained orchestration bundle supply this new recovery tooling.

## Validation, failed attempts and scope

[Validation evidence](../verification/source-baseline-restore/validation.json)
records actual commands/counts/exits. The package/schema tests are not GIS product
tests. Recovery tests use real temporary Git bundles and cover changed/corrupt
inputs, absent prerequisite commits, wrong revisions, bad patch bases/order,
missing LFS/required assets, collisions, traversal/symlink escapes, shared objects,
and incomplete/substituted receipts. Source-only probes and actual offline
recovery are distinguished from compilation/native/runtime tests.

Preserved failures include the recipe probe's temporary filesystem exhaustion,
an initial incorrect test working directory, missing old validation interpreter
and host jsonschema, a reproduced object-store symlink gap, two full-package
import errors caused by a cached unrelated `common` module, and a QGIS summary
metadata error. The source bytes and complete recovery inventory were always
correct for the latter. Its [separate correction](../verification/source-baseline-restore/qgis-receipt-correction.json)
binds the unchanged historical recipe receipt and fresh network-denied QGIS
regeneration; no old receipt was rewritten. Current verification checks the
actual generated file against accepted evidence and reports this exact correction.

The initial run's executed controller predates subsequent receipt-hardening guards;
its frozen tool bytes are retained separately. Later controller behavior is not
retroactively attributed to it. The product bundle-chain and final verification
record their own executed-tool identities.

No GIS service/database/browser fixture or whole native/runtime suite was started
for this source-only task. Existing successful exact-combination evidence remains
linked through the accepted candidate. Complete compiler/OS/base-image closure,
all transitive build/test tooling source gaps, full product builds and simulated
upstream-change immunity remain FND-08; synthetic independent repair/install/
restore remains OWN-02. These explicit later gates do not reopen FND-02.

## Resumption

Use the host namespace (`flatpak-spawn --host sh` from the IDE container). Historical
IDE and host `/tmp` locations differ; no missing old temporary venv is assumed.
Use the retained interpreter with jsonschema:
`/home/revelberry/Projects/AmbisGIS/build-worktrees/jupyter-slice/run-002/hub-env/bin/python`.
From the platform `plan/` directory, after putting its `bin/` first in PATH:

```sh
python3 tools/restore_sources.py --help
python3 tools/restore_sources.py --workspace-root /home/revelberry/Projects/AmbisGIS
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --eligibility
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --report
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

The successful `run-002` receipt is SHA256
`11bd0ba5f1662606b2d8ac604d469c2d3d02c1d73b0a1540d648856cdc2343f0`.
Exact read-only verification:

```sh
python3 tools/restore_sources.py --workspace-root /home/revelberry/Projects/AmbisGIS --verify --run run-002 --receipt-sha256 11bd0ba5f1662606b2d8ac604d469c2d3d02c1d73b0a1540d648856cdc2343f0
```
A fresh recovery uses the same
retained offline wrapper, `--recover-bundle-chain --from-run RUN --run NEW_RUN`
and that trusted receipt digest. Every output directory and network receipt must
be new; reuse or collisions are refused. Exact executed commands are retained in
the evidence index. Remote source promotion is the next owner decision, followed
by verified FND-07 acceptance before FND-08 can become ready.

For a further recovery, these are the exact commands with currently unused output names
(the tool refuses reuse if another run creates them first):

```sh
python3 ../build-support/postgis/offline_exec.py --evidence /home/revelberry/Projects/AmbisGIS/build-worktrees/source-baseline-restore/run-003-network.json -- python3 tools/restore_sources.py --workspace-root /home/revelberry/Projects/AmbisGIS --recover-bundle-chain --from-run run-002 --run run-003 --receipt-sha256 11bd0ba5f1662606b2d8ac604d469c2d3d02c1d73b0a1540d648856cdc2343f0
```

The new orchestration is retained at platform implementation commit
`e27769520a9b17a501aebfa2ac867cc150debf84`; its private bundle and verification
are separate from the original accepted-recipe platform commit `973a5ef...`.

The complete executable checkpoint is also retained at
`d006148e91b68dc04576eba9c468be7ecbb2aca1`, including the runtime custody and
acceptance metadata committed with this report. Private `checkpoint.bundle`
SHA256 `d3d48c8c03ee36f8ffc36bf91c2884b67772ef5cdfbe880fc7fb66d80a93d978`
was independently restored with full history; 20 files matched and its restored
read-only CLI inspected all eleven bundles successfully under network denial.
The earlier implementation-only orchestration bundle is preserved separately.

[Publication evidence](../verification/source-baseline-restore/publication.json)
records the separate PR Project item and narrow task reconciliation. Membership
changed from 81 to 82; FND-02 remains Merged, FND-07 is In review, and FND-08 is
unchanged. API readback preserved all existing fields/views/archive choices and
verified PR #69 in the existing `is:pr is:open` queue; no UI setup is claimed.
[Final source-fork readback](../verification/source-baseline-restore/final-source-fork-readback.json)
confirms the recorded source identities/defaults/workflow permissions are
unchanged and both planned AmbisGIS refs remain absent on all eleven forks.
