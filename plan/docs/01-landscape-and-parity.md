# 01 — Open-source landscape and feature parity

## 1. How to read the comparison

The comparison is functional, not a market-share or legal-monopoly analysis. There is no useful single percentage called “ArcGIS parity”: rendering, edit integrity, administrative UX, desktop publishing, security, and operations are different dimensions. The statuses below mean **available upstream**, **partial/building block**, or **new integration/product work**. They do not mean an integrated AmbisGIS implementation already exists.

A capability can be technically strong and still produce a poor end-to-end experience when identities, metadata, styles, permissions, and installation are fragmented. Conversely, some open-source systems offer valuable database or standards flexibility that should not be discarded merely to imitate a vendor UI.

## 2. Product-to-project comparison

| ArcGIS reference | Principal open-source candidates | What can be reused | Important gap for this project |
|---|---|---|---|
| Enterprise geodatabase | PostgreSQL/PostGIS; Kart; GeoGig; QGIS versioning | Spatial SQL/indexes/types; separate spatial version-control approaches. [S13–S17] | Unified schema semantics, service-only branch editing, conflict review, atomic post, domain/relationship enforcement. |
| GIS Server map services | GeoServer; QGIS Server; MapServer | Server rendering and standard map/feature/coverage interfaces. [S01, S04, S11, S45] | Unified configuration, ArcGIS-shaped service facade, transactional publishing, a simple service manager. |
| GIS Server feature services | GeoServer WFS/OGC Features; pygeoapi; Koop; custom feature API | Standards-based access plus existing GeoServices output foundations. [S05, S24, S41, S44] | Esri query/edit contracts, user-facing edit semantics, attachments/relations, branch integration. |
| Portal | GeoNode + MapStore; G3W-SUITE; Lizmap | Catalog/sharing/metadata and integrated mapping or publishing workflows. [S06–S10, S39–S40] | One polished UX, lifecycle consistency, app-composer requirements, notebook/version APIs. |
| Metadata/catalog | GeoNode; GeoServer metadata extension; pycsw; GeoNetwork | Several existing levels of metadata authoring and standards. [S02, S06, S25–S26] | One authoritative record and simple authoring workflow; avoid mandatory second admin application. |
| Dashboards | MapStore dashboards | Connected maps/charts/tables/counters. [S09] | Product theming, unified service permissions, chosen widget/event contracts, accessible workflows. |
| Experience Builder | MapStore application contexts/extensions; custom composer | Configurable application foundations. [S10] | General responsive composition and a curated widget framework; not Esri widget import compatibility. |
| Notebook Server | JupyterHub/JupyterLab + scientific images | Notebook execution and multi-user runtime building blocks. [S18–S19] | GIS-ready environments, resource/identity integration, safe isolation, publish SDK, scheduled execution. |
| Image Server subset | GeoServer coverage/ImageMosaic; GDAL; TiTiler | Raster coverage/mosaic/COG/tile building blocks. [S04, S27, S43] | Unified raster publishing; full raster analytics, orthomapping, and Esri raster-function chains excluded initially. |
| ArcGIS Pro publishing | QGIS plugin + QGIS Server or GeoServer adapter; Lizmap/G3W | Desktop/project-based publishing patterns and rendering. [S11–S12, S39–S40] | A single supported wizard, stable service IDs, overwrite/dependency checks, packaging diagnostics. |

GeoServer is a strong default, **not an objectively universal “best alternative.”** QGIS Server becomes preferable when preserving QGIS-specific cartography is more important than supporting a broad server-side style dialect. G3W-SUITE and Lizmap merit a working evaluation, not dismissal because the initial mental model named GeoNode.

## 3. Detailed feature matrix

“Implement” below names work in the proposed AmbisGIS distribution. Phase gates, not the presence of an upstream checkbox, establish acceptance.

