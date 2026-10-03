> Active authority: [standing owner delegation](docs/standing-delivery-policy.md), owner task sections 2 and 5. It supersedes earlier routine approval/continuation stops while preserving all product acceptance, rights/security blockers, excluded actions and historical records. Read it before applying procedural gates below.

# Decision index — revision 2

| Decision | Status | Evidence / consequence |
|---|---|---|
| Independently maintained product, not upstream-led integration | User requirement | Owned forks, builds, contracts and patch/release authority; chapter 11. |
| Substantive consolidation permitted and required | User requirement | One product model; inherited extension hooks and minimal patch size are not constraints. |
| Four new repositories plus eleven core forks | Revised baseline | Fifteen exact allow-listed targets; PostgreSQL/PostGIS/QGIS/Jupyter included. |
| One AmbisGIS catalog/metadata/policy authority derived initially from GeoNode | Baseline | Refactor inherited source; do not maintain duplicate writable catalogs. |
| GeoServer-derived rendering with owned GeoTools/GeoWebCache; optional QGIS-derived renderer | Baseline | Test owned builds and fidelity/security boundaries. |
| QGIS-derived supported desktop with bundled product plugin | Baseline | Upstream QGIS compatibility is optional, not the sole supported path. |
| Native feature/version contract; separate Esri compatibility tiers | Baseline | No untested capability flags or implied universal client support. |
| Eager typed snapshots for initial branch prototype | Evidence gate | FND-04 tests correctness/storage; retain required invariants if changed. |
| One public user-owned GitHub Project | User-requested governance | Project schema and safe importer in chapter 12; no live Project created yet. |
| Product name AmbisGIS | Provisional | Not trademark-cleared; actual clearance and asset/license review required. |
| GPL-3.0-or-later for new first-party code | Proposed license | Not a blanket license for inherited code; selected-file review required. |
| Source/dependency retention and independent security repair | Required | FND-07/FND-08, OWN-02, SEC-04. |
| Isolated notebook origins and runtimes | Required | Product unity must not weaken arbitrary-code security boundaries. |
| Single-node Linux, one organization per deployment first | Baseline | Measured recovery before HA/SaaS claims. |
| Exact component commits, artifact hashes and license closure | Unresolved P0 gate | Template is not a working lock; no invented values. |
| Controlled Java HTTP and OAuth development probes | Candidate; human security review pending | [ADR 005](adrs/005-controlled-java-http-and-auth-probes.md): verified loopback egress, retained fixtures, actual packaged logging and bounded opaque-token repairs; no release/source/security acceptance. |
| Configured GeoServer authorization and exact repaired aggregate | Engineering candidate; fresh human security review before merge | [ADR 006](adrs/006-configured-geoserver-authorization.md): synthetic opaque identity, real configured WFS/REST/role enforcement, explicit stateless mode, credential-safe diagnostics, exact-WAR restart and retained runtime limits. |
| F02-06 exact candidate inventory and grouped selection decisions | #65 consolidation checkpoint accepted; new variant adoption pending | [Candidate proposal](docs/fnd-02-candidate-proposal.md) and generated [decision register](docs/fnd-02-owner-decisions.md); baseline bytes remain preserved, chapter 11 maintenance binding prepared, selection/rights decisions separate from structural validity. |
| F02-06 frontend/IFC and QGIS optional-resource remediation | Implementation authorized by current owner prompt; new variant review pending | [Authorization](verification/frontend-qgis-remediation/authorization.json), [handoff](docs/frontend-qgis-remediation-handoff.md): exact retained IFC source and frozen frontend replay; 1,129 named QGIS palette exclusions. SRC-02 GMT alias and six Java blockers remain. No adoption/distribution or F02-07/F02-08 acceptance. |
| F02-06 independent JSON and optional JPEG2000 exclusion | Implementation authorized; tested successor proposed, owner adoption ungranted | [Exact handoff](docs/json-jpeg2000-remediation-handoff.md), [source/terms and removal comparison](docs/jpeg2000-exclusion-handoff.md), [four-criterion/maintenance decision](docs/fnd-02-json-nojpeg2000-acceptance.md). Both variant-only findings remediated; original rights and later obligations unchanged. NO-ORACLE/headless/NO-JPEG2000 selection requires explicit owner acceptance. |

