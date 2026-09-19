# 02 — Server product and service APIs

All GeoServer, GeoTools and GeoWebCache references below identify inherited code inside AmbisGIS-owned forks. Adapters are internal modules whose two ends the product controls, not a permanent dependency on externally evolving APIs. Service definitions, metadata and authorization have one authoritative product model. Remove redundant inherited ownership/configuration paths as specified in chapter 11.

## 1. Service manager and metadata UX

The service manager is a new AmbisGIS surface backed by the catalog and publishing API. It is not a cosmetic copy of GeoServer's configuration tree. Users see named services, type/capabilities, owner, sharing, health, source status, extent/CRS, active revision, edit policy, jobs, and metadata. Typical actions are Publish, Preview, Edit metadata, Configure sharing, Update, Stop, Start, Roll back, and Delete.

GeoServer's REST API remains an internal administrative mechanism for workspaces/stores/layers/styles. It does not establish the ArcGIS feature-data contract. [S01] GeoServer also has metadata support and an extension; those should be integrated rather than characterized as absent. [S02]

Metadata editing is available both on the portal item and on the service details screen. Both call the **same authoritative catalog API** with optimistic revision checks. Required fields are title, abstract, owner/contact, tags, rights/license/access constraints, geographic/temporal extent where known, source/lineage, CRS, field descriptions, and update frequency where relevant. Optional fields are progressive disclosure. Imported metadata that cannot be mapped is preserved as an original attachment, not silently discarded.

The product generates standard service metadata, basic feature-field descriptions, thumbnails, and citation/export formats from that record. Engine sync status is visible but users never install GeoNetwork merely to set a title or abstract. Advanced ISO profiles/harvesting are optional adapters. [S02, S25–S26]

## 2. Resource model

A `Service` has immutable UUID, stable URL slug, service kind, owner item ID, published layer IDs, capability profile, active revision ID, renderer, permission policy reference, data-source references, and status. A `ServiceRevision` is immutable and includes layer bindings, style/assets, schema fingerprint, CRS settings, metadata snapshot reference, engine descriptors, smoke-test result, and previous revision.

A `Layer` has an immutable UUID plus a stable numeric service-layer ID. That number is assigned once; reordering layers must not renumber endpoints. The underlying dataset ID and feature UUID namespace survive service overwrite. A layer alias is presentation, not identity. Deleting a layer that is used by a web map or relationship requires an explicit dependency resolution.

Use typed schema descriptors for integers, decimals, text length, date/time, booleans, UUID, coded values, nullability, geometry type/dimensions/SRID, and edit policy. Dates have explicit UTC/time-zone or date-only semantics; never infer all date fields are timestamps. Native JSON preserves large identifiers as strings when necessary; compatibility encoders enforce their documented numeric bounds.

## 3. Native API families

All routes below are **proposed contracts**. Initial JSON schema files are starter contracts, not a complete OpenAPI implementation. Implementation task API-01 creates the authoritative OpenAPI specification before handlers.