| ID | Capability | Existing foundation | AmbisGIS decision / implementation needed |
|---|---|---|---|
| CAP-01 | Simple installation | GeoNode integrated installation [S08] | Generate all component settings, credentials, callbacks, storage, health checks; one diagnostic surface. |
| CAP-02 | Modern service manager | GeoServer admin/config REST [S01] | Build service-oriented UI; do not expose upstream setup complexity as normal workflow. |
| CAP-03 | Dynamic map image | GeoServer / QGIS Server [S01, S11] | Gateway adapter, legend/identify consistency, policy enforcement, stable service URLs. |
| CAP-04 | Feature query | WFS/OGC APIs, PostGIS [S05, S13, S24] | Native typed query API with bounded filter grammar; tested ArcGIS subset. |
| CAP-05 | Feature edits | Database transactions; upstream edit protocols | Service-only native edit API with concurrency, validation, audit and permissions. |
| CAP-06 | Multi-layer edit atomicity | PostgreSQL transactions [S14] | Group layers in one managed geodatabase; reject impossible cross-database atomic requests. |
| CAP-07 | Domains / coded values | Database constraints; some import metadata [S27] | Registry, UI forms, subtype-specific domain binding, server validation and export mapping. |
| CAP-08 | Subtypes / field defaults | Generic database and application components | Explicit type registry, immutable IDs, supported default-expression grammar. |
| CAP-09 | Relationships | PostgreSQL foreign keys; import support [S27] | Typed relationship metadata and query/edit APIs; rules enforced per branch state. |
| CAP-10 | Attachments | Database/blob primitives | Immutable content, transactional relationship metadata, limits, policy-aware download. |
| CAP-11 | Global IDs / ObjectIDs | UUIDs / sequences | Stable identity independent of branch, import, layer order, or publication revision. |
| CAP-12 | Editor tracking | Database/service audit primitives | Trusted identity/time, immutable audit, no client spoofing of ownership. |
| CAP-13 | Named edit branches | Kart, GeoGig, versioning plugin [S15–S17] | Evaluate; implement accepted service-first semantics and UI rather than assume interchangeability. |
| CAP-14 | Reconcile/conflicts/post | Separate version-control approaches [S15–S17] | Three-way feature/field comparison; stale-head detection; atomic constraint-checked promotion. |
| CAP-15 | Historical queries | Snapshots / application revision models | Immutable commits, retention, policy checks, time/revision semantics explicitly defined. |
| CAP-16 | Attribute rules | SQL constraints / functions | Declarative validation/calculation subset; no unrestricted SQL/Python/Arcade submitted by users. |
| CAP-17 | Spatial validation | PostGIS operations [S13] | Chosen geometry validity policy, no silent repair; cross-feature rules as separate work. |
| CAP-18 | Full Esri topology/network fabric | Not the selected foundations | Excluded; a geometric validity check is not a topology/Utility Network implementation. |
| CAP-19 | Basic layer metadata | GeoNode / GeoServer metadata [S02, S06] | One editor and schema with projection into service descriptions. |
| CAP-20 | Standards metadata export | pycsw / GeoNetwork / GeoServer [S02, S25–S26] | Supported ISO/CSW mapping chosen and validated; preserve original imported XML. |
| CAP-21 | Metadata review/harvesting | GeoNetwork [S25] | Optional advanced deployment profile; not required for ordinary layer publication. |
| CAP-22 | Raster coverage | GeoServer WCS/mosaic [S04] | Publish/analyze/authorize coverage assets and render presets. |
| CAP-23 | Raster map tiles | GeoWebCache / coverage renderer | Automated gridset, extent, seeding, quota, version invalidation. |
| CAP-24 | Vector tiles | GeoServer vector tiles; Martin [S03, S42] | TileJSON/style/sprite/glyph lifecycle; measured alternative server only if needed. |
| CAP-25 | Cloud-optimized rasters | GDAL/TiTiler building blocks [S27, S43] | Optional COG path with range access controls and explicit data/visualization distinction. |
| CAP-26 | Raster analytics parity | Python/GDAL components | Basic registered notebook/jobs; distributed Image Server workflows not promised. |
| CAP-27 | Portal item catalog | GeoNode [S06] | Extend existing schema; add service, app, notebook, version-workspace item types. |
| CAP-28 | Users/groups/sharing | GeoNode/identity components [S07, S34] | One authoritative policy model and tests across every route/cache/engine. |
| CAP-29 | Web maps | MapStore [S09–S10] | Stable item references and renderer adapters; own versioned map definition. |
| CAP-30 | Dashboards | MapStore connected widgets [S09] | Reuse, theme, integrate resource permissions and accessible keyboard operations. |
| CAP-31 | Responsive app builder | MapStore contexts [S10] | New declarative composition, layouts, draft/publish workflow and widget registry. |
| CAP-32 | Esri app JSON / Arcade import | No accepted compatibility implementation | Unsupported by default; provide manual migration report, not a false automatic conversion. |
| CAP-33 | Notebook editor | JupyterLab [S18–S19] | Integrated catalog lifecycle and safe launch. |
| CAP-34 | Multi-user notebook execution | JupyterHub [S18] | Isolated runtime, per-user origin, quotas, persistence, scoped tokens. |
| CAP-35 | Python spatial environment | Scientific images + spatial libraries | Lock/test interoperable native packages; separate core, raster, optional PyQGIS profiles. |
| CAP-36 | Scheduled notebooks | Notebook execution tools and worker framework | Least-privilege execution, parameter schemas, run provenance, no hidden user token reuse. |
| CAP-37 | Desktop publication | QGIS ecosystem [S11–S12, S39–S40] | AmbisGIS wizard, analyzer, upload/reference, asynchronous progress and rollback. |
| CAP-38 | QGIS styling fidelity | Shared QGIS rendering libraries [S11] | Pin compatible renderer, fonts and assets; compare against desktop fixture render. |
| CAP-39 | Cross-engine styling | QGIS/SLD export path | Define a tested subset and warn on unsupported constructs; choose QGIS renderer when needed. |
| CAP-40 | Stable overwrite | Generic service/catalog primitives | Immutable publication revision, preserved IDs, atomic active-pointer cutover. |
| CAP-41 | ArcGIS-shaped discovery | Public Esri REST contract; Koop GeoServices output [S21, S44] | Evaluate reuse before implementing compatibility tier C1; do not call it full server federation. |
| CAP-42 | Esri branch REST protocol | Public version contract [S20] | Separate deferred compatibility profile; native branch functionality comes first. |
| CAP-43 | Offline replicas / sync | Different ecosystem projects | Explicit later work; no `syncEnabled` claim before protocol and conflict tests. |
| CAP-44 | Backup / restore / upgrades | Database and upstream mechanisms | One manifest-aware backup/restore procedure and supported upgrade path. |
| CAP-45 | Multi-node availability | Component-specific scale mechanisms | Later HA profile; Compose restart policies are not HA. |
| CAP-46 | Accessibility / modernity | Varies by upstream screen | Product design system, WCAG 2.2 AA target, keyboard and screen-reader acceptance tests. |
| CAP-47 | Full Pro analysis toolbox | QGIS/GRASS/Python ecosystem (requires task-level review) | Not a blanket parity claim; curate tested server/notebook tools for the scoped workflows. |
| CAP-48 | Enterprise operational diagnostics | Existing logs/health mechanisms | Unified correlation IDs, jobs, storage, permissions diagnostics and redacted support bundle. |

