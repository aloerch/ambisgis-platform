# Scoped MVP requirements, implementation and test matrix

Checkpoint: **2026-10-02**, platform repository `aloerch/ambisgis-platform`
(ID `1376927351`), merged baseline
`5213f31cd51aed5230d7bd550cc03662bcfb566f` (PR #71; reviewed head
`0f59f44be6c317759ff67ade73bcd2761b26df20`). This is a delivery index,
not product acceptance. No test was rerun to prepare this matrix.

All **R01–R24** are required for the first complete scoped release through P7.
The requirement text, test IDs and complete task mappings below are copied from
[requirements.json](../requirements.json) and [backlog.json](../backlog.json).
Each mapped task retains **all** of its original deliverables, acceptance criteria,
tests and dependencies in that backlog; this index does not replace or narrow them.
[Chapter 09](09-roadmap-and-acceptance.md) and component chapters retain additional
journey, platform and negative-case requirements. P1 remains a technical alpha.

Existing evidence references are defined after the matrix. Historical passing
component probes are reusable only after verifying unchanged inputs and their
recorded scope; they are not passes for the product tests in the third column.
“Open” means acceptance remains unproven, including where useful component code
already exists. Package/schema checks are necessary and separate from GIS tests.

| ID — unchanged requirement | Implementation tasks (unchanged mapping) | Required test IDs | Merged implementation/evidence and remaining acceptance |
|---|---|---|---|
| **R01** — One supported install and simple service administration | PLT-01, SRV-01, PUB-01, SRV-02, OPS-01, REL-02 | T-INSTALL-01, T-SRV-01 | No product installer/service manager. E1 supplies component builds only; clean install/sign-in/publish/query/share/revoke/restart remains open. |
| **R02** — Native REST, selected OGC and explicit ArcGIS C1 compatibility | FND-06, API-01, API-02, API-03, QA-01, REL-02 | T-API-01, T-QUERY-01, T-COMPAT-C1 | E1 has bounded inherited service probes. Native product API, selected OGC and named C1/client contract suites remain open; schemas are proposals. |
| **R03** — One integrated authoritative metadata workflow | SRV-03, REL-02 | T-META-01 | No accepted canonical metadata implementation or T-META-01 journey; inherited forms do not establish one product authority. |
| **R04** — Typed managed schema, stable identity, domains and relationships | DB-01, DB-02, REL-02 | T-DB-SCHEMA, T-DB-IDENTITY | E1 includes owned PostgreSQL/PostGIS builds and native tests. Managed typed schema, stable IDs, domains and relationships remain open. |
| **R05** — Service-only atomic edits with audit and idempotency | API-04, DB-04, DB-08, QGIS-05, REL-02 | T-EDIT-01, T-EDIT-RETRY | No accepted managed edit implementation; real atomicity, audit, replay/idempotency, authorization and concurrency tests remain open. |
| **R06** — Isolated named branches and retained history | FND-04, DB-03, DB-04, DB-07, DB-08, UX-02, QGIS-05, REL-02 | T-VERSION-SNAPSHOT, T-VERSION-ORACLE | E6 supplies an accepted typed two-layer database prototype with 25 real DB tests and 35 seeded reference comparisons. Product history, quotas, full schema/edit APIs and restored-branch acceptance remain open. |
| **R07** — Reconcile, explicit conflict resolution, accept and atomic post | FND-04, DB-05, DB-06, DB-07, DB-08, UX-02, QGIS-05, OPS-02, REL-02 | T-VERSION-RACE, T-VERSION-POST, T-VERSION-RECOVERY | E6 supplies the accepted reconcile/resolve/accept/post prototype, real concurrent post, stale-head and backend-termination rollback tests. Complete API authorization, supported migrations and restored-branch product journeys remain open. |
| **R08** — Unified catalog, roles and modern accessible portal | FND-03, PLT-02, UX-01, WEB-04, QA-02, REL-02 | T-PORTAL-01, T-A11Y-01 | E6 adds the accepted native-catalog policy prototype: 142 HTTP assertions and 70 native identity tests. Complete unified portal/policy journeys, manual accessibility and pilot acceptance remain open. |
| **R09** — Web maps and linked dashboard widgets | WEB-01, WEB-02, REL-02 | T-WEBMAP-01, T-DASHBOARD-01 | E1 builds owned MapStore/client. Product web-map authoring and linked table/chart/KPI dashboard journeys remain open. |
| **R10** — Responsive declarative application composer and revision lifecycle | WEB-03, WEB-04, WEB-05, REL-02 | T-APP-01, T-APP-SHARING | No accepted responsive composer or app revision/sharing implementation; responsive, accessibility, rollback and dependency tests remain open. |
| **R11** — Multi-user isolated Jupyter notebook launch and persistence | NB-01, NB-05, REL-02 | T-NB-ISOLATION | E1 includes owned Hub/Lab build and loopback kernel/save/reopen probes. Multi-user origin/container/network/filesystem isolation and persistence acceptance remain open. |
| **R12** — Pinned spatial package environments and GIS SDK | NB-02, NB-03, REL-02 | T-NB-ENV, T-SDK-01 | E1 includes bounded retained Jupyter dependencies/builds. Supported spatial profiles, SDK contracts and exact installed environment acceptance remain open. |
| **R13** — Notebook publishing and scoped scheduled execution | NB-03, NB-04, REL-02 | T-NB-PUBLISH, T-NB-SCHEDULE | No accepted notebook publication or scheduler; scoped credentials, revocation, run provenance, retry and restart journeys remain open. |
| **R14** — One QGIS copy/reference publishing wizard | FND-05, PUB-01, PUB-02, QGIS-01, QGIS-02, PUB-04, QA-01, REL-02 | T-QGIS-PUBLISH, T-PUBLISH-CRASH | E1 has QGIS desktop/server fixtures. Bundled sign-in/analyzer/copy/reference wizard, progress and worker-crash/retry acceptance remain open. |
| **R15** — Dynamic map, feature, raster and vector tile publication | SRV-01, SRV-04, QGIS-03, SRV-05, SRV-06, PUB-04, QA-01, REL-02 | T-TILES-01, T-RASTER-01 | E1 has bounded map/vector/raster/cache probes. Product map/feature/raster/raster-tile/vector-tile publication, style assets and policy tests remain open. |
| **R16** — Explicit cartographic fidelity and CRS/format diagnostics | FND-05, SRV-04, QGIS-03, QGIS-04, PUB-04, REL-02 | T-CARTO-01, T-INGEST-01 | E1 records bounded QGIS resource/render evidence; E2 changes publication source identity. Full CRS/format/visual diagnostics and Windows/Linux desktop packages remain open. |
| **R17** — Stable overwrite, dependency checking and recoverable publication | PUB-02, PUB-03, REL-02 | T-OVERWRITE-01, T-PUBLISH-CRASH | No accepted durable product publication saga; private staging, stable IDs, overwrite/dependency checks, compensation and restart/rollback acceptance remain open. |
| **R18** — Authorization enforced across every API, renderer, cache and runtime | FND-03, FND-06, PLT-02, PLT-03, PUB-01, SEC-01, SEC-02, WEB-05, NB-01, NB-05, SEC-03, REL-02 | T-AUTH-ALL, T-SEC-ABUSE | E1 includes real bounded GeoNode/GeoServer authorization probes. Product gateway and every output/cache/job/notebook bypass/revocation suite remain open. |
| **R19** — Backup/restore, upgrades, offline profile and measured support limits | OPS-02, OPS-03, QA-02, OPS-04, REL-02 | T-RESTORE-01, T-UPGRADE-01, T-OFFLINE-01, T-PERF-01 | No accepted product backup/restore/upgrade/offline distribution; source restore in E2 is separate. Measured support limits and clean-install/recovery acceptance remain open. |
| **R20** — Safe repositories, license/source compliance and evidence-based release | FND-01, FND-02, FND-06, OPS-03, REL-01, REL-02 | T-BOOTSTRAP-01, T-LOCK-01, T-RELEASE-01 | FND-01/FND-02 accepted/Merged (E1/E3). Release inventory, exact distributed bytes, source availability, security/license/brand/signing and T-RELEASE-01 remain open. |
| **R21** — Independent product ownership: source custody, local modification and release authority without upstream approval | FND-07, FND-08, OWN-01, OWN-02, SEC-04 | T-OWN-01, T-OWN-02, T-OWN-03, T-OWN-04, T-OWN-05 | E2/E5 establish retained eleven-root custody and all eleven canonical refs. Exact successor publication, independent recovery and zero-write replay passed; FND-07 is accepted/Merged via PR #73 at `7812efa3502ec1d7004b485d35b433eea56ce13e`. Build/drift/consolidation/repair gates remain open. |
| **R22** — Retained transitive build/runtime inputs, upstream-disconnected rebuilds and independent security maintenance | FND-07, FND-08, OWN-02, SEC-04 | T-OWN-01, T-OWN-02, T-OWN-04, T-OWN-05 | E1/E2 retain extensive inputs and source recovery. Complete initial owned-build inventory, donor-drift immunity, disconnected rebuild/repair and maintenance qualification remain open. |
| **R23** — Cross-repository GitHub Project with traceable tasks, dependencies, review/evidence states and safe repeatable provisioning | GOV-01, GOV-02 | T-PROJECT-01, T-PROJECT-02 | GOV-01/GOV-02 accepted/Merged (E4); live Project readback confirms both. Preserve accepted roadmap UI limitation, task progress and discussions; future delivery evidence continues. |
| **R24** — Consolidate inherited user-facing models and configuration into one product; a branded integration stack alone is insufficient | OWN-01 | T-OWN-03 | No accepted OWN-01 implementation. Consolidation register, single catalog/policy/schema/service/config authorities and alternate legacy write-path tests remain open. |

