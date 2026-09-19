# Implementation backlog — revision 2


All tasks are planned. GitHub issues/Project hold live progress after provisioning; do not re-import initial status over it.


## P0

### FND-01 — Verify environment and create only approved repositories

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** None.

**Requirements:** R20.

**Tests:** T-BOOTSTRAP-01.

**Deliverables**

- Bootstrap receipt; verified remotes; plan/scaffold PR
- Fifteen exact approved targets; preserve source-donor history; no public product release implied

**Acceptance**

- Package tests pass; dry-run shows all targets.
- Explicit apply creates missing public repositories only; collisions fail without modifying existing repos.
- No imported workflows enabled or secrets committed.



### FND-02 — Resolve source, license and compatible dependency tuple

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-01.

**Requirements:** R20.

**Tests:** T-LOCK-01.

**Deliverables**

- Exact source/image/runtime lock proposal; license inventory; upstream patch policy

**Acceptance**

- Inspect actual GeoNode, MapStore/client, GeoServer/extensions, QGIS and Jupyter versions.
- Resolve or record blocking GeoNode/license scope issues; preserve originals.
- Build and smoke-test selected tuple; no floating latest tags.
- Upstream releases are initial acquisition candidates only; later component changes follow AmbisGIS release authority.



### FND-03 — Prove catalog identity and ACL integration

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-02.

**Requirements:** R08, R18.

**Tests:** T-AUTH-ALL.

**Deliverables**

- Two-user identity/GeoNode/GeoServer policy spike and ADR

**Acceptance**

- Public/private/group reads and revocation work through gateway and engine path.
- No duplicate policy authority or raw admin access.



### FND-04 — Prototype and compare branch versioning approaches

**Repository:** `ambisgis-geodb` · **Risk:** critical · **Human review:** required

**Dependencies:** FND-02.

**Requirements:** R06, R07.

**Tests:** T-VERSION-ORACLE.

**Deliverables**

- Kart/GeoGig/plugin comparison; reference model; typed PostgreSQL prototype; storage measurements

**Acceptance**

- Demonstrate base isolation, conflict, stale target and atomic post in a real DB prototype.
- Report snapshot storage/time and choose documented implementation; no performance claims without measurements.



### FND-05 — Compare desktop publishing and renderer integration

**Repository:** `ambisgis-qgis-plugin` · **Risk:** high · **Human review:** required

**Dependencies:** FND-02.

**Requirements:** R14, R16.

**Tests:** T-CARTO-01.

**Deliverables**

- QGIS/GeoServer/QGIS Server fixture; G3W/Lizmap comparison and ADR

**Acceptance**

- Representative style packaging/rendering and authorization work.
- Record unsupported style/provider behavior and chosen extension hooks.



### FND-07 — Acquire source custody and record independently maintained product baselines

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-02.

**Requirements:** R21, R22.

**Tests:** T-OWN-01.

**Deliverables**

- Owned product branches in every fork; provenance inventory; git bundles; retained submodule/LFS/build assets

**Acceptance**

- Every selected core component resolves to an owned source revision and retained baseline.
- No source transfer implies a copyright reassignment or blanket relicensing.
- All required additional assets are enumerated; nulls are explicit blockers, not fabricated hashes.



### FND-08 — Build the initial product spine from owned sources and cached dependencies

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-07.

**Requirements:** R21, R22.

**Tests:** T-OWN-02.

**Deliverables**

- Owned PostgreSQL/PostGIS, catalog, rendering/cache and UI builds; controlled artifact store; source/build recipes

**Acceptance**

- Initial vertical-slice components build without resolving upstream branch tips or fetching unrecorded packages.
- A simulated upstream API/branch change does not change selected inputs or outputs.
- The source inventory includes libraries, plugins, styles, fonts, CRS resources, toolchains and base image dependencies.



### FND-06 — Freeze initial contracts, threat model and fixture design

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-03, FND-04, FND-05, FND-08.

