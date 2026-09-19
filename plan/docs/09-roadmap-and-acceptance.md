# 09 — Roadmap, requirements traceability and acceptance

## 1. Delivery approach

Use acceptance-gated increments. AI can produce and review substantial code, but cannot convert an undefined compatibility target into a verified one by assertion. Every phase leaves a runnable, demonstrable slice plus tests and a capability matrix that says what is still missing. Calendar estimates are intentionally omitted until the P0 prototypes establish scope and integration costs.

A phase can be developed in parallel where dependencies permit, but a phase exit cannot waive an earlier integrity/security gate. The `backlog.json` dependency graph is the machine-readable execution order; each task contains deliverables, acceptance criteria, test identifiers and the owning repository. Break oversized tasks into reviewable subtasks without dropping acceptance criteria.

## 2. Phases and exit demonstrations

| Phase | Outcome | Required exit evidence |
|---|---|---|
| P0 — validate foundations | Repos, source/license/dependency evidence, critical spikes, threat/contract decisions | Account-safe bootstrap; verified donor baselines and owned initial component builds; source/dependency custody; catalog/map/identity spike; branch reference/DB prototype; QGIS publishing comparison; Project setup/evidence or precisely tracked authorization blockers; ADRs. |
| P1 — one cohesive vertical slice | Install, identity, catalog, simple service and modern shell | From a clean supported host: sign in, publish one synthetic layer, view map/query/metadata, deny a second user, restart successfully. Not yet the full product. |
| P2 — service/data lifecycle | Native queries/edits, metadata, state-machine publishing, raster baseline, C1 subset | No manual upstream configuration; bounded query/edit contracts; failed job recovery; metadata consistency; all advertised C1 operations pass tests. |
| P3 — desktop and all requested publication outputs | QGIS wizard, fidelity option, stable overwrite, map/feature/raster/vector tiles | Publish representative desktop fixtures, compare renderers, interrupt/retry, preserve service/layer IDs, verify permissions and tile assets. |
| P4 — branch-style geodatabase | Schema semantics, snapshots, edits, reconcile/accept/post, native UI/plugin | Full conflict/concurrency/crash/property suite and restored branch post. No Esri branch-protocol claim. |
| P5 — modern portal applications | Web maps, dashboards, responsive app composer | End-user creates a linked map/table/KPI dashboard and responsive app, publishes/rolls back it, passes permission/accessibility tests. |
| P6 — notebooks | Isolated environments, SDK/catalog/publish, scheduled runs | Two-user isolation, pinned spatial image tests, notebook-to-service publishing, revocation, restart and schedule provenance. |
| P7 — release hardening | Supported installation/upgrade/recovery, measured scale, licenses/security/release | Complete capability/ownership acceptance run; upstream-disconnected rebuild and independent patch; security/license approval; actual Project evidence; exact product manifest and recovery record. |

The first complete **scoped** release is after P7. P1 is a technical alpha, not feature parity. P3/P4/P5/P6 can overlap after their contract dependencies, but security reviews and data migrations have a single responsible integrator.

## 3. User requirement traceability

| User goal | Required deliverables | Release gate |
|---|---|---|
| 1. Server-like REST and simple metadata/setup | Service manager, native API, selected OGC/C1 operations, canonical metadata, integrated installer | `T-INSTALL-01`, `T-SRV-01`, `T-META-01`, `T-AUTH-ALL`, `T-COMPAT-C1` |
| 2. Enterprise-geodatabase-like storage with branch workflow | Typed schema/domains/relations, stable IDs, service-only edits, snapshots, conflicts, accept/post, history | `T-DB-SCHEMA`, `T-VERSION-ORACLE`, `T-VERSION-RACE`, `T-VERSION-RECOVERY` |
| 3. Modern portal/apps | One catalog/identity, map authoring, linked dashboards, responsive composer, revision/sharing UX | `T-PORTAL-01`, `T-APP-01`, `T-APP-SHARING`, `T-A11Y-01` |
| 4. Spatial notebooks | JupyterHub/Lab, pinned packages, least-privilege runtime/SDK, publishing and jobs | `T-NB-ENV`, `T-NB-ISOLATION`, `T-NB-PUBLISH`, `T-NB-SCHEDULE` |
| 5. Simple QGIS publishing of service types | Plugin analyzer/wizard, copy/reference, map/feature/raster/vector outputs, stable overwrite | `T-QGIS-PUBLISH`, `T-CARTO-01`, `T-TILES-01`, `T-PUBLISH-CRASH`, `T-OVERWRITE-01` |
| 6. Independent product, source and maintenance authority | Owned forks/builds, retained dependencies, canonical-model consolidation and independent repair | `T-OWN-01` through `T-OWN-05` |
| 7. GitHub Projects governance | Cross-repository Project, safe issue provisioning, dependency/evidence workflow | `T-PROJECT-01`, `T-PROJECT-02` |

