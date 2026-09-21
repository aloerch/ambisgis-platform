# F06-FE-RECIPE proposed variant remediation

The 2026-09-21 owner prompt explicitly authorizes this distinct replay variant.
PR #65's merge `b31e81ad7bfe328d5a8b3ea579eff09e6a0086e7` accepts the earlier
consolidation only. Original build-01 orchestration identity remains unrecovered:
its immutable receipt binds only input identity, command receipts omit orchestration
bytes, its console records only success.json, and it has no recipe snapshot.
The acquisition preparer, later build-02/03 snapshots and later Git commit cannot
prove original execution. Original artifacts and receipts are preserved.

The new [replay wrapper](../../build-support/frontend/replay.py) physically executes
frozen tooling and rejects post-command changes. Independent review of code commit
`b2ea047606401fc02c2d50e352027211a8d5a2ed` found no material blocker. The exact
execution freeze is commit `7e6e2b1d92721f44d4066cac2ed807bbd84df834` (documentation added; code unchanged), with
retained snapshot manifest SHA-256
`8cd3592aa17c3bed74cd8b52ae28a7e8a21f3c99592373ec3a7afcb75eaf3634`.
The executed build recipe is unchanged at SHA-256
`638629d3fc8959a461c85468ac6ad074986fcefdd41d658b91338fe9e562a2af`;
wrapper SHA-256 is `06d5fe77b14c146c187ae3581c512c7caea42e6cb2333f5ab0b4bc0e6b3a0315`.
[Replay instructions](../../build-support/frontend/replay.md) preserve the original
input/lock guards and external-network-denied installation/build path.

Selected retained root:
`/home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-qgis-remediation/frontend`.
Use **replay-02**, **native-02**, **browser-02** and **final-integrity.json**.
Owned client `7ca4822125b67999c97cb4aa1faa84b8a28eee9b`, MapStore
`0f3518737f29f4049b131247ce981e94519d9ab0`, complete npm lock, all retained inputs,
Node 24.18.1/npm 11.16.0 and the two guarded local-archive substitutions are
unchanged. Actual source-package patches are retained and hashed.

The build passed in **173.887 seconds** (webpack **118.482 seconds**), installing
2,403 packages with disabled registry hooks and the reviewed MapStore hook.
All seven network-proof receipts pass their four actual kernel probes. It produces
1,038 staged files, including 960 compiled dist files (595 JS, 32 CSS) and 35
notice-named files. The notice count is a file-selection observation, not rights
clearance. Complete output manifest SHA-256:
`afe3c0d1bc6e44e94720f034788afa955ad06ae13776affb5c0024de3568136a`;
served `gn-map.js`: `1a5e45ed592b267fd9690b3cc000d93084688328d2ac08f50267385639b1616a`.

Raw output differs: six application entry files changed, 506 filenames moved from
webpack fullhash `337024cfcd227802` to `7f9758b868437b2a`, and 526 paths and bytes
are unchanged. Of the renamed files, 479 retain identical bytes. Diagnostic-only
replacement of the two exact build roots and observed fullhashes leaves no further
differences; raw outputs were never rewritten. All **13 IFC-named staged assets**,
including API and WASM families, are byte-identical. IFC source/notices are a
separate F06-FE-WEBIFC record; this replay adds no version, binary or loader change.

Actual client tests: **358 passed**, no skips, **27.947 seconds**. The seven-file
framework selection: **152 passed**, no skips, **7.795 seconds**. Nonmutating lint
still fails with **five inherited errors**, **3.174 seconds**; the aggregate native
runner correctly exits 1. No auto-fix or warning suppression. The build still has
five inherited webpack warnings. Build/replay **26**, staging/browser harness **9**
and directly reused loopback **15** guard tests pass. Package checks belong to the
integrated checkpoint and are not GIS runtime acceptance.

The actual owned backend serves the new artifact tree; all 1,038 staged files and
all loaded frontend chunks match the new manifest. Initial and restarted phases
each have **109 responses**, **43 distinct verified frontend assets** and three
render states (load, wheel zoom, reload), each with **556 red witness pixels**.
WMS BBOX span halves on zoom. Unexpected external requests, failed requests,
page errors and blocking console errors are zero. Anonymous native userinfo 401
remains an explicit expected denial. The unchanged WAR is
`a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`;
owned GeoNode/client wheels verify before and after. No Java/WAR modification.
The supervised backend phase lasts **73.235 seconds**, with 79 parent and 79
exec-child probes passing, zero UDP packets and closed broker sockets. Chromium
153.0.8010.12 keeps its sandbox and exact task-origin controls. PostgreSQL alone
retains the documented SCRAM/loopback exception. Both browsers/services/database
stop, stored credentials are invalidated, disposable secrets are scrubbed, and
final host process scan finds no selected task processes. External final hashing
confirms the executed frozen tooling and new static tree are unchanged.

Preserved failed aggregate: replay-01's build, 510 native assertions and browser
phases succeeded, with the same five lint failures. A later audit imported frozen
Python without `-B`, generating one bytecode file; the immutable-tree guard failed.
That attempt remains failed at aggregate validation. Fresh replay-02 and fresh
native/browser-02 were executed; no old smoke result was transferred to new bytes.
A late browser-01 timing observer found the process already exited; no timing was
invented. The final reported timing comes from the supervisor receipt.

[Compact evidence](../verification/frontend-qgis-remediation/frontend-evidence.json)
and [complete new output manifest](../verification/frontend-qgis-remediation/frontend-output-manifest.json)
bind commands, source patches, tools, all outputs, raw differences, native/browser
receipts, preserved failures and cleanup. F06-FE-RECIPE is remediated **for this
proposed variant only**. Explicit owner adoption, distribution obligations, IFC
source disposition and all other findings remain separate. No full 3D, private
browser, SSO, accessibility, publishing or whole-product acceptance is inferred.