**Requirements:** R02, R18, R20.

**Tests:** T-API-01, T-SEC-ABUSE.

**Deliverables**

- ADRs; public API boundaries; synthetic corpus generator; threat model
- Koop C1 reuse spike and ADR with bounded authorized query provider

**Acceptance**

- Native/OGC/ArcGIS tiers and authoritative ownership agreed.
- All five user goals retain traceable acceptance tests.
- Koop adoption/rejection records tested output, query pushdown, pagination, permission and licensing evidence before bespoke C1 encoding.



### GOV-01 — Implement safe GitHub Project and issue bootstrap

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-01.

**Requirements:** R23.

**Tests:** T-PROJECT-01.

**Deliverables**

- Idempotent project/issue importer; local receipts; public umbrella Project; seeded issues with stable IDs

**Acceptance**

- Validate project.json and generated seed; all read preflights precede mutation.
- Retry does not duplicate project, issue, field or item; ambiguous ownership aborts.
- Project visibility is explicitly public; secrets/private security reports never enter public items.
- Permissions and partial failures are reported accurately; no token scope escalation is automatic.



### GOV-02 — Configure project views, task transitions and evidence synchronization

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** standard PR review

**Dependencies:** GOV-01.

**Requirements:** R23.

**Tests:** T-PROJECT-02.

**Deliverables**

- Backlog/board/roadmap/review/maintenance views; task state policy; exported remote IDs; setup evidence

**Acceptance**

- Task dependencies determine Ready, not the agent's preference.
- In review/Verified/Merged/Released states are not conflated; cancellation is distinct from completion.
- A plan update only edits importer-owned issue content and preserves human discussion and progress.
- All views are verified using supported interfaces; any UI-only step is reported, not claimed completed.



## P1

### PLT-01 — Build repeatable development installation and config generator

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** FND-06.

**Requirements:** R01.

**Tests:** T-INSTALL-01.

**Deliverables**

- Compose profile; init/up/status/doctor skeleton; generated secrets/network

**Acceptance**

- Clean loopback install is idempotent and contains no public admin ports.
- Health distinguishes process state from useful service readiness.



### DB-01 — Implement managed dataset identity and typed schema foundation

**Repository:** `ambisgis-geodb` · **Risk:** high · **Human review:** required

**Dependencies:** FND-06.

**Requirements:** R04.

**Tests:** T-DB-SCHEMA, T-DB-IDENTITY.

**Deliverables**

- Migrations; dataset schema library; UUID/ObjectID registry
- DEFAULT-only version identity is part of the foundation so later named branches do not require an incompatible edit-table rewrite.

**Acceptance**

- No row-number identity; stable IDs survive reorder/republication.
- Typed geometry/SRID/null/length constraints pass real DB tests.



### API-01 — Implement versioned native contracts and initial read API

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** PLT-01, DB-01.

**Requirements:** R02.

**Tests:** T-API-01.

**Deliverables**

- OpenAPI; generated clients; bounded layer/schema/read routes

**Acceptance**

- Schema tests and real feature read tests pass.
- Unsupported capabilities are false/absent.



### PLT-02 — Implement the owned catalog authority for items, policy and jobs

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** PLT-01.

**Requirements:** R08, R18.

**Tests:** T-PORTAL-01, T-AUTH-ALL.

**Deliverables**

- Catalog extension; resource/item adapters; durable job tables

**Acceptance**

- No competing catalog; two-user item visibility and revision checks pass.
- Queue loss does not erase authoritative job state.
- Modify inherited GeoNode internals where necessary; no competing external catalog or mandatory upstream hooks.



### PLT-03 — Implement gateway authentication and policy enforcement

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** API-01, PLT-02.

**Requirements:** R18.

**Tests:** T-AUTH-ALL.

**Deliverables**

- OIDC session/token handling; policy adapters; revocation checks

**Acceptance**