`requirements.json` expands these into independently testable requirements. Every required item must link to an implementation task and actual test evidence before the release is labeled complete.

## 4. Test corpus

Use entirely synthetic datasets: address points, roads, parcels/polygons, a related inspection table, attachments, a small multiband raster, a time/mosaic fixture for later capability, and a rich-style QGIS project. Include a projected-feet dataset in EPSG:2230; numeric domains; Unicode; nulls/empty strings; date-only and zoned timestamps; decimal precision; Z/M geometries where supported; complex polygons; invalid geometries; duplicate keys; relationship violations and unusually large IDs.

Create small deterministic fixtures for correctness and parameterized larger fixtures for performance. Record random seeds and geometry generation rules. Do not upload City/contractor databases, exported private services, internal source schemas, production connection strings or licensed Esri sample content without authorization and redistribution rights.

The corpus includes private/public/group-shared data, row-filtered data, field-restricted data, and resources whose permission is revoked during operation. Private raster/tiles/search facets/job logs are tested, not only feature reads.

## 5. Test levels and evidence

**Unit/model:** filter parsing, capability resolution, metadata mapping, state-machine transitions, three-way field/existence merge, ID mapping, schema compatibility and policy evaluation.

**Database integration:** real PostgreSQL/PostGIS migrations, constraints, snapshot consistency, atomic edits/post, locks, concurrent transactions, retention and restoration. Test under the isolation levels the implementation actually uses.

**Contract/interoperability:** schema validation and native SDK tests; selected OGC conformance; explicitly named ArcGIS client/operation fixtures with public or appropriately licensed test environments. Esri integration tests are separate from the fully open-source CI path so the platform does not require a proprietary license to develop its core.

**End-to-end:** browser Playwright and actual QGIS plugin tests/fixtures. Run complete workflows rather than isolated successful HTTP requests. Mobile/responsive/accessibility behavior receives manual review alongside automation.

**Security/fault:** direct backend access attempts, spoofed headers, query/URL/upload abuse, cross-user notebook access, stale/replayed edits, cache isolation, worker termination, database disconnect, engine unavailability, expired source credentials and resource exhaustion.

**Recovery/performance:** restored full workflow; dependency upgrade rehearsal; repeatable load with recorded host/runtime/data/latency distributions. Attach actual logs/artifacts to the task evidence. A simulated result or a mocked HTTP response is never described as a real integration pass.

## 6. Proposed performance and usability targets

These are initial **targets to negotiate after P0 measurement**, not published benchmarks or hard guarantees. Correctness/security failures cannot be traded away to meet latency.

| Workload on recorded reference host | Initial target / measurement |
|---|---|
| Catalog search, warm small deployment | p95 below 1 second at 10 concurrent users, with policy filters. |
| Indexed bbox query, 1,000 returned simple features | p95 below 1 second; report payload/geometry complexity and cache state. |
| 100-feature atomic edit request | p95 below 2 seconds without lock contention; report conflicts separately. |
| Warm raster/vector tile | p95 below 500 ms locally; network/CDN conditions are separate. |
| Dynamic 1024×768 representative map | p95 below 3 seconds, with named renderer/style/feature count. |
| Branch snapshot/reconcile | Measure 100k/1m feature groups and 10 branches; set supported quotas from storage and lock results. |
| Usability | At least 4 of 5 representative pilot users complete basic publish and metadata edit without component-specific configuration assistance. |
| Accessibility | Zero unresolved critical keyboard/focus/label blockers in required journeys; manual assistive-technology review. |

