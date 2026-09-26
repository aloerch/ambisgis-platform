# FND-02 finite completion checklist

**FND-02 is owner-accepted and merged; issue #3 remains closed.** The separate
[owner decision](https://github.com/aloerch/ambisgis-platform/issues/3#issuecomment-5785944488)
(id `5785944488`, `aloerch` / user `15285626`, `2026-09-22T23:20:02Z`)
accepts the exact revision 4 selection, C1–C4, profile limits and maintenance rule,
including internal rows F02-06/F02-07/F02-08. Reviewed PR #68 head:
`7c4c6a6ddbc364e520911e06b9a97a7c10bdcfcf`; merge:
`973a5ef383687cd00143c679f832cfb006a57cf0`. The
[separate governance record](../verification/fnd-02-owner-acceptance/acceptance.json)
binds the real owner comment to immutable candidate bytes. The earlier #65/#67
consolidation and Java/GMT checkpoints remain historical evidence. Acceptance
covers the selected development candidate; it grants no distribution permission,
release, deployment, future merge or separate task acceptance. Original criteria,
eight general pass conditions and historical evidence remain unchanged.

## Unchanged live criteria

The following four lines are verbatim from issue #3; C1–C4 below are local labels.
Its importer-owned unchecked text is preserved. The separate explicit decision
accepts all four; unchecked importer seed text is not live acceptance authority.

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
**owner-accepted** = an explicit acceptance of the stated scope. All four
criteria are accepted by the separate linked owner decision; a merged checkpoint
alone did not supply that decision. All rows are owned by existing FND-02 unless a later task is named in
the separate boundary table.

| ID | Criterion | Exact remaining result | Existing evidence | Pass condition | Concrete blocker | Responsible task | Evidence state |
|---|---|---|---|---|---|---|---|
| F02-01 | C1 | Carry all eleven inspected core revisions and selected extension/profile identities into the final proposal in F02-06. | [Candidate inspection](candidate-tuple-evidence.md), [Jupyter selection](jupyter-slice-evidence.md), [Java profiles](java-profile-decisions.md), [#61 source/artifact index](../verification/geonode-role-propagation/evidence.json). | Each named component/version is derived from exact owned source; recorded gitlinks, extension choices and guarded modifications agree with the final proposal. | All eleven inspected revisions, tag/gitlink and selected guarded changes are reconciled and accepted for development; later custody/promotion remains FND-07. | FND-02 | **Owner-accepted C1 inspection/selection; separate source-branch promotion remains pending.** |
| F02-02 | C1, C3 | Bounded build/replay executed; retain these exact inputs and carry identities and limitations into F02-06. | [Fresh frontend handoff](frontend-completion-handoff.md), [commands/hashes](../verification/frontend-completion/evidence.json): three clean builds, 2,410-entry lock, 2,022 registry archives, exact retained helper/Git inputs, 960 dist files, 358 client + 152 selected framework native passes. | Audited scripts; fixed retained `@mapstore/project` and `@mapstore/patcher` inputs; complete lock; clean build and fresh retained-input replay; actual native checks/exclusions and output manifest. No byte-identical claim without comparison. | No remaining build-execution blocker. Five inherited lint errors and five webpack warnings remain recorded; bounded selection is owner-accepted and distribution rights remain gated. | FND-02 | **Demonstrated bounded build/replay; bounded #62 checkpoint owner-accepted.** Not byte-identical; exact build paths/fullhash explain differences. |
| F02-03 | C3 | Bounded public viewer executed; preserve the served build and successful restart evidence. | [Browser evidence](../verification/frontend-completion/browser-evidence-summary.json), [complete output manifest](../verification/frontend-completion/served-build-output-manifest.json), [handoff](frontend-completion-handoff.md): smoke-06 passes both service phases, 43 artifact hashes/109 responses per phase, six rendering witnesses, actual zoom/reload. | Real backend configuration/metadata and layer requests; loaded entry/chunk hashes match the output manifest; meaningful DOM/network/rendering plus pan/zoom or visibility evidence; no missing chunks, blocking console errors or unexpected external assets; same artifacts pass restart. | No remaining public-smoke execution blocker. Expected native anonymous userinfo 401 retained; broader private access/SSO remains outside this row. | FND-02 | **Demonstrated bounded public browser/backend smoke; bounded #62 checkpoint owner-accepted.** |
| F02-04 | C1, C3 | Bounded owned QGIS desktop/server candidate build at `1a4cda5f2620e7374e5926fc955a7d2d06493e15`, with exact Qt/Python/native-library inputs and basic PostGIS/CRS/rendering compatibility. | [Owned QGIS handoff](qgis-candidate-handoff.md): exact source and retained support/spatial/XML inputs, staged desktop/server artifacts, 66 C++ cases and 16 Python tests with no failures or skips; readable desktop rendering, zoom/save/reopen, six actual WMS requests, server restart, selected-library origins and cleanup. Failed attempts and explicit profile/test omissions remain retained. | Actual desktop/server artifacts and startup; known local vector/raster/CRS witness with the selected GEOS/PROJ/GDAL/PostGIS combination; relevant native checks and explicit omissions. | No remaining bounded build/native/runtime execution blocker. Owner accepted bounded #63 and final F02-06 reconciliation; later source/license obligations remain recorded. | FND-02 | **Demonstrated bounded owned desktop/server build, native tests and runtime smoke; bounded #63 checkpoint owner-accepted.** |
| F02-05 | C3 | Close only uncovered selected-component smoke links: integrated browser/GeoNode/GeoServer via F02-03; QGIS/spatial libraries via F02-04; verify embedded GeoWebCache tile response and reuse exact database, Java and Hub/Lab results. | [PostGIS](postgis-slice-evidence.md), [Jupyter](jupyter-slice-evidence.md), [Java native probes](java-compatibility-evidence.md), [controlled XML/MapFish/OAuth](java-http-auth-handoff.md), [QGIS](qgis-candidate-handoff.md), [#61](../verification/geonode-role-propagation/evidence.json), [compact final matrix](fnd-02-combination-smoke.md), [fresh tile/restart index](../verification/combination-gwc/evidence.json). | One compact final matrix names exact artifacts and actual positive smoke/restart evidence for each selected combination; fresh runs only for missing/changed links. No full publishing, policy, cartographic-parity or spatial-notebook profile claim. | Revision 4 changed-WAR matrix is freshly demonstrated; unchanged database/Jupyter/QGIS and frontend build inputs are integrity-verified reuse. The separate owner decision now accepts this bounded result. | FND-02 | **Revision 4 bounded matrix demonstrated; prior accepted checkpoints preserved.** |
| F02-06 | C1, C2, C3 | Consolidate one exact candidate source/runtime/dependency proposal, selected-file/license inventory and explicit selection-blocker dispositions, referencing existing locks rather than copying receipts. | [Active candidate](../candidates/fnd-02-candidate.json), generated [decision register](fnd-02-owner-decisions.md), [NO-JPEG2000 source/terms and guard evidence](jpeg2000-exclusion-handoff.md), and [criterion report](fnd-02-json-nojpeg2000-acceptance.md). Prior Java/GMT records remain historical. | All eleven source roots, guarded patches, runtime/tool identities, lock/artifact hashes and retained notices are linked; no floating selected input. GeoNode header/full-text discrepancy, GeoTools scope, relevant Java gaps and frontend/QGIS rights each have a specific resolution or recorded blocker and proposed owner decision. | Both variant-only findings have evidence-supported remediation; JSON closing condition is unchanged and JAI records the authorized removal alternative. No variant adoption blocker remains. Explicit owner candidate/limitations acceptance is linked above; retained distribution obligations remain. | FND-02 | **Owner-accepted revision 4 selection, source/terms findings and exact bounded aggregate.** |
| F02-07 | C4 | Bind the proposal to the existing selective maintenance rule; record the approving owner/decision when obtained. | [Chapter 11 §§6–7](11-independent-product-and-source-ownership.md), [chapter 08](08-repositories-and-licensing.md), [decision index](../DECISIONS.md), guarded Java/GeoNode repairs in #58–#61.  [Candidate maintenance binding](fnd-02-candidate-proposal.md).  [Successor maintenance binding](fnd-02-json-nojpeg2000-acceptance.md). | Proposal explicitly selects owned revisions/retained inputs; later imports/backports/independent fixes require AmbisGIS review, affected tests and a manifest change. Donor releases/disclosures are advisory; no auto-sync or unsupported indefinite freeze. | Existing rule explicitly bound to revision 4 and accepted in the linked owner decision. | FND-02 | **Owner-accepted maintenance binding and C4.** |
| F02-08 | C1–C4 | Produce the final criterion-by-criterion acceptance report, including unresolved findings and exact owner decision scope. | [Successor criterion-by-criterion report and decision scope](fnd-02-json-nojpeg2000-acceptance.md), this unchanged checklist and linked immutable evidence. | Every unchanged criterion independently evidenced; unresolved selection problems addressed as the criterion permits; explicit later owner acceptance of full FND-02. | Final report and exact-WAR/manifest/check evidence accepted by the linked separate owner decision after PR #68 merged. | FND-02 | **Owner-accepted C1–C4 and FND-02 completion; merged, not released.** |

Coverage check: C1 → F02-01/02/04/06; C2 → F02-06; C3 → F02-02–06;
C4 → F02-07; F02-08 reviews all four. No original criterion is unassigned.
This mapping is not proof of satisfaction. A discovery may amend a row only with
the affected criterion, concrete impact and reason; it is not automatically a new
milestone. F02-05 now has [demonstrated bounded matrix/cache evidence](fnd-02-combination-smoke.md).
All eight rows are accepted within their bounded FND-02 scope. Internal F02-07
and F02-08 are distinct from tasks FND-07 and FND-08. Subsequent source-custody
work belongs to FND-07; it does not reopen these completed rows.

## Current reconciliation

The bounded successor `fnd-02-json-nojpeg2000-proposal-4` retains the original
criteria, source roots, unaffected findings and selected profiles. The accepted
manifest SHA-256 remains `0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99`;
WAR SHA-256 remains `90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1`.
The [current criterion report](fnd-02-json-nojpeg2000-acceptance.md) records final
owner acceptance separately from the immutable candidate and earlier failed or
unapproved receipts. NO-ORACLE/headless-Temurin17/NO-JPEG2000 limits and all
inherited failures remain accepted limitations, not newly passing tests.
Read-only inventory/report checks reuse the exact successful combination evidence.
Eligibility still exits 2 for distribution and later obligations.

## Prior Java/GMT revision 3 checkpoint — historical

F02-06 proposes `fnd-02-java-gmt-proposal-3` (schema 1/revision 3), preserving both
original and revision 2 manifests and all original sources/artifacts. One coherent
final aggregate-02 selects complete-source variants for AspectJ, XMLPull, json-lib,
Marlin and JAI ImageIO plus explicit NO-ORACLE/headless behavior. An earlier
aggregate is retained after a file-level notice audit justified omitting unused
Marlin benchmark helper classes. QGIS adds only the recorded GMT alias exclusion:
1,130 cumulative palettes omitted; all 265 ColorBrewer palettes remain unchanged.

Fresh exact-WAR XML/JSON/proxy/weaving, actual PostgreSQL GeoFence transactions,
codec/MapFish/renderer, strict GeoNode authorization, browser, PostGISvector/mosaic
and GWC/cache/restart evidence is scoped in the [handoff](java-gmt-remediation-handoff.md).
Whole historical Java and QGIS native suites are not relabeled as reruns.
Unchanged frontend replay02/native/IFC and database/notebook results are reused
with integrity checks. Inherited frontend lint, JSON introspection, Java7 LTW and
Marlin degenerate-line limitations remain explicit; no failing test is erased.

Five targeted findings close for this selection. JSON-derived grant-chain and
JJ2000 combination-license closing conditions remain unsatisfied. C2 can accept
an accurate investigation record without adopting blocked artifacts. The finite
next action is compatible source/terms repair for those two components, then one
affected aggregate/matrix. F02-07 is documentary and F02-08 remains unaccepted.
No new milestone or later-task acceptance is created.

## Historical Java ledger baseline and current reconciliation

This entire historical subsection describes the pre-remediation #61 selection.
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