- Deny-path tests cover metadata, features and raw backend access.
- Revoked permissions deny new requests without relying only on delayed GeoFence sync.



### SRV-01 — Implement private GeoServer rendering/configuration adapter

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** PLT-03.

**Requirements:** R01, R15.

**Tests:** T-SRV-01.

**Deliverables**

- Engine adapter and extension manifest; upstream patch only if required

**Acceptance**

- Create private staged layer and serve map through gateway.
- No public admin/config API or arbitrary workspace passthrough.



### UX-01 — Build product shell and initial content/service details

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** PLT-02, API-01.

**Requirements:** R08.

**Tests:** T-PORTAL-01.

**Deliverables**

- React shell; design tokens; content/service/job screens

**Acceptance**

- Keyboard-accessible sign-in/content/details flow works with real API.
- Error/loading states distinguish permission denial and no data.



### PUB-01 — Complete the single-layer publish/share/revoke/restart slice

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** SRV-01, UX-01, DB-01.

**Requirements:** R01, R14, R18.

**Tests:** T-INSTALL-01, T-AUTH-ALL.

**Deliverables**

- Synthetic upload-to-private-service flow; end-to-end recording

**Acceptance**

- Clean install to map/query/item workflow requires no upstream UI.
- Second user deny/grant/revoke and restart preserve correct behavior.



## P2

### API-02 — Implement typed query grammar and bounded statistics

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** PUB-01.

**Requirements:** R02.

**Tests:** T-QUERY-01.

**Deliverables**

- Filter AST compiler; pagination; CRS; aggregates

**Acceptance**

- SQL injection/fuzz, null/date, cursor-revision and policy-filtered counts pass.
- Large/unsupported requests fail explicitly.



### API-03 — Implement explicitly scoped ArcGIS C1 facade

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** API-02.

**Requirements:** R02.

**Tests:** T-COMPAT-C1.

**Deliverables**

- Discovery/query/export/legend supported subset; conformance matrix

**Acceptance**

- Tests name exact clients/parameters; unknown operations are rejected.
- No branch/sync/federation capability claim; protected-client auth limitations recorded.
- Implement the FND-06 Koop reuse decision; no in-memory full-dataset shortcut or parallel permission authority.



### DB-02 — Implement domains, subtypes, relationships and validation rules

**Repository:** `ambisgis-geodb` · **Risk:** high · **Human review:** required

**Dependencies:** DB-01.

**Requirements:** R04.

**Tests:** T-DB-SCHEMA.

**Deliverables**

- Schema registry; deterministic rule subset; relation constraints

**Acceptance**

- Domain/default/subtype/relationship failures reject edits.
- No arbitrary SQL/Python/Arcade execution; schema revisions retained.



### API-04 — Implement basic native atomic edits and attachments

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** API-02, DB-02.

**Requirements:** R05.

**Tests:** T-EDIT-01, T-EDIT-RETRY.

**Deliverables**

- Edit endpoints; scanned blob references; idempotency/audit

**Acceptance**

- Atomic multi-layer edits within one DB; duplicate requests return original result.
- Cross-DB atomicity is rejected; untrusted ownership fields cannot be spoofed.



### OWN-01 — Consolidate inherited product models and eliminate redundant administration

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** PUB-01, FND-08.

**Requirements:** R21, R24.

**Tests:** T-OWN-03.

**Deliverables**

- Duplication register; canonical catalog/service/config models; retired or restricted legacy write paths; owned internal contracts

**Acceptance**

- Metadata, ownership, permission and service lifecycle have one authoritative source.
- Inherited admin screens cannot bypass or contradict the authoritative product model.
- Local structural changes are not rejected merely because upstream lacks an extension hook.
- Useful engine capabilities survive; notebook/database isolation is preserved.



### PUB-02 — Implement durable publication saga and recovery

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** PUB-01, API-04.

**Requirements:** R14, R17.

**Tests:** T-PUBLISH-CRASH.

