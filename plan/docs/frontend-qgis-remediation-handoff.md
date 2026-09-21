# FND-02 frontend/QGIS remediation handoff

The proposed variant is implemented and freshly tested. **FND-02 remains In
progress.** This checkpoint needs owner review; seven adoption blockers and
separate distribution obligations remain. The current owner prompt authorizes
implementation, while #65 accepted only the preceding consolidation checkpoint.

Repository `aloerch/ambisgis-platform`; branch
`fnd-02/frontend-qgis-selection-remediation`; worktree
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-remediation`.
Frozen implementation/candidate commit: `660208bd87fa508c627b223a121c299c278ea0bc`.
The later publication record and issue #3 pin the final pushed review head.
No merge or distribution has occurred.

## Owner actions and next finite decision

Review this exact candidate's bounded frontend/IFC source remediation and QGIS
resource selection. Acceptance would record those engineering results and their
remaining limitations. It would not adopt the blocked whole candidate, grant
license/distribution permission or accept F02-07/F02-08.

The remaining QGIS choice is authoritative source/permission evidence for retained
`gmt/GMT_dem1.svg`, or a separately authorized one-file exclusion with affected
catalogue/stage/native/desktop/server checks. The file is byte-identical to
excluded `td/DEM_print.svg` but carries different recorded provenance/terms.
This gates adoption and distribution; independent engineering can continue.
No additional palette was removed to force closure.

Next recommend one coordinated Java source/codec/rendering remediation batch for
AspectJ, xmlpull, JAI ImageIO, json-lib and Marlin, with one deliberate
Oracle-support/ojdbc17 decision and one affected aggregate rebuild/test plan.
No such replacement, exclusion, upgrade or WAR change was made here.

## Six findings within existing F02-06

| Finding | Baseline → proposed variant | Closing evidence / remaining condition |
|---|---|---|
| F06-FE-RECIPE | Adoption blocker → resolved for replay-02 | Original recipe unproved; newly frozen/executed source/input/tooling/output chain, native passes, current lint failure, actual served browser/restart and integrity. Original gap remains historical. |
| F06-FE-WEBIFC | Adoption blocker → distribution obligation | Exact historical main source + eight pinned sources/notices, real staged index, build/binding/asset correspondence, native tests and Node-WASM geometry/save/reopen. Distribution/generated-code/toolchain obligations remain. |
| F06-QGIS-SRC-01 | Adoption blocker → resolved for variant | 256 exact SVG omissions in 19 scopes; corrected metadata, native resource/chooser and new desktop/server evidence. |
| F06-QGIS-SRC-02 | Adoption blocker → still blocked | 138 named SVGs omitted; retained identical GMT file has unproved provenance/applicable terms. |
| F06-QGIS-SRC-03 | Adoption blocker → resolved for variant | 690 exact omissions, reference audit and new runtime evidence. |
| F06-QGIS-SRC-04 | Adoption blocker → resolved for variant | 45 exact omissions, reference audit and new runtime evidence. |

All six Java adoption blockers are unchanged. All 52 untargeted findings remain
byte-equivalent as JSON values; ColorBrewer's 265 retained palettes and exact
acknowledgement/naming obligations are unchanged. The active register has seven
adoption blockers and 46 distribution-gated findings. A finding's resolved
selection state never grants whole-product distribution permission.
The [eight-row checklist](fnd-02-completion.md) preserves all four live criteria
and eight pass conditions; F02-07 is documentary preparation, F02-08 unaccepted.

## Exact identities

| Selected record | Identity / SHA-256 |
|---|---|
| Baseline `fnd-02-tested-proposal-1`, schema 1 | `18d80d6e7520e3a16db023bbff87cd2dc20a33ba921bd4f26e49a67d71a0aace` |
| Variant `fnd-02-frontend-qgis-proposal-2`, candidate revision 2 / schema 1 | `3c59d99834b53f8778143db70f754272bce9920ca05071586d4f3629cdd625a0` |
| Frontend replay output manifest | `afe3c0d1bc6e44e94720f034788afa955ad06ae13776affb5c0024de3568136a` |
| Executed frontend `build.py` | `638629d3fc8959a461c85468ac6ad074986fcefdd41d658b91338fe9e562a2af` |
| Executed replay wrapper | `06d5fe77b14c146c187ae3581c512c7caea42e6cb2333f5ab0b4bc0e6b3a0315` |
| Frozen frontend tooling manifest | `8cd3592aa17c3bed74cd8b52ae28a7e8a21f3c99592373ec3a7afcb75eaf3634` |
| web-ifc main source archive | `8da14825b1b205766a1d762fe687749c58ca1228dc0db8273cad0f1e63461333` |
| Browser and Node WASM (identical bytes; origin ambiguity retained) | `94e1927131654a4288f8b868f33766c33979a8290d019ad3b9def7f40a0afbd6` |
| Multithreaded WASM | `797f6e0be82d95c22292894e8c9c8e8e70eb46d20b519b3f081a8df1e91208ca` |
| IFC source-stage manifest | `271d1408451a26ee6585827d701b68bcba9f10fce864a0fddc18242abf5587b3` |
| New QGIS resource manifest | `4e65c76d2af1bc811dca913d0450d4ab614f5cf14c3c9022d544796e5130a8a3` |
| Executed QGIS selection recipe | `6d3523522b4de1f7142e6895025aee19c854a623dacb67430c8eb92b98e28591` |
| QGIS runtime-07 result | `9d7be55906e6bd51da62ad1582ada3931105cf098a032931d8c81ab3d74b5898` |

Owned client revision `7ca4822125b67999c97cb4aa1faa84b8a28eee9b`, MapStore revision
`0f3518737f29f4049b131247ce981e94519d9ab0` and guarded package patches are in the
[frontend index](../verification/frontend-qgis-remediation/frontend-evidence.json).
web-ifc revision `b55d8bde10067415d4536b23c27edcc13acf217c`, all eight exact pinned
sources and 17 notices are in the [source index](../verification/frontend-qgis-remediation/webifc-source-index.json)
and [lock](../../build-support/frontend/webifc-sources.json). Owned QGIS revision
`1a4cda5f2620e7374e5926fc955a7d2d06493e15` and original source archive remain
unchanged. Source delivery is locally staged, not externally published.

QGIS selected tree is 8,110 entries versus 9,235 originally: exactly 1,129 SVGs
removed, 84 metadata files relocated unchanged, 19 catalogues corrected, notice
additions recorded, 8,003 unrelated entries unchanged, zero compilation steps.
Full audits find the one disclosed GMT alias; no other omitted-scheme references
or packaged/Qt copies. Frontend retains 1,038 static files (960 dist); six entry
files and 506 renamed filenames differ. All 13 IFC assets are unchanged.
The WAR remains `a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`.

## Actual checks and limitations

| Fresh check | Result / time |
|---|---|
| Frontend replay-02 build | Passed, 173.887 s; webpack 118.482 s, five warnings |
| Client / selected framework native | 358 passed / 152 passed; 27.947 s / 7.795 s, no skips |
| Inherited frontend lint | Five errors, exit 1; aggregate native receipt remains failed |
| New served browser-02 | Two service phases, each 109 responses and 43 hashed loaded artifacts; real red-layer render, zoom/reload/restart, no unexpected external/page/console errors; supervised 73.235 s |
| IFC native-03 | Source/dependency compile 46.024 s; six upstream encoding tests; final source/tooling integrity passes |
| Unchanged Node-WASM | Independent synthetic 2×3×4 box, one mesh / 12 triangles, finite bounds, save/reopen; no browser/MT or full 3D acceptance |
| QGIS runtime-07 | Passed, 21.176 s; 1,129 native file/model exclusions, 265 palette loads / 530 endpoints, actual chooser, vector/raster style/save/reopen, eight desktop renders, six WMS requests and restart |
| Integrated guards | 39 frontend + 71 QGIS passed; 15 shared supervision regressions separately passed |
| Package / schemas | 245 tests passed, 9.316 s, no skips; four schema/example checks passed |
| Final candidate regressions | 41 passed after review wording corrections |
| Baseline / variant integrity + report | Passed; baseline 243 records, variant 390 records / 313 JSON assertions / 80 archive members / 22,136 complete-tree entries / 11 source repositories |
| Eligibility | Exit 2 for both manifests; owner/distribution acceptance remains ungranted |

[Validation](../verification/frontend-qgis-remediation/validation.json) retains
exact commands, working directories, timings, file hashes and test scope.
After the complete suite, review changed only manifest wording; final integrity,
eligibility, report drift and all candidate regressions ran again at the frozen
commit. [Independent reviews](../verification/frontend-qgis-remediation/review.json)
found no remaining material engineering issue. Their integrity checks are not
native/runtime reruns or license approval.

All failures remain literal: original recipe recovery did not prove build-01;
replay-01 passed its runtime but failed a later frozen-tree guard after auditor
bytecode creation; replay-02 replaced it with fresh tests. IFC earlier probes
failed on wrong Node path/incomplete synthetic geometry and were corrected in
new outputs. QGIS selection-01 found the GMT alias; runtime-01 through -06 and
one preflight caught missing-file boolean, SIP ownership, implicit SVG black and
actual chooser-selection errors. None was relabeled successful. Detailed attempts
are in the [frontend](frontend-remediation-handoff.md), [IFC](webifc-remediation-handoff.md)
and [QGIS](qgis-resource-selection-handoff.md) handoffs.

All builds/probes use retained network-denied or existing loopback-supervised
mechanisms. Chromium sandboxing and origin controls remain intact; each browser/
QGIS supervisor proof includes 79 parent and 79 child kernel checks. The prior
PostgreSQL-only exception is unchanged. These are trusted-fixture controls, not
hostile-code isolation. Task processes stopped; credentials were invalidated and
private files scrubbed. Final read-only process audit finds no task service or
remaining task database PID file. Unrelated processes and user edits were untouched.

## Retained commands and resumption

All new output roots live under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-qgis-remediation/`:
`frontend/replay-02`, `frontend/native-02`, `frontend/browser-02`,
`webifc/source-stage-03`, `webifc/native-03`, `qgis/selection-03`, `qgis/runtime-07`,
`validation-01`, `validation-final` and `recovery`.
Exact execution argv and snapshots are referenced by each component index.
The [proposal](fnd-02-candidate-proposal.md) lists the supported validator commands.
Run from this checkout's `plan/` using the verified IDE Python environment
`/tmp/ambisgis-validation-venv/bin/python`; host and IDE `/tmp` are different.
The retained validation runner records that path explicitly.

Original branches, source archives, source-fork defaults, original build/staged
outputs and failed evidence remain preserved. Five unchanged backend combinations
reuse exact historical evidence; unrelated Java/database/Jupyter suites were not
rerun. No workflow, secret, automatic synchronization, upstream contact, new
repository, release or production change occurred.