| Family | Representative route | Required behavior |
|---|---|---|
| Catalog | `GET /api/v1/items`, `GET/PATCH /api/v1/items/{id}` | Search/filter; conditional update; discoverability separate from data permission. |
| Metadata | `GET/PUT /api/v1/items/{id}/metadata` | One canonical record, validation, revision check, export links. |
| Service directory | `GET /api/v1/services`, `GET /api/v1/services/{id}` | Human and machine discovery; only visible resources. |
| Layer schema | `GET /api/v1/layers/{id}` | Accurate capabilities and field/domain/relationship schema. |
| Feature query | `POST /api/v1/layers/{id}/query` | Typed filter, geometry filter, CRS, field selection, sorting, keyset cursor, version/revision. |
| Feature read | `GET /api/v1/layers/{id}/features/{uuid}` | Branch-aware state, revision token, authorization. |
| Edits | `POST /api/v1/version-groups/{id}/apply-edits` | Atomic supported multi-layer edits; idempotency, expected head, per-feature revision. |
| Attachments | `POST /api/v1/uploads`, then edit attachment references | Staged immutable content; download authorization; atomic logical attachment changes. |
| Versions | `POST/GET /api/v1/version-groups/{id}/versions` | Owner/privacy, consistent base snapshot, bounded lifecycle. |
| Reconcile | `POST /api/v1/versions/{id}/reconcile` | Immutable three-way plan with captured source/target heads. |
| Resolve/accept | `PUT /api/v1/reconciles/{id}/resolutions`, `POST /api/v1/reconciles/{id}/accept` | Revision checks; no unresolved conflicts; accept candidate into branch only. |
| Post | `POST /api/v1/versions/{id}/post` | Accepted reconcile and expected heads; atomic target promotion after revalidation. |
| Maps | `POST /api/v1/services/{id}/export-map` | Authorized layers, renderer policy, bounded dimensions/DPI/time. |
| Tiles | `GET /api/v1/services/{id}/tiles/{z}/{x}/{y}` | Revision/policy-aware cache; correct tile scheme/content type. |
| Publications | `POST /api/v1/publications`, `GET .../{id}`, `POST .../{id}/cancel` | Durable job and state machine; private staging; safe cancellation. |
| Jobs | `GET /api/v1/jobs/{id}`, event stream/poll | Coarse status plus actionable diagnostics and support correlation ID. |
| Applications | `POST /api/v1/apps/{id}/publish` | Immutable app revision and dependencies checked at publish. |
| Notebooks | `POST /api/v1/notebooks/{id}/launch`, run/schedule APIs | Scoped execution and catalog integration; no privileged browser token. |

## 4. Query correctness

Use a typed filter AST with allow-listed operators and schema-validated fields. Compile to parameterized SQL. Never concatenate client `where`, sort, table, layer, or CRS strings into SQL. The compatibility parser accepts only its documented expression subset and returns a useful unsupported-expression error rather than stripping unsupported clauses.

Define null semantics, escaped strings, date handling, spatial predicate and input CRS explicitly. Apply server-side authorization filters **before** counts, statistics, pagination, exports, and aggregation. Feature counts and existence/extent can leak private information too. Pagination must preserve a consistent requested revision; opaque cursors contain signed query/revision context, not trusting client-supplied offsets as a security boundary.

Bounding-box candidates use spatial indexes followed by precise predicates where necessary. Define output field order, aliases, geometry winding, Z/M behavior, and empty geometry. Do not reproject or drop precision without an explicit request. Unknown or unavailable CRS transformations fail with an analyzer error. Include EPSG:2230 as a feet-based test fixture and verify transformation grids under the selected runtime; no assumption that one generic WGS84 transform is suitable for every dataset.

Set per-operation row, byte, geometry-complexity, execution-time, upload, and map-size limits. Exceeding a synchronous threshold returns an async export path or a clear limit error. Counts/statistics have independent limits and tests. All requested capabilities must appear in the service's tested profile.

## 5. ArcGIS compatibility tiers

The facade uses `/arcgis/rest/services/...` for familiarity, but is cleanly separated from native contracts. Implement from public documentation and authorized test observations; do not copy proprietary source or bundled SDK assets. [S20–S22]

**Reuse gate before implementation:** prototype Koop's GeoServices output with a provider backed by the authorized AmbisGIS query contract. Koop already implements relevant FeatureServer-shaped output; determine whether adopting its packages or a bounded internal adapter reduces work without losing database query pushdown, revision-consistent pagination, permission enforcement, error fidelity or resource limits. Document gaps and retain its required notices. A rejected reuse option needs measured evidence; an accepted option does not inherit a blanket compatibility claim. Keep edit/version integrity in `ambisgis-geodb`, never in a translation shim. [S44]

| Tier | Included | Explicit exclusions / gate |
|---|---|---|
| C0: native + standards | AmbisGIS API, selected WMS/WFS/WMTS/WCS/OGC Features capabilities | No Esri REST compatibility claim. |
| C1: read-oriented facade | Service directory; `MapServer`/`FeatureServer` descriptors for supported services; layer metadata; bounded `query`; map `export`; legend/identify subset | Tested exact parameters/encodings; no federation or blanket SDK compatibility. |
| C2: basic editable features | Tested add/update/delete or `applyEdits` subset; appropriate edit results; attachments/related records only when implemented | No sync replicas or Esri branch protocol. Never advertise unsupported rollback/global-ID behavior. |
| C3: optional version protocol | Exact scoped `VersionManagementServer` operations and related feature request behavior | Deferred until native engine is proven and independent conformance tests pass against named clients. |