**Deliverables**

- Persisted steps/leases/idempotency/compensation; staging ownership tags

**Acceptance**

- Kill worker in each step; recovery never deletes prior/shared resources.
- Private staging is not discoverable and failures retain previous active service.



### SRV-03 — Implement canonical metadata forms and standards projection

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** PLT-02, SRV-01.

**Requirements:** R03.

**Tests:** T-META-01.

**Deliverables**

- Metadata schema/editor; GeoServer/pycsw projections; original XML retention

**Acceptance**

- One update appears consistently in item/service metadata.
- Validation and stale projection errors are visible; no separate GeoNetwork install.



### SRV-04 — Implement raster ingestion and coverage/map baseline

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** PUB-02.

**Requirements:** R15, R16.

**Tests:** T-RASTER-01, T-INGEST-01.

**Deliverables**

- Raster analyzer; native/GeoServer coverage mapping

**Acceptance**

- Band/nodata/CRS validation and sample-value checks pass.
- Rendering does not masquerade as scientific coverage output.



### SEC-01 — Run complete initial service bypass/cache tests

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** API-04, SRV-03, SRV-04.

**Requirements:** R18.

**Tests:** T-AUTH-ALL, T-SEC-ABUSE.

**Deliverables**

- Security route matrix and abuse fixtures

**Acceptance**

- Query/count/legend/raster/download/admin paths enforce policy.
- Unsupported secure render combinations are denied, not leaked.



### SRV-02 — Complete service manager controls and diagnostics

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** PUB-01.

**Requirements:** R01.

**Tests:** T-SRV-01.

**Deliverables**

- Service status/start/stop/configure UX; diagnostics

**Acceptance**

- Operators manage services without GeoServer settings screens.
- IDs and permission policy persist across stop/start.



## P3

### PUB-03 — Implement stable overwrite, dependency checks and rollback

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** PUB-02, PLT-02.

**Requirements:** R17.

**Tests:** T-OVERWRITE-01.

**Deliverables**

- Immutable service revisions; active pointer; dependency analyzer

**Acceptance**

- Layer IDs/URLs/UUIDs persist; breaking changes blocked.
- Configuration rollback distinguished from dataset history; old service survives failed activation.



### QGIS-01 — Implement QGIS sign-in and catalog browser

**Repository:** `ambisgis-qgis-plugin` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** PUB-01, FND-05.

**Requirements:** R14.

**Tests:** T-QGIS-PUBLISH.

**Deliverables**

- Plugin packaging; PKCE/device flow; credential-store adapter

**Acceptance**

- No password/token in project files; supported desktop versions tested.
- Catalog only lists authorized resources.



### QGIS-02 — Implement analyzer and publishing wizard

**Repository:** `ambisgis-qgis-plugin` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** QGIS-01, PUB-02, SRV-03.

**Requirements:** R14.

**Tests:** T-QGIS-PUBLISH.

**Deliverables**

- Copy/reference choices; analyzer; progress/cancel UI

**Acceptance**

- End-to-end publish from real QGIS completes without component-specific settings.
- Missing CRS/source/font or rights issues produce actionable warnings/errors.



### QGIS-03 — Implement QGIS Server project renderer adapter

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** QGIS-02, FND-05.

**Requirements:** R15, R16.

**Tests:** T-CARTO-01.

**Deliverables**

- Sandboxed project packaging; renderer adapter; source/asset rewriting

**Acceptance**

- No macros/arbitrary plugin execution or embedded secrets.
- Same service and policy model works with both renderers.



### QGIS-04 — Verify cartographic, CRS and desktop packaging fidelity

**Repository:** `ambisgis-qgis-plugin` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** QGIS-03.

**Requirements:** R16.

**Tests:** T-CARTO-01, T-INGEST-01.

**Deliverables**

- Controlled desktop/server visual fixtures and conversion reports
- Owned QGIS Desktop/Server builds plus bundled AmbisGIS plugin; source provenance and distribution obligations