## 4. Alternative project decisions

**Kart, GeoGig, and the QGIS versioning plugin:** perform a focused spike against branch isolation, multi-layer atomicity, delete/update conflicts, geometry identity, server authorization, and history retention. A Git-like data workflow may be useful, but it cannot be declared a drop-in implementation of Esri's service-managed editing semantics. Reuse algorithms or choose an engine only after correctness and license gates. The new domain API remains the product contract even if storage internals change. [S15–S17, S20]

**G3W-SUITE and Lizmap:** evaluate publishing one real representative QGIS fixture through each. They are particularly relevant to avoiding needless work on project packaging and QGIS Server integration. Selection still must satisfy the product's catalog authority, REST, notebook, and branch requirements; keep a scored evaluation artifact rather than an impressionistic UI ranking. [S39–S40]

**pygeoapi:** evaluate for standards adapters if the selected GeoServer release lacks a required stable implementation. Do not introduce another catalog or expose its configuration as a second user workflow. [S41]

**Martin and TiTiler:** optional specialist serving engines behind existing contracts. They must earn additional deployment complexity through measured throughput, cost, or format capability, not architectural fashion. [S42–S43]

**GeoNetwork:** retain for organizations needing advanced catalog governance. Default metadata authoring stays in the product; requiring a second metadata application would reproduce the user's stated pain. [S25]

**QGIS core and PostgreSQL/PostGIS:** maintain source-owned forks and build the supported product from those sources. Initial algorithms may be unchanged, but source custody, patch capability and release authority are mandatory. A plugin or schema boundary is an implementation choice, not a ban on core changes. Optional compatibility with independently installed upstream QGIS is a separate tested profile, never the only supported publishing path.

**Koop:** a JavaScript toolkit that already exposes GeoServices/FeatureServer-style endpoints through providers and output plugins. Evaluate its `output-geoservices`, `featureserver` and query machinery before implementing the C1 facade from scratch. This is an important reuse candidate, not evidence of branch editing, full write compatibility, or secure integration with this design. The native typed API remains authoritative. Avoid unbounded dataset materialization or a second permission/cache model. Selection requires conformance, query-pushdown, licensing, maintenance and protected-route tests. No extra fork is authorized by default. [S44]

**MapServer:** a separate mature mapping-engine alternative with OGC services and MapCache. Compare it when map rendering, deployment footprint or supported formats justify another engine evaluation. Do not add a third renderer to the default distribution merely for completeness. [S45]

**Mapbender / QGIS2Mapbender:** browser-configured map applications and direct QGIS-project/QGIS Server publication provide an alternative end-to-end workflow to evaluate. They may reduce application/publishing work, but are not assumed to satisfy the unified branch, notebook and catalog requirements. [S46]

**QGIS Web Client / QWC Services:** existing authentication/permission, editing, full-text search and permalink components are useful comparisons for a QGIS-centered product. Evaluate their real setup and security boundaries alongside Lizmap/G3W; do not mistake a Docker example for a complete supported AmbisGIS distribution. [S47]

## 5. Evaluation scorecard and stop rules

For each selected component, produce an evidence sheet with supported release, security posture, license scope, API extension points, representative workflow result, test coverage, upgrade rehearsal, maintainer/patch burden, and replaceability. Score integration correctness and recoverability before cosmetic familiarity.

Stop a component adoption when its license prevents the required use, it exposes an unfixable authorization bypass, it cannot preserve source data faithfully, or its ownable maintenance burden exceeds demonstrated capacity. A large justified refactor or inability to merge an entire upstream release is not by itself disqualifying; AmbisGIS must demonstrate a safe patch or replacement path. Do not treat “we already forked it” as a reason to continue with a failing choice.