## Exact existing evidence and acceptance limits

- **E1 — accepted component tuple:** FND-02 accepted/Merged through PR #68,
  merge `973a5ef383687cd00143c679f832cfb006a57cf0`, reviewed head
  `7c4c6a6ddbc364e520911e06b9a97a7c10bdcfcf`. The
  [immutable acceptance record](../verification/fnd-02-owner-acceptance/acceptance.json)
  binds manifest SHA256
  `0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99`
  and WAR SHA256
  `90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1`.
  [Accepted criteria and profile limits](fnd-02-json-nojpeg2000-acceptance.md),
  [combination evidence](fnd-02-combination-smoke.md),
  [database evidence](postgis-slice-evidence.md),
  [Jupyter evidence](jupyter-slice-evidence.md), and
  [frontend/QGIS evidence](frontend-qgis-remediation-handoff.md)
  describe the tested scope and preserved failures/skips. NO-ORACLE,
  headless-Temurin17 and NO-JPEG2000 limits stay explicit. Neither the manifest
  nor old binaries are relabeled as builds of successor sources.
- **E2 — merged custody/publication preparation:** PR #71 at the baseline above;
  [handoff](canonical-and-publication-repairs-handoff.md),
  [canonical delivery](../verification/canonical-and-publication-repairs/canonical-delivery.json),
  [independent remote recovery](../verification/canonical-and-publication-repairs/canonical-remote-delivery.json),
  [validation](../verification/canonical-and-publication-repairs/validation.json),
  and [two exact successors](../verification/canonical-and-publication-repairs/next-source-publication.json).
  Nine owned canonical refs were recovered, with unchanged replay and preserved
  refs/defaults/disabled Actions. GeoTools successor
  `3363c3d4ae8adfe3ed2024c27f92ec63855093be` and QGIS successor
  `86af40542b219b0da6df1a43914413443330c0c0` were local at that checkpoint.
  The owner-supplied standing delegation authorizes their initial creation-only
  publication subject to fresh checks. Authorization is not evidence of execution.
  The QGIS snapshot excludes exactly 1,130 palettes and preserves all 265
  ColorBrewer palettes; no existing fork history/network purge or clearance is claimed.
  The recorded 415 package tests/four schemas are historical package evidence,
  not an owned-build, installer or GIS acceptance run.