**Acceptance**

- Fonts/labels/symbols pass supported-subset tests.
- No silent SRID/units/Z/M loss; unsupported conversion documented.



### SRV-05 — Implement raster tile jobs and bounded caching

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** SRV-04, PUB-03.

**Requirements:** R15.

**Tests:** T-TILES-01.

**Deliverables**

- Gridset/zoom analyzer; seeding quotas/cancel; cache invalidation

**Acceptance**

- Requested raster tiles render; quota/cancel/retry works.
- Policy/style/data revision separation prevents private cache leakage.



### SRV-06 — Implement vector tiles with style assets

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** PUB-03, API-02.

**Requirements:** R15.

**Tests:** T-TILES-01.

**Deliverables**

- MVT/TileJSON/style/sprite/glyph pipeline; serving tests

**Acceptance**

- Client renders complete map, not just standalone PBF.
- IDs/extents/zoom limits and policy-scoped caching pass.



### PUB-04 — Complete ingestion fidelity and parser sandbox tests

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** QGIS-04, SRV-05, SRV-06.

**Requirements:** R14, R15, R16.

**Tests:** T-INGEST-01, T-PUBLISH-CRASH.

**Deliverables**

- Format/geometry/schema/CRS corpus; resource-bomb tests

**Acceptance**

- Malformed packages/paths/remote URLs fail safely.
- All requested output types have successful and interrupted-publish tests.



## P4

### DB-03 — Implement isolated typed snapshots and branch lifecycle

**Repository:** `ambisgis-geodb` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-02, FND-04.

**Requirements:** R06.

**Tests:** T-VERSION-SNAPSHOT.

**Deliverables**

- Version/snapshot/commit migrations; quotas; branch CRUD

**Acceptance**

- Branch base consistent across layers and unaffected by later DEFAULT changes.
- Cancellation/creation failure cannot expose a partial branch.



### DB-04 — Implement branch edit concurrency and audit

**Repository:** `ambisgis-geodb` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-03, API-04.

**Requirements:** R05, R06.

**Tests:** T-EDIT-01, T-EDIT-RETRY.

**Deliverables**

- Expected-head/revision checks; typed branch edits; idempotency

**Acceptance**

- Stale edits never overwrite newer work.
- Concurrent duplicate requests produce one commit; attachments/relations are atomic.



### DB-05 — Implement three-way reconcile and conflict candidate

**Repository:** `ambisgis-geodb` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-04.

**Requirements:** R07.

**Tests:** T-VERSION-ORACLE.

**Deliverables**

- Immutable B/O/T plans; field/existence/geometry conflicts; candidate validation

**Acceptance**

- Reference comparison covers delete/update, disjoint fields, Z/M and natural-key conflicts.
- No silent preference or geometry repair; plan bound to exact heads/schema.



### DB-06 — Implement accept-reconcile and atomic post

**Repository:** `ambisgis-geodb` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-05.

**Requirements:** R07.

**Tests:** T-VERSION-POST, T-VERSION-RACE.

**Deliverables**

- Branch-only accept; target promotion; approvals and lock ordering

**Acceptance**

- Changed target/source/schema invalidates plan; revalidation happens inside post.
- Crash/retry and concurrent posts produce no lost/half updates.



### DB-07 — Implement history, retention and version recovery hooks

**Repository:** `ambisgis-geodb` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-06.

**Requirements:** R06, R07.

**Tests:** T-VERSION-RECOVERY.

**Deliverables**

- History APIs; reference-aware GC; snapshot/asset backup manifests

**Acceptance**

- No live base/revision/blob collected; historical schema remains resolvable.
- Restored branch successfully reconciles/accepts/posts.



### DB-08 — Complete randomized DB/reference and fault validation

**Repository:** `ambisgis-geodb` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-07.

**Requirements:** R05, R06, R07.

