# Implementation status — Java/GMT remediation variant

**FND-02 remains In progress.** Proposed `fnd-02-java-gmt-proposal-3` (schema 1,
revision 3) derives from verified owner-merged #66/main
`6b2e2fd7edc91746748d916d34af01f0a681e342` on
`fnd-02/java-gmt-selection-remediation`. Current prompt explicitly authorizes
implementation; owner checkpoint review, adoption and distribution remain separate.

Five of seven targeted adoption findings have variant-only remediation. JSON-derived
grant-chain and JJ2000combination terms remain blockers. Final aggregate-02 selects
six JARs from five complete-source components, explicit NO-ORACLE/headless Temurin17,
and preserved required GIS/authentication/printing/cache functionality. QGIS adds
only recordedGMTalias omission:1,130 total,265 ColorBrewer unchanged, zero compilation.
All 58 finding IDs, eleven owned roots, four criteria and eight pass conditions remain.

[Exact handoff](docs/java-gmt-remediation-handoff.md), [proposal](docs/fnd-02-candidate-proposal.md),
[decision register](docs/fnd-02-owner-decisions.md), [matrix](docs/fnd-02-combination-smoke.md)
and [checklist](docs/fnd-02-completion.md) distinguish fresh runtimes from historical
native/integrityreuse. All failed attempts and inherited frontend/JSON/Marlin/LTW
limits remain explicit. Next finite action: compatible source/terms repairs for
JSON and JPEG2000, then affected aggregate checks. F02-07 documentary binding and
F02-08 full criterion acceptance remain pending; no new milestone.

Publication/validation evidence records final exact review head, tests and liveProject
membership without promoting parent Delivery. No merge/release/distribution or
source-fork/default/workflow/secret changes.

Final validation: **251 package tests, four schemas, 383 Java guards, 39 frontend,
75 QGIS and 59 GWC guards pass**; 15 containment guards pass. Inventory validates
723 records, 50,817 complete-tree entries and 484 archive members. Integrity/report
exit 0; eligibility exit 2. Native partial failures and two adoption blockers remain
explicit. [Validation](verification/java-gmt-remediation/validation.json) binds the
exact code/contracts and independent reviews. Task-owned services are stopped.

