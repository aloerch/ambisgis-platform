# FND-02 finite completion checklist

**FND-02 remains In progress.** This is the authoritative execution checklist for
[issue #3](https://github.com/aloerch/ambisgis-platform/issues/3). Current main and
owner-merged #64 were verified at `725d519820293f466b287d7f4cd779c36b9b7977`,
reviewed head `ee5be14d9d0d14f361dbd235dedc64b3fdb84db0`. This accepts bounded
F02-05 only; #63/#62 remain bounded F02-04/F02-02–03 acceptance. Dated open-PR
statements remain historical records, not new approval obligations. The
[F02-06 proposal](fnd-02-candidate-proposal.md) and its generated decision register
separate inventory evidence, blocked candidate selection and owner acceptance.
Historical receipts retain their original artifact/test scope. No criterion,
row ID, pass condition, dependency or release gate changes.

## Unchanged live criteria

The following four lines are verbatim from issue #3; C1–C4 below are local labels.

- [ ] Inspect actual GeoNode, MapStore/client, GeoServer/extensions, QGIS and Jupyter versions.
- [ ] Resolve or record blocking GeoNode/license scope issues; preserve originals.
- [ ] Build and smoke-test selected tuple; no floating latest tags.
- [ ] Upstream releases are initial acquisition candidates only; later component changes follow AmbisGIS release authority.

The deliverable remains **“Exact source/image/runtime lock proposal; license
inventory; upstream patch policy”**, with R20 / T-LOCK-01 and License/Brand review.
“Record” in C2 permits an explicit blocking finding; it does not confer legal
clearance, make unusable required source viable, or authorize distribution.

## Finite work and evidence

States describe evidence: **demonstrated** = the named bounded result ran;
**partial** = some required evidence exists; **missing** = the named result has
no retained pass; **recorded decision** = a documented choice, not execution;
**owner-accepted** = an explicit acceptance of the stated scope. None of the four
whole criteria has owner-accepted evidence here. A merged checkpoint is not that
decision. All rows are owned by existing FND-02 unless a later task is named in
the separate boundary table.

| ID | Criterion | Exact remaining result | Existing evidence | Pass condition | Concrete blocker | Responsible task | Evidence state |
|---|---|---|---|---|---|---|---|
| F02-01 | C1 | Carry all eleven inspected core revisions and selected extension/profile identities into the final proposal in F02-06. | [Candidate inspection](candidate-tuple-evidence.md), [Jupyter selection](jupyter-slice-evidence.md), [Java profiles](java-profile-decisions.md), [#61 source/artifact index](../verification/geonode-role-propagation/evidence.json). | Each named component/version is derived from exact owned source; recorded gitlinks, extension choices and guarded modifications agree with the final proposal. | All eleven inspected revisions, tag/gitlink and selected guarded changes are now reconciled in the proposal; adoption remains subject to its explicit blockers. | FND-02 | **Demonstrated inspection and completed inventory reconciliation; no baseline adoption.** |
| F02-02 | C1, C3 | Bounded build/replay executed; retain these exact inputs and carry identities and limitations into F02-06. | [Fresh frontend handoff](frontend-completion-handoff.md), [commands/hashes](../verification/frontend-completion/evidence.json): three clean builds, 2,410-entry lock, 2,022 registry archives, exact retained helper/Git inputs, 960 dist files, 358 client + 152 selected framework native passes. | Audited scripts; fixed retained `@mapstore/project` and `@mapstore/patcher` inputs; complete lock; clean build and fresh retained-input replay; actual native checks/exclusions and output manifest. No byte-identical claim without comparison. | No remaining build-execution blocker. Five inherited lint errors and five webpack warnings are recorded; selection/rights decisions remain F02-06. | FND-02 | **Demonstrated bounded build/replay; bounded #62 checkpoint owner-accepted.** Not byte-identical; exact build paths/fullhash explain differences. |
| F02-03 | C3 | Bounded public viewer executed; preserve the served build and successful restart evidence. | [Browser evidence](../verification/frontend-completion/browser-evidence-summary.json), [complete output manifest](../verification/frontend-completion/served-build-output-manifest.json), [handoff](frontend-completion-handoff.md): smoke-06 passes both service phases, 43 artifact hashes/109 responses per phase, six rendering witnesses, actual zoom/reload. | Real backend configuration/metadata and layer requests; loaded entry/chunk hashes match the output manifest; meaningful DOM/network/rendering plus pan/zoom or visibility evidence; no missing chunks, blocking console errors or unexpected external assets; same artifacts pass restart. | No remaining public-smoke execution blocker. Expected native anonymous userinfo 401 retained; broader private access/SSO remains outside this row. | FND-02 | **Demonstrated bounded public browser/backend smoke; bounded #62 checkpoint owner-accepted.** |
| F02-04 | C1, C3 | Bounded owned QGIS desktop/server candidate build at `1a4cda5f2620e7374e5926fc955a7d2d06493e15`, with exact Qt/Python/native-library inputs and basic PostGIS/CRS/rendering compatibility. | [Owned QGIS handoff](qgis-candidate-handoff.md): exact source and retained support/spatial/XML inputs, staged desktop/server artifacts, 66 C++ cases and 16 Python tests with no failures or skips; readable desktop rendering, zoom/save/reopen, six actual WMS requests, server restart, selected-library origins and cleanup. Failed attempts and explicit profile/test omissions remain retained. | Actual desktop/server artifacts and startup; known local vector/raster/CRS witness with the selected GEOS/PROJ/GDAL/PostGIS combination; relevant native checks and explicit omissions. | No remaining bounded build/native/runtime execution blocker. Owner accepted bounded #63; selected-input reconciliation and source/license findings remain F02-06. | FND-02 | **Demonstrated bounded owned desktop/server build, native tests and runtime smoke; bounded #63 checkpoint owner-accepted.** |
| F02-05 | C3 | Close only uncovered selected-component smoke links: integrated browser/GeoNode/GeoServer via F02-03; QGIS/spatial libraries via F02-04; verify embedded GeoWebCache tile response and reuse exact database, Java and Hub/Lab results. | [PostGIS](postgis-slice-evidence.md), [Jupyter](jupyter-slice-evidence.md), [Java native probes](java-compatibility-evidence.md), [controlled XML/MapFish/OAuth](java-http-auth-handoff.md), [QGIS](qgis-candidate-handoff.md), [#61](../verification/geonode-role-propagation/evidence.json), [compact final matrix](fnd-02-combination-smoke.md), [fresh tile/restart index](../verification/combination-gwc/evidence.json). | One compact final matrix names exact artifacts and actual positive smoke/restart evidence for each selected combination; fresh runs only for missing/changed links. No full publishing, policy, cartographic-parity or spatial-notebook profile claim. | No remaining bounded smoke execution gap: actual embedded WMTS public/reader MISS → HIT → persistent-restart HIT, scoped protected-tile denials, invalid/positive controls, integrity and cleanup all pass. Owner-merged #64 accepts this bounded checkpoint only. | FND-02 | **Demonstrated bounded combination matrix and embedded cache smoke; bounded #64 checkpoint owner-accepted.** Six combinations reuse exact historical profiles; no simultaneous whole-tuple claim. |
| F02-06 | C1, C2, C3 | Consolidate one exact candidate source/runtime/dependency proposal, selected-file/license inventory and explicit selection-blocker dispositions, referencing existing locks rather than copying receipts. | [Authoritative manifest](../candidates/fnd-02-candidate.json), [proposal/validator](fnd-02-candidate-proposal.md), generated [58-finding decision register](fnd-02-owner-decisions.md), [real validation](../verification/candidate-selection/validation.json). | All eleven source roots, guarded patches, runtime/tool identities, lock/artifact hashes and retained notices are linked; no floating selected input. GeoNode header/full-text discrepancy, GeoTools scope, relevant Java gaps and frontend/QGIS rights each have a specific resolution or recorded blocker and proposed owner decision. | Twelve explicit adoption blockers: six Java source/profile findings (five prior plus shipped ojdbc17 placeholder source), web-ifc source/WASM correspondence, four QGIS optional-palette groups, and original frontend build-01 executed-recipe identity. Exact actions/alternatives and distribution-only obligations are in the register. | FND-02 | **Fully populated inventory; structural/integrity validation demonstrated. Candidate selection blocked; new owner review/acceptance pending.** |
| F02-07 | C4 | Bind the proposal to the existing selective maintenance rule; record the approving owner/decision when obtained. | [Chapter 11 §§6–7](11-independent-product-and-source-ownership.md), [chapter 08](08-repositories-and-licensing.md), [decision index](../DECISIONS.md), guarded Java/GeoNode repairs in #58–#61.  [Candidate maintenance binding](fnd-02-candidate-proposal.md). | Proposal explicitly selects owned revisions/retained inputs; later imports/backports/independent fixes require AmbisGIS review, affected tests and a manifest change. Donor releases/disclosures are advisory; no auto-sync or unsupported indefinite freeze. | Documentary binding prepared; no new approving owner decision recorded. | FND-02 | **Documentary binding prepared; owner policy/criterion acceptance pending.** |
| F02-08 | C1–C4 | Produce the final criterion-by-criterion acceptance report, including unresolved findings and exact owner decision scope. | This checklist and its linked component receipts; owner merges are historical checkpoint evidence only. | Every unchanged criterion independently evidenced; unresolved selection problems addressed as the criterion permits; explicit later owner acceptance of full FND-02. | Explicit C1–C4 review and owner decisions remain: accept the accurate C2 investigation record within its permitted scope, resolve adoption blockers before adopting a component/variant, and approve final maintenance/criterion acceptance. No later task is accepted. | FND-02 | **Missing.** Keep In progress in this session. |

Coverage check: C1 → F02-01/02/04/06; C2 → F02-06; C3 → F02-02–06;
C4 → F02-07; F02-08 reviews all four. No original criterion is unassigned.
This mapping is not proof of satisfaction. A discovery may amend a row only with
the affected criterion, concrete impact and reason; it is not automatically a new
milestone. F02-05 now has [demonstrated bounded matrix/cache evidence](fnd-02-combination-smoke.md).
The next finite row is **F02-06 selected-input/license reconciliation and owner
decisions**, then F02-07 maintenance-policy binding and F02-08 final acceptance.

## This session

F02-06 consolidates the exact tested combinations into one validated proposal.
It reuses accepted bounded F02-02–05 evidence without new smoke runs. The register
covers all original Java 12 unresolved/four partial cases (48 structural cases
stay structural), selected GeoNode/GeoTools scope, ten GeoNode absent-sdist
records, Jupyter's distinct 146-sdist inventory, all 18 frontend declaration gaps,
actual generated/native/WASM membership, QGIS resource/support terms and recorded
technical/containment limitations. Exact historical evidence resolves some gaps;
12 adoption blockers remain concrete decisions, not a vague license backlog.

C2 permits accepting an accurate record of blocking findings. That is distinct
from adopting the affected selection or distributing it. F02-06 inventory coverage
is complete for this finite pass; candidate adoption is blocked and owner acceptance
is pending. No raw source, binary, palette or notice was changed. The proposed
remediation batch requires the named choices before variant implementation and
affected tests; F02-07's documentary binding is prepared, F02-08 is not satisfied.
No new smoke milestone or later-task acceptance has been introduced.

## Historical Java ledger baseline and current reconciliation

The current [decision register](fnd-02-owner-decisions.md) supersedes this dated
selection analysis where new exact-file evidence resolves or expands a finding;
the original ledger remains unchanged. In particular, absence of old ojdbc14 did
not establish absence of a different Oracle driver.

The [64-coordinate report](../verification/java-source-provenance.json) remains
**48 structural / 12 unresolved / four partial**. Structural mappings, embedded
sources and generation inputs are not 48 reproducible source builds. A read-only
comparison with the hash-verified #61 WAR
`a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`
enumerated all 369 `WEB-INF/lib` jars and compared the 16 partial/unresolved
entries by filename and SHA-256. The five present entries are exact hash matches. Absence means absent as that
standalone jar from this WAR, not globally unused or free of shaded classes.

| Ledger entries (all 12 unresolved and four partial accounted for) | Actual relevance and outstanding result |
|---|---|
| Unresolved `net.sf.json-lib:json-lib:2.4.2-geoserver`; `xmlpull:xmlpull:1.1.3.1` | Both ship in this WAR; json-lib is a declared GeoServer core/WFS/OAuth input. Exact corresponding source is not retained. **F02-06 selection/source blockers**, not blanket later-task deferrals. Resolve source/rights or propose a tested capability-preserving change. |
| Unresolved `javax.media:jai_imageio:1.1` | Ships in WAR; declared MapFish codec input. Original source/native/redistribution evidence is missing. **F02-06 selection blocker** for the selected printing profile; a successor source tag is not exact provenance. |
| Partial `org.aspectj:aspectjweaver:1.5.4`; `org.marlin:marlin:0.9.4.8` | Both ship in WAR. AspectJ lacks five embedded BEA source classes; Marlin lacks OGLRenderQueue/QueueFlusher correspondence. **F02-06 selection/source-rights blockers**; passing GeoFence/rendering tests cannot close them. |
| Unresolved `com.oracle:ojdbc14:10.2.0.3.0`; `opendap:opendap:2.1` | Absent from this WAR; respectively provided `gt-imagemosaic` and compile `gt-netcdf` declarations. Still resolve required capability/build-path relevance and source/rights in **F02-06**; no silent driver removal or assertion they are unused. If required for the selected tuple, unusable source/build/license status blocks selection. |
| Unresolved `com.google.code.typica:typica:1.3` | Absent from WAR; retained `spring-ldap-test` declaration, not observed runtime proof. Original ZIP is binary/docs only. Preserve exact source gap and trace selected test/build use in FND-08; elevate to F02-06 if it prevents a required candidate build/test or invalidates selection. |
| Unresolved `classworlds:classworlds:1.1-alpha-2`; `dom4j:dom4j:1.1`; `geronimo-spec:geronimo-spec-jta:1.0.1B-rc4`; `org.netbeans.lib:cvsclient:20060125`; `org.sonatype.sisu:sisu-inject-plexus:2.1.1`; `plexus:plexus-utils:1.0.3` | Absent from WAR; ledger records actual Maven plugin acquisition/POM paths. Exact source correspondence remains missing (including cvsclient's HTML response masquerading as an archive). FND-08 must determine required build-tool closure; any necessary unbuildable/restricted input remains an F02-06 selection blocker. These are not six new frontend milestones. |
| Partial `commons-codec:commons-codec:1.2`; `net.sourceforge.groboutils:groboutils-core:5` | Absent from WAR. Codec's plugin/acquisition source misses SoundexUtils; GroboUtils is declared GeoTools test scope with only 388/1,006 classes mapped. Preserve FND-08 build/test-source closure and elevate actual candidate-blocking defects to F02-06. No complete source claim. |

No entry currently demonstrates that the selected frontend cannot compile or its
public-layer smoke cannot run. That permits bounded engineering to continue; it
does not approve the tuple or permit distribution. Recording these limitations
requires an explicit appropriate owner decision before acceptance of a proposed
limited checkpoint; no decision can substitute for required viable source or
license rights. Rebuilding unrelated Java entries is outside this session.

## Evidence retained for later tasks

The live issues below were inspected with their current unchanged criteria;
all remain open. This table adds references, not acceptance or changed edges.

| Existing task | Reusable evidence | Still-missing task acceptance |
|---|---|---|
| [FND-03](https://github.com/aloerch/ambisgis-platform/issues/4) | #60/#61 real identity/role, negative and measured revocation [evidence](geonode-role-propagation-handoff.md). | Public/private/group access and revocation through the actual gateway **and** engine; no duplicate policy authority/raw admin bypass. Browser SSO, complete sharing and multi-node behavior are unproved. Do not expand this frontend session into them. |
| [FND-05](https://github.com/aloerch/ambisgis-qgis-plugin/issues/1) | [QGIS candidate build/native/basic desktop/server smoke](qgis-candidate-handoff.md); Java rendering/printing probes; demonstrated F02-03 public-layer result. | Representative desktop style packaging/rendering **and authorization**, unsupported styles/providers and hooks, G3W/Lizmap comparison and ADR. A basic QGIS build or browser map is insufficient. |
| [FND-07](https://github.com/aloerch/ambisgis-platform/issues/6) | Eleven full-history owned bundles and notices in [source acquisition](source-acquisition-evidence.md); later candidate receipts. | Reviewed independently maintained product baselines/branches, all required submodule/LFS/build assets, explicit remaining nulls and original rights; acquisition references are not approved baselines. |
| [FND-08](https://github.com/aloerch/ambisgis-platform/issues/7) | Retained-input database/Jupyter/Java/GeoNode results, [bounded QGIS candidate](qgis-candidate-handoff.md) and [demonstrated frontend replay](frontend-completion-handoff.md). | Complete initial-spine build/input inventory including fonts/styles/CRS/toolchain/base-image dependencies; simulated upstream-change immunity; all relevant source/build closure. No automatic acceptance from one offline replay. Full disconnected repair/recovery remains OWN-02 and maintenance exercise SEC-04. |

The earlier candidate handoff mixed selection smoke with full publication,
branch correctness and CRS/style/font parity. This checklist interprets those
execution boundaries through the unchanged FND-03/FND-05/FND-07/FND-08 and later
product tasks; it does not amend their specifications. Any proposed interpretation
that would permit a required core component with unusable source, an unbuildable
required input or invalid licensing must instead be presented as a specification/
selection conflict for explicit review. Independent frontend engineering can proceed.