A benchmark must publish configuration, resource consumption, error rates, percentiles, warm/cold distinction and policy scope. Do not quote throughput from a different upstream project as the performance of this distribution.

## 7. Definition of done for an implementation task

A task is done only when code is merged through the agreed review path, required tests actually pass, user-facing failure handling exists, contracts/docs/capability matrix are updated, migrations have rollback/recovery notes, license/source notices are preserved, no secrets or sensitive fixtures are present, and `STATUS.md` links to the commit/PR and evidence. A TODO, mock, screenshot or green container is not an implementation of the named capability.

Security-critical/database tasks require an independent reviewer. Where one person operates all AI agents, use a separate reviewer context and then explicit human inspection for release-critical decisions; an agent's self-review is not independent evidence.

## 8. First-release readiness checklist

All five user goals pass end-to-end. Every advertised REST capability has positive/negative tests. Unimplemented capabilities are absent or false. Versioning passes concurrency/crash/recovery tests. All read paths enforce policy. Notebooks are origin/runtime isolated. Installer, backup, restore and supported upgrade work from documented steps. Artifacts are reproducibly built with licenses/notices/source availability, SBOM and no blocking vulnerabilities. Performance/support limits are documented. The release clearly states that full Esri protocol, analysis, network, offline and proprietary desktop publishing parity are outside its certified scope.

## 9. Major risks and mitigations

| Risk | Early mitigation | Escalation trigger |
|---|---|---|
| Branch engine complexity/data loss | P0 prototype, pure oracle, real DB concurrency tests, staged rollout | Any invariant violation blocks edits/post release. |
| Cross-engine permission drift | Single catalog policy + gateway + deny-path matrix | Private output obtainable via any route/cache blocks release. |
| Inherited source maintenance burden | Owned baselines, controlled builds, independent fixes/backports, canonical-model refactors | No demonstrated source/build/repair path -> block release and resolve the ownership gap. |
| QGIS style loss | Dual renderer, analyzer, visual fixtures | Silent loss of supported symbols/labels blocks publishing fidelity claim. |
| Excessive deployment burden | One installer/profile, avoid unnecessary extra engines | Routine operation still requires several component admin UIs -> UX/integration defect. |
| Notebook compromise | Per-user origins, container/network isolation, scoped tokens | Runtime can reach control-plane credentials or another user's data -> no multi-user release. |
| License/trademark ambiguity | Exact-source inventory and preserved notices | Unresolved combined-work/redistribution issue blocks binaries/branding release. |
| AI-generated superficial completeness | Evidence-gated tasks and capability matrix | Tests skipped/replaced with mocks without disclosure -> task reopened. |

## 10. Later expansion without scope creep

After the scoped release, evaluate advanced raster analytics, large-scale structural-sharing branches, richer topology/rules, offline synchronization, C2/C3 interoperability, multi-node HA and additional client support as separate designs. Hub/Online/Knowledge remain excluded unless the user changes scope. Do not start them while a required basic publishing, editing or recovery workflow is still missing.


## Revision 2 independence and governance gates

P0 additionally requires FND-07 source custody and FND-08 owned builds for the initial product spine. GOV-01/GOV-02 establish the cross-repository Project and evidence workflow in parallel with unblocked engineering. P1 is built from owned product revisions, not upstream containers whose source repair path is untested.

P2 includes OWN-01 canonical-model consolidation. P7 additionally requires OWN-02's upstream-disconnected rebuild/independent repair and SEC-04's maintenance obligations. R21/R22/R24 make source, build, repair and product authority part of release acceptance; R23 makes GitHub work tracking traceable. The Project cannot waive integrity/security gates, and independent maintenance cannot be postponed beyond the first supported release.

The complete scoped release requires these additional gates as well as the original capabilities. A working integration demo does not satisfy revision 2 product ownership.