- **E3 — repository foundation:** FND-01 accepted/Merged, PR #1 merge
  `2215a91511a53601464eef46d383cd3557cfa3a8`;
  [verified repository receipt](../verification/repository-bootstrap.json) and
  [source acquisition record](source-acquisition-evidence.md). This establishes
  allow-listed creation/provenance, not acceptance of all later source or releases.
- **E4 — governance:** GOV-01 PR #50 merge
  `3e7581a06b000856ea9b27468cc415612c28b4b0`, GOV-02 PR #52 merge
  `fc77ab978e567ce5d55e3428d1249a3b332da09d`;
  [Project IDs/evidence](../verification/project-live.json),
  [accepted view reconciliation](project-view-reconciliation.md),
  and [PR #71 preservation record](../verification/canonical-and-publication-repairs/project.json).
  Existing review-time descriptions and immutable receipts remain historical;
  they do not override verified later merges or current owner delegation.

- **E5 — authorized successor delivery:** [execution and unchanged criteria](authorized-successors-delivery.md), [publication](../verification/authorized-successors/publication.json), [independent recovery](../verification/authorized-successors/successor-recovery-summary.json), [zero-write replay](../verification/authorized-successors/successor-replay-verification.json), and [nine unchanged roots](../verification/authorized-successors/prior-nine-current.json). New source builds remain FND-08; these checks do not relabel historical binaries. PR #72 installed the independently reviewed delivery gate and required CI; [execution record](../verification/standing-delegation/workflow-execution.json). FND-03/FND-04 have since been accepted within their original prototype criteria (E6).

Current source acceptance is recorded in [PR #73 acceptance/merge evidence](../verification/authorized-successors/acceptance-and-merge.json). FND-08 and FND-05 are In progress; their acceptance and full product acceptance remain open.

- **E6 — accepted foundation prototypes:** [acceptance/merge/post-merge evidence](../verification/foundation-prototypes/acceptance-and-merge.json). FND-03 platform PR #74 at `0876999d7535d792d0024586981c762b2f9bf513` delivers the [native catalog policy spike](fnd-03-catalog-policy.md), with immediate revocation, denied inherited administration and catalog-outage/restart tests. FND-04 geodatabase PR #10 at `b7e5888b11a4b3d2246daeffe0173113f1628f2d` delivers typed snapshots and explicit conflict/post semantics, 25 actual database tests, 12 pure-model tests, and measured 100k/1m-row ten-branch behavior. Separate-context review found and repaired NULL-selector defects before merge. Fresh post-merge database checks passed. These are original P0 prototype acceptances, not completion of R06/R07/R08/R18 or P4/P7 release qualification.

## Starting dependency state (historical observation)

Read-only live observation on 2026-10-02 used the installed host CLI:
`flatpak-spawn --host gh project item-list 2 --owner aloerch --limit 150 --format json`.
Project `PVT_kwHOAOk9es4Bj_k-`,
[aloerch Project #2](https://github.com/users/aloerch/projects/2), reports
FND-01, FND-02, GOV-01 and GOV-02 **Merged**, FND-07 **In review**, and
all other planned tasks **Backlog**. The live platform issue list still has
GOV-02 issue #9 open; issue closure and task acceptance are distinct. This
observation performs no transitions and must be reconciled again before writes.

FND-03, FND-04, FND-05 and FND-07 have the accepted FND-02 dependency.
FND-08 becomes dependency-ready after actual FND-07 acceptance; FND-06 waits
for FND-03/FND-04/FND-05/FND-08. Prioritize the authorized two-source delivery,
FND-07 closure and FND-08 owned builds while independent ready foundation work
can proceed. Live progress must never be reset from initial JSON statuses.

## Completion conditions retained beyond the table

- **Platforms and packaging:** clean single-node Linux organizational install,
  offline install/update, and separately tested **Windows and Linux owned QGIS
  desktop** packages with the bundled plugin, per chapters
  [06](06-qgis-and-publishing.md) and [07](07-security-and-operations.md).
  Existing Linux component probes do not establish either product installer or
  Windows acceptance. macOS remains contingent on an actual packaging/test runner.
- **Journeys:** identity and access; install/publish/query/display/share/revoke/restart;
  all publication outputs and copy/reference/overwrite/retry behavior; real branch
  edit/conflict/reconcile/accept/post/recovery; linked maps/dashboards/apps;
  isolated notebook SDK/publishing/scheduling; coordinated backup/restore and
  supported upgrade. Preserve negative authorization, concurrency, crashes,
  cancellation, safe compensation, private staging and stable service/layer IDs.
  No SQL/WFS-T/notebook path may bypass managed branch semantics.
- **Independence and artifacts:** OWN-01 consolidation and legacy mutation restrictions;
  T-OWN-01 through T-OWN-05 custody, drift immunity, canonical state, disconnected
  rebuild/repair and maintenance. Retain submodules, complete dependencies,
  toolchains/base inputs, notices and corresponding source. Every distributed
  installer/image/desktop artifact needs exact source/build/input records, digest,
  SBOM, support limits and applicable signature evidence. Fresh-download digest
  verification and clean install/smoke run against published bytes remain required.
  No installation artifact, packaged scoped MVP or published MVP is evidenced here.
- **Human-only evaluation:** WEB-04 manual assistive-technology/accessibility review
  and representative-user pilot observations remain unperformed. Chapter 09's
  proposed usability target is at least four of five representative pilots
  completing basic publish/metadata edit without component-specific help; it is a
  target to resolve with actual evaluation evidence, never an automated pass.
  Assemble one final evaluation packet with the technically validated build.
  Proprietary client environments unavailable for QA-01 are explicit untested
  compatibility cases. Required evaluations, material legal/brand decisions and
  unavailable signing identities cannot be fabricated or waived by routine review
  delegation; production deployment and commercial launch remain outside scope.

Update this index with each accepted task's exact implementation revision,
commands/results and artifact digests. Distinguish implemented, tested, reviewed,
merged, packaged and published states; no required row is complete merely because
its issue closed or a component probe passed.