## Final FND-02 decision — supersedes proposal status above

On `2026-09-22T23:20:02Z`, owner `aloerch` (user ID `15285626`) separately
[accepted FND-02 and the exact revision 4 candidate](https://github.com/aloerch/ambisgis-platform/issues/3#issuecomment-5785944488),
all four original criteria, internal F02-06/F02-07/F02-08, the
NO-ORACLE/headless-Temurin17/NO-JPEG2000 limits and chapter 11 maintenance rule.
Reviewed PR #68 head `7c4c6a6ddbc364e520911e06b9a97a7c10bdcfcf` was merged as
`973a5ef383687cd00143c679f832cfb006a57cf0`. The
[separate governance record](verification/fnd-02-owner-acceptance/acceptance.json)
binds the comment to manifest `0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99`
and WAR `90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1`.
The immutable manifest, generated review-time finding register and historical
receipts retain their original fields. Acceptance grants subsequent engineering;
FND-03/FND-05/FND-07/FND-08, P0, distribution/notices/security/source/operational
gates, release/deployment and future merges remain unaccepted. New source custody
work belongs to FND-07 under its own criteria.

FND-07 materialized source custody is proposed for owner review in [ADR 009](adrs/009-accepted-source-custody.md): independently restored core histories, guarded product-source replay and Class B vendor recovery. Remote promotion and human review remain pending; no public source ref/default/workflow or distribution approval is granted.

## FND-07 exact non-default publication decision — 2026-09-26

The [separate owner comment](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5850316210)
binds PR #69 head and its immutable eleven-row promotion plan. It authorizes
creation of absent `ambisgis/review/fnd-07-baseline-v4` refs only where applicable
source-publication rights are established, and repository Actions disablement
on exactly those source forks. It accepts the prior restoration/notice/asset
evidence within its limits. It is not final FND-07 acceptance, authority to
promote canonical source refs/defaults, or permission to publish custody archives.
See [execution and rights evidence](verification/source-ref-promotion/README.md).

## FND-07 nine canonical refs and local repair preparation — 2026-09-28 UTC

The [separate live owner authorization](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863464446)
authorizes only the nine immutable canonical rows and local GeoTools/QGIS source
repair preparation. All nine refs were created and verified; exact replay made
zero ref/settings mutation attempts. Original refs/defaults and disabled Actions
remain preserved. This supersedes the previous canonical-authorization blocker,
not the original source-promotion plan or FND-02 acceptance.

The two changed-source successors remain local and require the [exact subsequent
publication decision](verification/canonical-and-publication-repairs/next-source-publication.json).
[ADR010](adrs/010-qgis-publication-source-boundary.md) records QGIS's parentless
source boundary, preserved custody history and unresolved existing-host/network
condition. [The handoff](docs/canonical-and-publication-repairs-handoff.md) binds
actual source identities, recovery/equivalence evidence and unchanged FND-07
criteria. No held-root publication, default switch, merge, final task acceptance
or FND-08 execution is implied.

## FND-08 acceptance and FND-06 start — 2026-10-03

[PR #76](https://github.com/aloerch/ambisgis-platform/pull/76) merged the independently
reviewed owned initial-spine build evidence as `6d18637e39818e60bcc947d3a7c252e84ab48fe0`.
[Actual acceptance](verification/fnd08-acceptance/acceptance-and-merge.json) follows
fresh final-artifact runtime and independent verification. This accepts the original
FND-08 criteria, including recorded raw reproducibility differences; it does not
accept full source-toolchain bootstrap, OWN-02 repair, installation or release.
FND-06 is dependency-ready and claimed for contracts, corpus, threat model and the
mandatory Koop comparison. Its architecture/adoption decisions await evidence.
