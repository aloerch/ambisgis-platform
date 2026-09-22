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