**Tests:** T-VERSION-ORACLE, T-VERSION-RACE, T-VERSION-RECOVERY.

**Deliverables**

- Seeded property tests; process/DB failure harness; measurements

**Acceptance**

- Reference and real PostgreSQL state match after randomized operation sequences.
- Document supported quotas and lock/storage results; no production claims from mocks.



### QGIS-05 — Implement controlled branch edit sessions

**Repository:** `ambisgis-qgis-plugin` · **Risk:** high · **Human review:** required

**Dependencies:** QGIS-01, DB-06.

**Requirements:** R05, R06, R07.

**Tests:** T-EDIT-RETRY, T-VERSION-POST.

**Deliverables**

- Local edit buffer; revision tracking; submit/reconcile UI

**Acceptance**

- No direct managed DB writes; stale buffer requires explicit resolution.
- Lost response resolves through idempotency before clearing local edits.



### UX-02 — Implement branch management and conflict-review UX

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** DB-06, UX-01.

**Requirements:** R06, R07.

**Tests:** T-VERSION-POST.

**Deliverables**

- Version panel; diff/conflict map/table; accept/post permissions

**Acceptance**

- User inspects base/branch/target and resolves validated conflicts.
- Stale plans and permission revocation handled with no data loss.



### SEC-02 — Enforce branch read/render boundaries

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-08, UX-02, QGIS-05.

**Requirements:** R18.

**Tests:** T-AUTH-ALL.

**Deliverables**

- Branch authorization tests; DEFAULT-only WMS gate or secure immutable projection

**Acceptance**

- Feature/history/render cache cannot cross branch permissions.
- No untested branch WMS or Esri branch capability advertised.



## P5

### WEB-01 — Implement versioned web maps and MapStore adapter

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** API-02, QGIS-03, SRV-06.

**Requirements:** R09.

**Tests:** T-WEBMAP-01.

**Deliverables**

- Web-map schema/editor; stable layer/style references

**Acceptance**

- Feature/map/raster/vector layers load with correct policy and capabilities.
- Schema migrations preserve supported map settings.



### WEB-02 — Integrate linked dashboard widgets

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** WEB-01.

**Requirements:** R09.

**Tests:** T-DASHBOARD-01.

**Deliverables**

- Map/table/chart/KPI widgets; typed event bus; aggregation API

**Acceptance**

- Cross-filtering works without event loops or unbounded downloads.
- Counts/statistics enforce the same row/field policy as map data.



### WEB-03 — Build constrained responsive app composer

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** WEB-02.

**Requirements:** R10.

**Tests:** T-APP-01.

**Deliverables**

- Widget registry; layouts/breakpoints; properties/preview/undo

**Acceptance**

- User builds a functional responsive app without editing JSON.
- No arbitrary user JS; invalid bindings block publish.



### WEB-04 — Complete accessibility and task usability review

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** required

**Dependencies:** WEB-03, SRV-02.

**Requirements:** R08, R10.

**Tests:** T-A11Y-01.

**Deliverables**

- Keyboard/screen-reader tests; responsive fixtures; pilot results

**Acceptance**

- No critical focus/label/keyboard blockers; data has accessible alternative.
- Pilot findings logged and blocking workflow problems fixed.



### WEB-05 — Implement app revision, dependencies and sharing lifecycle

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** WEB-03, PUB-03.

**Requirements:** R10, R18.

**Tests:** T-APP-SHARING.

**Deliverables**

- Draft/publish/rollback; viewer preview; dependency permissions

**Acceptance**

- Public app never auto-publicizes private sources.
- Concurrent config edits conflict safely; published rollback preserves drafts.



## P6

### NB-01 — Implement isolated JupyterHub profile and SSO

**Repository:** `ambisgis-notebooks` · **Risk:** critical · **Human review:** required

**Dependencies:** PLT-03, FND-06.

**Requirements:** R11, R18.

**Tests:** T-NB-ISOLATION.