Review [PR #67](https://github.com/aloerch/ambisgis-platform/pull/67), implementation
head `e1b960588c51beb35f83c5f1c5d137e85a0d414c`. [Project evidence](verification/java-gmt-remediation/project.json)
records exactly two authorized writes: the deduplicated PR item and Evidence link.
Live count 79→80; all 79 prior items, fields/views/archive choices and unchanged
`is:pr is:open` are preserved. Immediate list-readback failed after successful
writes; later read-only reconciliation passed without repeating mutations. Only
#67 is in the open queue; parent Delivery stays In progress. Final pushed head is
pinned in issue #3; publication documentation changes no tested selection.

# Preserved status — prior checkpoints

# Implementation status — frontend/QGIS remediation variant

**FND-02 remains In progress.** The new `fnd-02-frontend-qgis-proposal-2`
(schema 1 / candidate revision 2) is implemented and freshly tested, awaiting
owner review. #65's actual merge `b31e81ad7bfe328d5a8b3ea579eff09e6a0086e7`
accepts consolidation only; the current prompt separately authorizes implementation.
Frozen implementation/candidate commit: `660208bd87fa508c627b223a121c299c278ea0bc` on
`fnd-02/frontend-qgis-selection-remediation`.

Five targeted adoption blockers have variant-specific remediation: frozen frontend
replay with actual new native/browser/restart evidence, exact retained IFC source
and eight pinned dependencies, and three QGIS palette groups. Exactly 1,129 named
palettes are omitted with 265 ColorBrewer palettes unchanged. **Seven adoption
blockers remain:** six unchanged Java findings and QGIS SRC-02's identical GMT
palette under unresolved provenance/terms. IFC, ColorBrewer and other distribution
obligations stay explicit. Original baseline/archives/artifacts remain preserved.

Fresh checks pass 245 package tests/four schemas, 39 frontend and 71 QGIS guards,
41 final candidate regressions, 358+152 frontend native tests, browser restart,
IFC native/WASM probes and QGIS resource/desktop/server restart. Five inherited
frontend lint errors remain failed. Inventory/report pass; eligibility honestly
exits 2. Task services stopped and fixture credentials invalidated/scrubbed.

[Handoff](docs/frontend-qgis-remediation-handoff.md),
[proposal](docs/fnd-02-candidate-proposal.md),
[generated register](docs/fnd-02-owner-decisions.md) and unchanged
[eight-row checklist](docs/fnd-02-completion.md) separate evidence, owner adoption
and distribution. The finite next QGIS decision is provenance recovery or an
explicit additional one-file exclusion. Recommend one coordinated Java batch with
an Oracle-support choice and affected aggregate tests. F02-07/F02-08 remain
unaccepted; no new milestone or later-task acceptance is introduced.

Review [PR #66](https://github.com/aloerch/ambisgis-platform/pull/66). [Project evidence](verification/frontend-qgis-remediation/project.json) records exactly two authorized writes: the separate PR item and its Evidence link to #66/issue #3. Live count is 78 → 79; all 78 prior items, fields/views/archive decisions and `is:pr is:open` remain preserved. Only #66 is in the open queue. An immediate list-readback failure is retained; a later read-only reconciliation passed without replaying writes. Parent Delivery stays In progress. The final pushed review head is recorded in issue #3; later publication documentation changes no tested artifact or manifest.

# Preserved status — prior checkpoints

# Implementation status — FND-02 candidate consolidation

**F02-06 inventory consolidation is demonstrated; candidate adoption remains blocked.
FND-02 remains In progress.** Current main/owner-merged #64 is
`725d519820293f466b287d7f4cd779c36b9b7977`, reviewed head
`ee5be14d9d0d14f361dbd235dedc64b3fdb84db0`; that accepts bounded F02-05 only.
This session uses `fnd-02/candidate-selection-consolidation` in
`ambisgis-platform-candidate`. Historical open-PR claims below are dated records.

The [exact proposal](docs/fnd-02-candidate-proposal.md),
[one manifest](candidates/fnd-02-candidate.json) and generated
[owner-decision register](docs/fnd-02-owner-decisions.md) contain eleven owned roots,
ten separate profiles, seven scoped combinations and 58 findings. Read-only
validation checks hashes and complete selected output membership. It does not
reexecute native suites or certify complete transitive source/rights closure.
[Validation and handoff](verification/candidate-selection/validation.json) record
actual commands, results and manifest identity.

Twelve adoption blockers remain: AspectJ, xmlpull, JAI ImageIO, json-lib, Marlin,
shipped ojdbc17 placeholder source, web-ifc source/WASM correspondence, four
optional QGIS palette groups, and missing original frontend build-01 executed
recipe identity. Recovered exact web-ifc MPL terms, Python source-bearing wheels,
GeoNode/GeoTools file scope and notices narrow the decisions without granting
rights. All original ledger cases and technical limits remain accounted for.

The next authorized engineering prerequisite is review of the specific source /
optional-profile / palette-remediation choices; then a separately identified
variant only for approved changes, with affected builds and tests. Accepting an
accurate C2 investigation record is distinct from adopting these components or
allowing distribution. F02-07 documentary maintenance binding is prepared; no
new owner decision or F02-08 acceptance is recorded. FND-03/FND-05/FND-07/FND-08
and release gates remain unchanged. No merge, default/workflow change, binaries,
deployment, services or upstream contact occurred.

Review [PR #65](https://github.com/aloerch/ambisgis-platform/pull/65); frozen
implementation/evidence head `82b69845fd8550da612e026fed0755a5e9e00f50`.
[Project publication](verification/candidate-selection/project.json) used exactly
two authorized writes: PR membership and its Evidence link to PR #65/issue #3.
Actual count is 77 → 78; all prior represented item/field/view/archive states
were preserved, and only #65 matches unchanged `is:pr is:open`. Parent Delivery
stays In progress. Subsequent publication-documentation commits change no selected
artifact, manifest or validator behavior. Final review head is pinned in issue #3.

# Preserved status — earlier checkpoints

# Implementation status — FND-02 combination/cache checkpoint

**F02-05 bounded engineering evidence is demonstrated; [PR #64](https://github.com/aloerch/ambisgis-platform/pull/64) awaits owner checkpoint review. FND-02 remains In progress.** This slice starts from verified owner-merged
[PR #63](https://github.com/aloerch/ambisgis-platform/pull/63), merge
`56186baf19dc6ee02d4152e019d2dd96c5ec1b3e`, reviewed head
`c68f42baa8cb6d21d6b34dce07c2e4ad3ee64409`. That accepts bounded F02-04 only;
historical open-PR prose below is not a new review gate or resource-rights approval.

The [compact matrix](docs/fnd-02-combination-smoke.md) and
[index](verification/combination-gwc/evidence.json) bind six reused component
combinations and fresh embedded GeoWebCache `smoke-07`: 30 real HTTP requests,
ten decoded PNG witnesses, public and reader MISS/HIT/persistent-restart HIT,
eight anonymous/outsider protected denials, invalid-layer and positive controls.
Exact unchanged WAR, original security settings, full active security set,
catalog/styles and persistent tiles pass integrity checks. Task services/database
stop and credentials are invalidated/scrubbed; existing containment limits remain.
Six failed attempts and independent negative regressions are preserved.

Frozen tested implementation `4d58d7f17bba71bae60670fde2587f3fdbdf3307`, branch
`fnd-02/combination-gwc-smoke`. Fresh checks pass: 59 new harness, 4 runtime input,
7 configured-fixture, 15 loopback, 203 package tests and four strict schemas/examples.
Unchanged full native component suites were not repeated. No aggregate/source
repair or rebuild was necessary. The new task-local GWC security/route configuration
requires owner review before merge; #63 approval does not approve this checkpoint.

The [finite checklist](docs/fnd-02-completion.md) preserves all four criteria,
eight row IDs and pass conditions. Next is **F02-06**, exact candidate proposal
and source/license selection decisions, then F02-07 and F02-08. QGIS resource
rights, frontend notices/web-ifc/lint/nonidentical replay and distinct Java source
findings remain unchanged. No whole-task, license, release or deployment acceptance.

Project #2 publication passed: 77 items, all 76 prior items/views/archive decisions
preserved, only #64 in the open-PR queue; exactly membership and PR Evidence were
written. Parent Delivery remains In progress.

# Preserved status — earlier checkpoints

# Implementation status — FND-02 owned QGIS candidate

Current authorized engineering is **F02-04** on `fnd-02/qgis-candidate-build`,
from verified owner-merged [PR #62](https://github.com/aloerch/ambisgis-platform/pull/62)
at `8e1717ddc9ea33d28f5460c858904723aec05949`, reviewed head
`0db4c9190cee633b973a1f5ee9c87e1fa4061bf1`. **FND-02 remains In progress.**
That owner merge accepts only the bounded frontend/checklist checkpoint.

**F02-04 is demonstrated; [PR #63](https://github.com/aloerch/ambisgis-platform/pull/63) is open for owner review.** The
[QGIS handoff](docs/qgis-candidate-handoff.md) and
[compact evidence index](verification/qgis-candidate/evidence.json) bind the clean
owned QGIS desktop/server/PyQGIS build, 9,235 staged entries, 66 passing C++ cases
and 16 Python tests, readable Qt offscreen desktop canvas/zoom/save/reopen, and six
real WMS HTTP requests across a server restart. Exact loaded origins, integrity,
network controls, secret invalidation and cleanup pass. The sole inherited
source-generated metadata addition is separately reproduced and reconciled;
failed build/runtime attempts remain preserved. No physical-display, full native
suite, multiplatform or byte-identical rebuild claim is made.
The [finite checklist](docs/fnd-02-completion.md) preserves all four criteria and
eight rows. Fresh checks: 57 QGIS guards, 203 package tests, four schema/example
checks and 15 shared loopback regressions. Historical component passes are reused
only within their original scope.

The [separate dependency inventory](docs/qgis-dependency-audit.md) records Qt,
binding and QGIS rights questions; it does not grant license clearance or replace
the unchanged Java 48 structural / 12 unresolved / four partial ledger. Frontend
five lint errors, five webpack warnings, nonidentical replay and rights findings
remain F02-06. No merge, release, deployment or source-fork default change occurred.

The next finite engineering row is F02-05's missing
selected-combination smoke, including the embedded GeoWebCache tile response;
then F02-06/07/08. FND-05 publication and platform installers stay outside scope.
The following status records are preserved history.

# Preserved status — owned frontend and finite FND-02 completion

The current checkpoint is [PR #62](https://github.com/aloerch/ambisgis-platform/pull/62),
implementation `2eb07794dc9fd014e8002112bd45a95309f8cf9e`, on
`fnd-02/completion-frontend` from verified owner-merged
PR #61 / `ambisgis/main` `433cb7d8fb662b05bd1f67e8825938d0770a0d41`.
**FND-02 remains In progress.** The [finite completion checklist](docs/fnd-02-completion.md)
and [frontend handoff](docs/frontend-completion-handoff.md) are current authority.
Earlier open-PR and arbitrary Java-gap next-action prose below is dated history.

Owned client/MapStore now compile into six applications and 960 dist files.
Three fresh retained-input builds pass with Node 24.18.1/npm 11.16.0 and a complete
2,410-entry lock. Replay denies Internet sockets and uses fresh caches; absolute
build paths/fullhash references prevent byte-identical output. The real GeoNode
viewer and owned GeoServer public layer pass sandboxed Chromium load, zoom, reload
and service restart. Each browser phase verifies 43 frontend artifacts across
109 responses; all six canvas states contain the known local witness. Native
proxy routes and strict token/role/stateless guards remain intact. Services,
database and browser stopped; disposable credentials invalidated/scrubbed.

Fresh checks: **358 client + 152 selected MapStore native cases**, **22 build guards**,
**nine smoke artifact cases**, **15 loopback regressions**, **176 package tests**
and **four strict schema checks** pass without skips. Nonmutating lint has **five
inherited errors**; webpack has five recorded warnings. Failed attempts and
independent review fixes are retained in the [evidence index](verification/frontend-completion/evidence.json).
This is public browser compatibility, not SSO, full policy, publishing or release.

F02-02/03 bounded engineering is demonstrated; owner review of the new PR still
gates merging. #61's approval does not approve new changes. Frontend rights/notice
findings and the unchanged Java/GeoNode selection blockers remain F02-06. Required
source or licensing problems are not waived by recording them. FND-03/FND-05/
FND-07/FND-08 remain separate and unaccepted. No merge/release/deployment occurred.

[Project publication](verification/frontend-completion/project/README.md) passed:
75 items = 66 tasks + nine PRs; all 74 prior items/views preserved. Only #62
matches the unchanged `is:pr is:open` queue; its item has no Task ID/Delivery.

Next bounded engineering: **F02-04, owned QGIS desktop/server candidate build**,
then missing combination/GWC smoke and consolidated candidate/license proposal.
Full FND-02 acceptance requires unchanged criterion evidence and an explicit later
owner decision; no percentage or fixed prompt count is implied.

# Preserved status record — authoritative role propagation checkpoint

FND-02's source-owned GeoNode role-service implementation is frozen at
`d935fb48a7e0721b1e25f67eccfe3ed836c890fc` on `fnd-02/geonode-role-propagation`,
from verified owner-merged [PR #60](https://github.com/aloerch/ambisgis-platform/pull/60),
main `a58eff30305de4f4f24b8f5c9075672c4745aa5f`. #60's older open-PR prose is historical.
**FND-02 remains In progress; GOV-02 remains Merged.** Fresh human security review
gates [PR #61](https://github.com/aloerch/ambisgis-platform/pull/61), published at
`7ebc480fae0dedc70271ed17756387f5fefedd07`; subsequent changes are publication
documentation only. The final pushed review head is pinned in the FND-02 issue
evidence comment. See the [current handoff](docs/geonode-role-propagation-handoff.md),
[ADR 008](adrs/008-authoritative-geonode-role-service.md) and
[hash-bound evidence](verification/geonode-role-propagation/evidence.json).

Actual GeoNode membership now controls configured GeoServer/GeoFence resources
through authenticated HTTP; local XML supplies identities only and no role grants.
The fresh complete seven-profile WAR is
`a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`.
With the same valid token, group removal was first denied at **1.084476s** and
administrator demotion at **1.094112s** after native committed acknowledgment;
restoration returned access automatically. The single-process healthy test bound
was seven seconds; delayed role transport has separately measured serial-call limits.

Final execution passed **393 GeoServer HTTP requests**, **82 protocol assertions
across 156 harness-driven GeoNode HTTP requests**, **70 native Django cases**,
**39 native Java role cases**, and fresh **708 OAuth/security cases: 707 passed,
one inherited skip**. **112 GeoNode harness / 379 Java tooling / 176 plan tests / four schema checks**
passed without skips. Aggregate packaging skipped tests explicitly. Independent
review found and resolved ambiguous JSON parsing; failures remain preserved.
Both services/database stopped; disposable credentials were invalidated/scrubbed.

This does not accept full object-sharing/unified policy, browser SSO, publishing,
multi-node revocation, source/toolchain closure, FND-03/FND-07/FND-08, P1/P6 or
license/security/release gates. Java source ledger stays **48 structural / 12
unresolved / four partial**; GeoNode dependencies remain a separate inventory.
No merge, deployment or release was performed. [Publication readback](verification/geonode-role-propagation/project/README.md)
passed: **74 items = 66 tasks + eight PRs**; only #61 matches the preserved
`is:pr is:open` filter. All 73 prior items, planning fields, archive decisions and
views were preserved. FND-02 Delivery remains In progress.

## Preserved status record — GeoNode identity checkpoint


Current authorized FND-02 engineering is the source-owned GeoNode identity checkpoint in open [PR #60](https://github.com/aloerch/ambisgis-platform/pull/60), on `fnd-02/geonode-identity-integration`, based on verified owner-merged [PR #59](https://github.com/aloerch/ambisgis-platform/pull/59), merge `360b1e87b392d0e6cb8bf64fac543f75e6f27eb2`, reviewed head `c899ab0791ec87ef0a002b3953aa6a8268c4dc3e`. [PR #58](https://github.com/aloerch/ambisgis-platform/pull/58) is also merged at `b68e3d59bafb4bbf7b2007c76e5e59a25b4139e7`; dated open-review descriptions below are preserved history. **FND-02 remains In progress**; GOV-02 remains Merged.

The owned GeoNode and client backend are built from retained source in a fresh network-denied Python environment. Actual migrations and authorization-code issuance expose and reproduce inherited client-authentication, application-binding and inactive-user defects. A guarded default-false source repair adds explicit strict backend verification and exact-view middleware handling; the unchanged #59 WAR is the resource server. The [current handoff](docs/geonode-identity-handoff.md), [ADR 007](adrs/007-geonode-backend-token-verification.md) and [indexed evidence](verification/geonode-identity/evidence.json) record measured results, retained failures, artifact identities and exact resumption. A new human security review gates merging this checkpoint; the prior merge does not approve it.

Final real identity integration passed **38 native Django tests**, **176 GeoServer HTTP requests** and **48 protocol assertions**, including actual issuance, restart and measured cache limits. **96 GeoNode harness tests, 366 Java tooling tests, 176 plan tests and four schema checks passed**. The separately rerun synthetic #59 regression passed 177 HTTP requests plus its session assertion. The repaired Python backend also rebuilt from retained inputs with explicit network-denial proof. Fixture processes stopped and credentials were invalidated.

GeoNode groups and the comparison GeoServer XML roles are not automatically synchronized. Full frontend/browser SSO, unified identity/policy, publishing, source/toolchain closure, FND-07/FND-08, P1/P6 and license/security/release gates remain open. The Java ledger remains **48 structural / 12 unresolved / four partial**; the new GeoNode dependency inventory is separate. No merge, deployment or release was performed.

Project #2 now has **73 items: 66 tasks + seven PRs**. The separate #60 item carries its Evidence link without copied task planning fields; only #60 matches `is:pr is:open`. [Publication reconciliation](verification/geonode-identity/project/README.md) preserves the initially stale readback and proves all 72 prior items/views unchanged. No writes were replayed.

## Preserved status record — 20 September 2026

The configured GeoServer authorization slice is prepared in open [PR #59](https://github.com/aloerch/ambisgis-platform/pull/59), on `fnd-02/geoserver-configured-auth`, from owner-merged [PR #58](https://github.com/aloerch/ambisgis-platform/pull/58) at `b68e3d59bafb4bbf7b2007c76e5e59a25b4139e7`. Final tested implementation is `38ef3560a42af230fe75e20cc02578b12d8fcd2f`. FND-02 remains **In progress** and GOV-02 **Merged**. Project #2 now has 72 items; only #59 matches the preserved open-PR queue. Its separate PR item/Evidence were added with prior fields, archives and views preserved. Exact publication and final implementation identities are in the [current handoff](docs/geoserver-configured-auth-handoff.md).

Actual configured WFS/REST authorization and restart passed **177 HTTP requests plus one session-policy assertion** against the fresh repaired full-profile WAR. Native security/OAuth passed **707 tests / one inherited skip**, including six diagnostic and fourteen stateless regressions. Aggregate packaging succeeded with tests explicitly skipped; six repaired class definitions and the complete 368-library inventory were verified, and seven logging emissions each appeared once. **366 Java tooling tests, 176 plan tests and four strict schema checks passed.**

[ADR 006](adrs/006-configured-geoserver-authorization.md) and the [evidence index](verification/geoserver-auth/evidence.json) explain the actual failures/fixes: credential-safe diagnostics, explicit default-false stateless bearer mode, real configured role/resource authorization, cache expiry and preservation of browser context during early response commits. The identity endpoint is synthetic. The authenticated disposable PostgreSQL fixture runs outside the unchanged supervisor because native backends require denied `setsid`; application/identity HTTP remain supervised. Source dispositions stay **48 structural / 12 unresolved / four partial**. Human security review, actual GeoNode/browser SSO, canonical AmbisGIS policy, full source/license/toolchain closure, FND-07/FND-08, P1/P6 and releases remain separate. The dated records below are preserved history.

FND-01 is **Merged** after owner-approved [PR #1](https://github.com/aloerch/ambisgis-platform/pull/1), merge commit `2215a91511a53601464eef46d383cd3557cfa3a8`. All fifteen authorized public targets were created, their IDs/remotes verified and their sources cloned. `ambisgis-platform` defaults to `ambisgis/main`, initially created from that approved merge; donor references remain preserved. The eleven source-fork defaults are unchanged pending source/workflow/baseline review.

GOV-01 is **Merged** after owner-approved [PR #50](https://github.com/aloerch/ambisgis-platform/pull/50), merge commit `3e7581a06b000856ea9b27468cc415612c28b4b0`, on `ambisgis/main`. Its feature branch was `gov-01/project-importer` at reviewed commit `3c4a95415049f574caacb52528edd177ef4b69f7`. The [public Project #2](https://github.com/users/aloerch/projects/2) has all fifteen repository links, eleven custom fields, 66 task issues/items and 130 verified native dependency relations. Five planned views exist with verified names/layouts; GitHub's automatic default view is preserved. Live recovery completed after a roadmap API restriction was fixed. An unchanged reapply performed **zero transport mutations across 480 reads**, preserving all item values/archive states and sampled issue states, assignees, comments and bodies. Required owner review passed; provisioning does not complete other tasks or release product functionality.

Historical GOV-01 validation: **143 package/governance tests passed with no skips**; strict plan/dependency and all four schema/example checks passed. Independent code review found no blockers. [Actual test output](verification/project-importer-tests.txt), [schema output](verification/project-importer-schemas.txt), [public IDs and live verification](verification/project-live.json), and [review record](verification/project-importer-review.txt) are retained. These governance tests are separate from GIS acceptance tests.

FND-02 remains **In progress**. Owner-merged [PR #51](https://github.com/aloerch/ambisgis-platform/pull/51), merge `a3c2e2e696ea11bdc10c2ad202a240fbd0137f45`, accepts the bounded database development checkpoint only. Its PostgreSQL/PostGIS native and harness results remain historical evidence; database native/harness suites were not repeated during this governance preparation.

Owner `aloerch` merged [PR #53](https://github.com/aloerch/ambisgis-platform/pull/53) at `12bd2c5c88ab8573add1b483f1d53b4024649b39` on 2026-09-19T20:58:39Z. Its branch `fnd-02/jupyter-runtime` and retained runs are preserved. That bounded Jupyter checkpoint built owned Hub 6.0.1 and Lab 4.6.3 (including their frontends) from 5,510 retained hash-recorded inputs. A fresh network-denied build passed 24 top-level commands; all 329 selected native tests passed without failures/skips. Two fresh-state runtime probes passed standalone Lab and Hub/proxy/singleuser launch, real kernel execution, notebook save/reopen, authentication denial and orderly shutdown. Installed wheels and 418 Lab assets matched the owned build receipts; all observed listeners were loopback. [Evidence and preserved failures](docs/jupyter-slice-evidence.md), [machine results](verification/jupyter-slice.json), [recipes](../build-support/jupyter/README.md) and [exact handoff](docs/jupyter-slice-handoff.md) are retained. A broad linkage scan's unused musl variant is diagnosed separately; actual glibc loading succeeded. Host-toolchain/source closure, canonical baselines, licenses/security, FND-07/FND-08, P1 and P6 remain unaccepted.

GOV-02 is **Merged** following owner `aloerch`'s actual [PR #52](https://github.com/aloerch/ambisgis-platform/pull/52) merge at `fc77ab978e567ce5d55e3428d1249a3b332da09d` on 2026-09-19T21:54:27Z. Its corrections preserve the combined Delivery/Review gate filter (including Release), distinguish board columns from horizontal grouping, and withdraw the unavailable roadmap field-picker instruction. The accepted roadmap limitation and original transition receipts remain in [the reconciliation evidence](docs/project-view-reconciliation.md). Live Delivery was reconciled from In review to Merged on 2026-09-20; Evidence still links PR #52. Old Blocked/In review observations are historical. The resolution checkpoint's [original merge observation](verification/java-resolution-governance-observation.json) is retained. This is not Released or GIS product acceptance.

The original [PR #56](https://github.com/aloerch/ambisgis-platform/pull/56) correction preserved the existing [PR review queue / view 7](https://github.com/users/aloerch/projects/2/views/7), table filter `is:pr is:open`, and all six older views. It added existing PRs #54/#55 by content ID, with no Task ID, Delivery or Review gate, and exposed Repository/Evidence while retaining the original columns. Its dated **66 planned tasks + two PR items = 68** observation predates the later authorized addition of #56/#57. [Original tracking evidence](docs/pr-review-visibility.md) and its active/archived PR preservation regression remain intact; the old snapshot is not a command to reset current Project state.

The preceding FND-02 Java audit in [PR #54](https://github.com/aloerch/ambisgis-platform/pull/54) was owner-merged on 2026-09-20T20:09:12Z at `8393fc46b9b979b05faa416f5998e0159ecd1e33`. Its preserved branch `fnd-02/java-dependency-audit` retains 70 audit inputs / 902,064,509 bytes and accounts for 519 POMs plus six Maven configuration files. Its actual inventory exits 1 for one inherited malformed archetype POM; file enumeration is complete, XML interpretation and effective dependency closure are not. GeoNode's printing path reaches a moving MapFish snapshot, and exact recipe inspection exposes importer/WPS/profile and bootstrap-license questions. **28 audit/custody tests + 175 package tests and four schema/example checks passed without failures/skips** in the retained validation environment. Initial host-Python schema skips/failure are preserved. No Java build or runtime test ran. [Findings](docs/java-dependency-audit.md), [machine evidence](verification/java-dependency-audit.json), and [resumption record](docs/java-audit-handoff.md) retain exact identities, hashes, diagnostics and acceptance gaps.

The subsequent FND-02 toolchain/resolution checkpoint is in [PR #55](https://github.com/aloerch/ambisgis-platform/pull/55), owner-merged at `bb3680802d7f7d5c500180ec12e66d32d81d0aa0`, on branch `fnd-02/java-toolchain-resolution`. Temurin 17.0.20.1+1 and Maven 3.9.16 are retained with publisher sources/notices and verified installed trees. The selected 157-module core/GeoNode-extension graph completed the pinned dependency-acquisition goal with exit 0 after three preserved failed passes; 19 exact schema resource archives were inspected and retained. **140 custody/resolver tests and 175 package tests passed without failures/errors/skips**; strict plan validation and four schema/example checks passed. [Detailed evidence](docs/java-resolution-evidence.md), [machine results](verification/java-resolution.json), and [current handoff](docs/java-resolution-handoff.md) record final custody/replay results and source gaps. No Java compilation/native/runtime test ran.

The preceding review preparation selected **PR #55 only**, after verifying the actual #54 merge. The chosen review order is **#54 → #55 → #57 → #56**; #56 remains technically independent. A normal merge of current `ambisgis/main` preserved the complete original #55 source tree and remaining diff. One independent engineering finding in POM license parsing is corrected: encoded DTD/entity declarations must be refused before parsing. That review passed **143 Java tooling tests, 175 package tests and all four schemas**; the full actual retained inventory still reports 64 gaps with unchanged semantic results. The [actionable review report](docs/pr-55-review.md) records exact ancestry, tested source identity, checks, remaining limitations and the separate owner decision. That preparation did not merge a PR or enable auto-merge; owner `aloerch` subsequently merged #55 at `bb3680802d7f7d5c500180ec12e66d32d81d0aa0` on 2026-09-20T20:50:29Z from reviewed head `8eeb408f296b7c6152fae2ef5edef65161f674ac`. Source recovery/native work in #57 and governance implementation in #56 remain separate.

The FND-02 source/compatibility slice in [PR #57](https://github.com/aloerch/ambisgis-platform/pull/57) was owner-merged at `8bf1217c8c078c26558da4b3318feda07a9c4ce1` on 2026-09-20T21:32:22Z, on `fnd-02/java-source-compatibility`, originally based on PR #55 head `9e1b2e1bca26d00b200a39f58a4a0890d43fca98`, now normally reconciled with its actual owner merge `bb3680802d7f7d5c500180ec12e66d32d81d0aa0`. The 64-gap supplement now accounts structurally for 48 artifacts; **12 unresolved and four partial cases remain**, with no reproducible-source or legal approval implied. Actual owned/component compilation and native probes include GeoTools referencing (667 passed/eight skips), XML resolver (12 passed), GeoFence (62 passed including real PostgreSQL/PostGIS), Huldra (19 passed) and recovered JavaCSV (105 passed with explicit CRLF; the same 16 Linux-default failures reproduce against the original binary). Broader XML/MapFish socket-fixture failures remained open at that checkpoint. Importer compiled all 89 selected reactor modules and passed 112 native tests, including four GDAL transformations, with six Oracle/SQL Server fixture skips. Historical checkpoint checks: **212 integrated Java tooling tests, 175 package tests and all four schemas passed without failures/skips.** Failed runs and retained custody are in the [new handoff](docs/java-source-closure-handoff.md), [compatibility evidence](docs/java-compatibility-evidence.md) and [ADR 004](adrs/004-java-source-and-compatibility-probes.md). Historical database/Jupyter native suites were not rerun; new GeoFence tests use verified prior owned database artifacts in a fresh stopped private cluster.

The separately authorized Project correction added only existing PRs #56/#57 and their parent Evidence links. **66 planned tasks + four PR items =70 items** were retained unarchived at the #57 review; its then-current saved `is:pr is:open` membership was #57/#56 after the owner merged #55. That read-only audit preserved all 70 identities/archive states and all task fields; #55's built-in Status is now Done. No prior mutation was replayed. All task fields, archive states and views compare unchanged; FND-02 remains In progress. Full importer execution, task transitions and workflow/secret changes did not occur. [Prior correction receipts](verification/pr55-review/project/README.md) and [retained #57 readback](verification/pr57-review/project/README.md) preserve the actual observations.

The preceding review preparation selected **#57 only**, normally integrated and explicitly retargeted to actual main. Independent engineering review corrected encoded POM declarations in the source supplement and a compatibility receipt that could remain successful after a source-hash error. That preparation passed **218 Java tooling tests, 175 package tests, all four schemas and 12 selected native XML resolver tests**. The actual 64-artifact source report is byte-identical after the repair and still exits 2 for 12 unresolved/four partial cases. [The selected review report](docs/pr-57-review.md) records exact ancestry, code identity, checks, omissions and acceptance boundaries. Review order remains **#54 → #55 → #57 → #56**. #54, #55 and #57 are now actually owner-merged. The #57 merge has the exact reviewed tree `7bb7ce83f8bfc900a707de8524b2efafb4a74f16`. These retained tests were not repeated as native tests for #56; no new engineering acceptance is implied.

Historical #56 preparation readback at 2026-09-20T21:39:28Z confirms **66 planned tasks + four PR items = 70**, all unarchived; saved `is:pr is:open` matches **#56 only**. All represented task fields, item identities/archive states, seven views, 24 fields and 15 repository links match the immutable #57 snapshot. Only #57's built-in Status changed Todo to Done after its owner merge. FND-02 remains In progress; GOV-02 remains Merged. This run made zero Project mutations. [Current review/handoff](docs/pr-56-review.md) and [compact readback](verification/pr56-review/project/README.md) distinguish fresh checks from retained native results. The integrated implementation passed **218 Java tooling tests, 176 package tests and all four strict schemas**, with no failures/errors/skips.

The preceding run selected **Phase A: prepare #56 only**, on `gov-02/pr-review-visibility`. Owner `aloerch` subsequently merged #56 at `a9ec191658be027b40118fd35e145729202fe55d`, with the exact reviewed tree. The current authorized run selects **Phase B** from that verified merge on fresh branch `fnd-02/java-http-auth-compatibility`; no Phase A work remains. The Phase B HTTP/XML/MapFish and combined logging/OAuth engineering, retained failures, relevant source observations and separate acceptance gates are documented in the [current handoff](docs/java-http-auth-handoff.md) and [ADR 005](adrs/005-controlled-java-http-and-auth-probes.md). Schema rights/repackaging, rendering, other capability choices, bootstrap assets and host/toolchain/native closure remain explicit gates before full Java tuple acceptance. Client/MapStore and QGIS follow the dependency graph. No full tuple, canonical source baseline, license/security, FND-07/FND-08, P1 or P6 acceptance is implied. No inherited workflow, source-fork default, secret, deployment or release changed. Initial JSON statuses remain seeds, never progress-reset commands.