Native branch support is a first-release requirement; **C3 is not**. Native clients may branch-edit through `/api/v1` while the ArcGIS facade remains DEFAULT-only and read-only or limited C2. Set `isDataBranchVersioned=false` in a compatibility service unless C3 behavior really exists. Likewise omit/disable sync, replicas, advanced editing, historic-moment, pagination, statistics, curves, and time capabilities until each is tested.

Conformance covers GET/POST form encoding, `f=json` and other promised outputs, errors and HTTP behavior expected by each client, Esri JSON geometry and spatial references, IDs, field domains, extents, record limits, query flags, output SR, and service-level edit atomicity. “The URL loads in a browser” is not a conformance test. An API schema cannot replace execution through a named desktop/web client.

Tokens and authentication are an additional compatibility problem. The native system uses OIDC. Do not imitate Esri Portal token generation or federation unless separately designed and tested. Public C1 read-only services can be tested first. Protected ArcGIS clients may require a supported OIDC/proxy integration; unsupported authentication must be documented rather than weakening access controls.

## 6. OGC and raster boundaries

Expose only selected, tested OGC conformance classes. GeoServer's Features extension and other OGC API modules have different release maturity; verify the chosen tuple. OGC Features Part 1 is a read/query standard, not complete edit/versioning semantics. [S05, S24]

Public gateway requests are parsed and normalized, not blindly forwarded to arbitrary workspaces. Deny unrestricted WFS-T writes; native versioned data is writable only through the feature API. Raw internal endpoints are network-isolated and authenticated; a forwarded user header from the internet is never trusted.

Raster coverage downloads, rendered raster maps, raster tile images, and vector tiles are distinct products. A PNG tiled rendering does not preserve original scientific pixel values. Coverage exports report resolution, band mapping, nodata, CRS and resampling. Support fixed visualization presets first; time/mosaic selection later within the same service model. Full Esri ImageServer query/function/analytics behavior is excluded initially. [S04, S43]

A vector tile service includes tile metadata, a supported style document, sprites/glyph assets, attribution, extents, zoom range, and cache policy. GeoServer's vector output is a foundation, not by itself an Esri VectorTileServer clone. [S03]

## 7. Authorization, errors, and observability

Every route checks operation, item/data, branch, and field/row policy as applicable. Rendering and tile services must not bypass rules enforced by feature queries. V1 can prohibit raster/map publication of a row-filtered service until an equivalent secure render projection is implemented; rejecting unsupported secure rendering is safer than leaking the layer.

Use stable native error codes such as `UNSUPPORTED_CAPABILITY`, `SCHEMA_MISMATCH`, `STALE_BRANCH_HEAD`, `STALE_RECONCILE`, `CONFLICTS_UNRESOLVED`, `PUBLICATION_FAILED`, and `TRANSFORM_UNAVAILABLE`. Return remediation fields and a correlation ID, never SQL credentials or internal paths. Compatibility errors map to documented client expectations without hiding failure.

Log request ID, principal pseudonymous ID, operation, resource IDs, revision IDs, duration, rows/bytes, and result classification. Redact tokens and sensitive queries. Metrics include query/map/tiles latency, error rate, queue age, engine availability, and authorization-denial spikes. Health endpoints distinguish process liveness from ability to serve an authorized fixture.

## 8. Acceptance examples

A publisher creates a layer, edits metadata once, and sees consistent text in the portal, native API, and supported service capabilities. Reorder does not change numeric endpoint IDs. An unprivileged user cannot enumerate private items or infer their counts via a statistics route. An edit retries after a timeout and returns the original result rather than duplicating inserts. A disabled capability returns an explicit error in both native and compatibility clients. A GeoServer failure leaves the prior published revision usable and visible in product diagnostics.