**Deliverables**

- Per-user domain/runtime; storage/quota/network; hub auth

**Acceptance**

- Two users cannot access each other or control-plane services.
- No Docker socket/admin tokens; source/output not portal-origin executable content.



### NB-02 — Build locked spatial image profiles

**Repository:** `ambisgis-notebooks` · **Risk:** medium · **Human review:** standard PR review

**Dependencies:** NB-01, FND-02.

**Requirements:** R12.

**Tests:** T-NB-ENV.

**Deliverables**

- Core/raster image locks; optional PyQGIS image; import/CRS/I/O tests
- Owned JupyterHub/JupyterLab builds and complete retained native/Python dependency graph

**Acceptance**

- Native GIS package ABI and required transformations work reproducibly.
- Image digests and libraries recorded; no claim of ArcPy parity.



### NB-03 — Implement ergonomic SDK and notebook catalog/publish integration

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** NB-02, PUB-03.

**Requirements:** R12, R13.

**Tests:** T-SDK-01, T-NB-PUBLISH.

**Deliverables**

- Generated clients; runtime auth broker; catalog extension; result publisher

**Acceptance**

- Notebook reads authorized data and publishes private output through standard saga.
- Credentials excluded from notebook source/output; revocation enforced.



### NB-04 — Implement scoped scheduled execution and provenance

**Repository:** `ambisgis-notebooks` · **Risk:** high · **Human review:** required

**Dependencies:** NB-03.

**Requirements:** R13.

**Tests:** T-NB-SCHEDULE.

**Deliverables**

- Runner; validated parameters; time-zone/concurrency/retry policy

**Acceptance**

- Job uses approved narrow identity, not retained admin token.
- Inputs/environment/output provenance and failure artifacts recorded.



### NB-05 — Complete runtime abuse, restart and quota validation

**Repository:** `ambisgis-notebooks` · **Risk:** critical · **Human review:** required

**Dependencies:** NB-04.

**Requirements:** R11, R18.

**Tests:** T-NB-ISOLATION.

**Deliverables**

- Cross-user/browser/network/resource/restart test suite

**Acceptance**

- Memory/storage exhaustion and malicious HTML do not affect other users or APIs.
- Persistent notebooks recover after restart with correct owner.



## P7

### OPS-01 — Finish organizational installer and guided diagnostics

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** PUB-04, SEC-02, WEB-05, NB-05.

**Requirements:** R01.

**Tests:** T-INSTALL-01.

**Deliverables**

- Production profile; credential enrollment; full first-run wizard

**Acceptance**

- Clean install completes all service integrations without upstream admin steps.
- Repeated initialization is safe; missing TLS/DNS/storage are diagnosed.



### OPS-02 — Implement coordinated backup and isolated restore

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** DB-07, NB-05, PUB-03.

**Requirements:** R19, R07.

**Tests:** T-RESTORE-01, T-VERSION-RECOVERY.

**Deliverables**

- Checkpoint/backup manifests; restore command; rehearsal logs

**Acceptance**

- Restore complete catalog/data/assets/notebooks and execute branch post.
- No untested RPO/RTO guarantee; actual recovery timings recorded.



### OPS-03 — Implement locked upgrades and migration recovery

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** OPS-02, FND-02.

**Requirements:** R19, R20.

**Tests:** T-UPGRADE-01, T-LOCK-01.

**Deliverables**

- Release lock; staging-copy upgrade; ordered migrations; rollback notes

**Acceptance**

- Supported previous release upgrades with contract tests.
- Irreversible migrations are not falsely reversed by image rollback.



### OPS-04 — Validate offline distribution and operational dependencies

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** OPS-03, NB-02.

**Requirements:** R19.

**Tests:** T-OFFLINE-01.

**Deliverables**

- Offline source/image/docs/grid/font bundle; install/update tests

**Acceptance**

- Fresh offline host starts required workflows without hidden downloads.
- Third-party basemaps and optional network features are clearly disabled or configured.



### OWN-02 — Demonstrate no-upstream rebuild, independent patch and product recovery

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** OPS-04, NB-02, QGIS-04, FND-08, OWN-01.

**Requirements:** R21, R22.

**Tests:** T-OWN-04.

**Deliverables**

- Air-gapped rebuild/install report; independently implemented regression fix; restored source/artifact/backlog export

**Acceptance**

- With upstream origins and public registries blocked, rebuild all selected components from retained source and dependencies.
- Using a synthetic defect, produce and test an owned source patch without consulting or importing a donor update.
- Install signed product artifacts, run publication/branch/notebook tests and restore after failure.
- Reproducibility differences are documented; no claim of bit-for-bit reproducibility without evidence.



### QA-01 — Run native/OGC/ArcGIS and actual client compatibility matrix

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** API-03, PUB-04, WEB-05, NB-05, SEC-02.

**Requirements:** R02, R14, R15.

**Tests:** T-API-01, T-COMPAT-C1, T-QGIS-PUBLISH.

**Deliverables**

- Named build/operation conformance results; release capability matrix

**Acceptance**

- Supported exact clients and authentication paths pass real tests.
- Core OSS CI remains runnable without proprietary licenses.



### QA-02 — Measure supported scale and workflow usability

**Repository:** `ambisgis-platform` · **Risk:** medium · **Human review:** required

**Dependencies:** OPS-01, DB-08, WEB-04.

**Requirements:** R19, R08.

**Tests:** T-PERF-01.

**Deliverables**

- Reproducible load scripts; hardware/data/results; supported quotas

**Acceptance**

- Report p95/error/resource results with warm/cold and security scope.
- Only measured limits appear in release notes.



### SEC-03 — Complete release threat-model and abuse review

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** OPS-01, OPS-03.

**Requirements:** R18.

**Tests:** T-AUTH-ALL, T-SEC-ABUSE.

**Deliverables**

- Independent security review; all route/cache/runtime tests

**Acceptance**

- No blocking authorization/secret/execution/data-integrity defect.
- Failures/skips explicitly recorded and prevent unsupported capability claims.



### SEC-04 — Establish independent security maintenance and supported-release obligations

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-07, SEC-03.

**Requirements:** R21, R22.

**Tests:** T-OWN-05.

**Deliverables**

- Dependency vulnerability triage policy; source patch/backport workflow; supported-series inventory; private reporting route

**Acceptance**

- Security responsibility belongs to AmbisGIS even when no upstream fix exists.
- A corrective patch is tested against product contracts and storage/recovery invariants.
- No automatic donor synchronization, indefinite insecure freezing or unsupported SLA.



### REL-01 — Complete license/branding/source and supply-chain release gate

**Repository:** `ambisgis-platform` · **Risk:** high · **Human review:** required

**Dependencies:** FND-02, OPS-03, OPS-04, OWN-02, SEC-04.

**Requirements:** R20.

**Tests:** T-RELEASE-01.

**Deliverables**

- Notices; exact-source bundle; SBOM; signatures/provenance; branding review

**Acceptance**

- No unresolved redistribution/trademark/source-obligation blockers.
- Every binary/image maps to exact source/build and dependency records.



### REL-02 — Publish first complete scoped release after acceptance

**Repository:** `ambisgis-platform` · **Risk:** critical · **Human review:** required

**Dependencies:** SEC-03, QA-01, QA-02, REL-01, OPS-02, OWN-02, GOV-02.

**Requirements:** R01, R02, R03, R04, R05, R06, R07, R08, R09, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, R20.

**Tests:** T-RELEASE-01.

**Deliverables**

- Five-goal end-to-end acceptance record; release notes; support matrix

**Acceptance**

- All required requirements have merged implementation and actual passing evidence.
- Explicitly list remaining Esri incompatibilities/exclusions; no blanket parity claim.
