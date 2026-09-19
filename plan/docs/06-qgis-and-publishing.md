# 06 — QGIS integration and publication lifecycle

## 1. Desktop strategy

Maintain the `ambisgis-qgis` source fork and an AmbisGIS-controlled desktop/server distribution. Develop the publishing and branch client in `ambisgis-qgis-plugin` and bundle it into the supported desktop build. The plugin supplies sign-in, catalog, publication, progress, service loading and constrained branch editing. Preserve useful QGIS authoring capabilities; source ownership does not require rewriting them. Core changes are permitted where they improve product behavior, with regression and migration evidence.

P0 selects one tested QGIS desktop/server family and records the Python/Qt API boundary. Do not assume a plugin built for one major QGIS/Qt generation works unmodified in another. Windows and Linux desktop builds are separate acceptance targets; macOS is added only after an actual packaging/test runner is available. After license/trademark review, desktop branding may apply to the owned distribution and bundled workflows with explicit QGIS-derived attribution. A separately installed upstream QGIS plus plugin is an optional compatibility profile, not a required product dependency. No branding may claim AmbisGIS originally authored the inherited engine.

For branch editing, use a controlled plugin edit-session adapter: read an authorized snapshot into a local edit buffer/temporary working layer, capture edits with stable feature UUID and base revision, validate and submit through the native API, then refresh. Do not enable direct PostgreSQL writes on managed branch tables. Provider-level seamless editing can follow after the basic edit-session protocol is proven. Local working files are not an offline replica/sync guarantee.

## 2. Publish wizard

One primary action: **Publish to AmbisGIS**. Sequence:

1. Select account/deployment, destination folder, title and layers/project.
2. Choose outputs: dynamic map, editable feature service where supported, raster tiles, vector tiles, coverage download where supported. Explain whether data will be copied or reference a registered server-accessible source.
3. Run analyzer: schema/CRS, geometry, source access, styles/fonts, rights, data volume, service capabilities, dependencies, and resource estimates.
4. Enter/review metadata and sharing. Default new content to private. Confirm edit and branch policy separately from view sharing.
5. Publish and show durable job progress, warnings, retry/cancel controls, resulting item/service URLs, and Add to map.

An experienced publisher should not create GeoServer workspaces/stores, configure pycsw, register OAuth clients, or manually synchronize permissions. Advanced options are optional and understandable at the service level.

## 3. Copy versus reference

**Copy** uploads a bounded package or streams a registered local export into managed storage. The server owns the resulting dataset lifecycle and can offer supported geodatabase semantics. A vector publication can use GeoPackage or another validated interchange format; the server inspects schema rather than trusting extension names.

**Reference** points to an administrator-registered server-accessible database, file source, or approved remote service. The client passes a source ID and allowed dataset reference, not plaintext credentials or arbitrary server filesystem paths. A read-only external reference is not automatically eligible for AmbisGIS branch editing. To version-edit it, migrate/register it as a managed dataset through an explicit conversion process.

The analyzer explains this difference before publishing. Reference connection failure produces a diagnostic without revealing credentials. Source registration restricts network destinations and database privileges. Server-side import jobs do not connect to arbitrary URLs supplied by an untrusted publisher.

## 4. Cartographic fidelity and renderers

Support two renderer paths under one service identity:

- **GeoServer:** general serving with the product's tested style subset. Analyze QGIS-to-SLD/style translation and list unsupported label expressions, symbol effects, blend modes, layout features, fonts and plugins. Never silently flatten important styling and call it parity.
- **QGIS Server:** package the project/assets and use a pinned compatible server renderer when faithful QGIS rendering is required. Shared rendering libraries provide the right foundation, but fonts, server settings, providers, paths and versions still require fixture testing. [S11–S12]

Default renderer selection is based on a capability analyzer, with a visible explanation and override where valid. Metadata, sharing, URLs, logging and rollback stay identical whichever renderer is chosen. The user is not forced to administer a second GIS product.

Do not execute project macros, Python expressions/functions from untrusted uploads, arbitrary plugins or uncontrolled network references on the server. Only approved expression/provider capabilities are enabled. Reject or strip with explicit consent and a report; silent execution is not an option.

## 5. Publication manifest and assets

The proposed `contracts/publication.schema.json` defines the initial envelope: schema version, item title, upload/registered-source reference, requested outputs, renderer preference, metadata, sharing, stable layer references, and overwrite target where applicable. The full implementation adds schema-checked renderer options and analyzer results through additive versioned changes.

Package manifests list asset hashes, lengths, media types, relative paths, source CRS, data schema fingerprints, styling dependencies, font licensing declarations and transformation-grid requirements. Rebase local paths to a sandbox root. Reject path traversal, symlinks escaping the package, nested archive bombs, unsupported MIME signatures and excessive uncompressed size. Never accept embedded credentials in QGIS datasource strings; redact and replace with server-side source references.

Preserve original data separately where retention allows. Imported geometries and attributes undergo fidelity checks including Unicode, decimal/date semantics, nulls, domains, relationships, and Z/M. GDAL's OpenFileGDB driver offers more than read-only access, but that does not guarantee complete migration of enterprise-geodatabase behaviors, attribute rules or versions. Produce a conversion report for every unsupported construct. [S27]

## 6. Durable state machine

```text
CREATED -> UPLOADING -> SCANNING -> ANALYZING -> AWAITING_CONFIRMATION
        -> STAGING_DATA -> BUILDING_SCHEMA -> BUILDING_STYLES
        -> CONFIGURING_SERVICES -> BUILDING_TILES (when requested)
        -> VERIFYING -> READY_TO_ACTIVATE -> ACTIVE

Before activation: failure/cancel -> COMPENSATING -> FAILED/CANCELLED
After activation: explicit rollback -> prior revision or a new corrective revision
```

Persist every step's inputs, idempotency key, allocated resource IDs, completion record and retry policy. A worker queue message wakes a job; it does not define its state. Lease jobs with heartbeats and reclaim abandoned work safely. Retries inspect step completion before creating resources again.

All staged stores/layers/items/URLs are **private and unlisted**. Allocate stable product IDs separately from temporary engine names. Validate source data, engine output, metadata and authorization through the gateway. Only then switch the active service-revision pointer and publish the catalog item under the requested policy.

There is no cross-component database transaction. Use compensating actions to delete only resources created by this job, identified by immutable ownership tags. Failure must not delete an existing shared data store, overwrite a previous style, or remove another job's staging directory. Keep a recovery record when cleanup cannot complete, and expose that condition to administrators.

## 7. Atomic activation and stable URLs

Activation is a small catalog transaction updating a service's active revision pointer and item state after all prerequisite artifacts are available. The gateway resolves each request to a single immutable revision. Private staged revisions are not addressable by guessing a URL. Engine names include the publication revision so in-place GeoServer reloads do not corrupt the previous active service.

Overwrite preserves item UUID, service URL slug, numeric layer IDs, feature identity mapping and compatible dependent references. Layer order is independent of numeric ID. The analyzer compares schema/geometry/CRS, domains, capabilities and map/app/notebook/branch dependencies. Breaking changes require a new service or a reviewed migration plan; they cannot sneak through an “overwrite” checkbox.

Rollback changes the active pointer back to a retained verified revision after permission/data-compatibility checks. It does not pretend to undo unrelated edits to a shared live dataset. Distinguish **configuration rollback**, **publication-data snapshot rollback**, and **feature edit history** in the UI. A renderer revision may point to live DEFAULT data, so restoring a style revision does not restore past feature values.

## 8. Raster, map and vector-tile outputs

Dynamic maps render on request. Raster map tiles cache rendered images under a gridset/zoom scheme. Raster data/coverage exports preserve explicit pixel/band semantics. Vector tiles contain generalized features and need style/glyph/sprite metadata to form a usable map. These are separate checkbox choices with separate validation and storage implications.

For raster assets, inspect georeferencing, dimensions, band types, nodata, overviews, CRS, color interpretation and statistics. Missing CRS is an error requiring user input, not a guess. COG conversion is a chosen delivery optimization, not a license to change numeric data silently. Mosaic/time-series support is a later scoped increment built on GeoServer's foundations. [S04, S43]

For tiles, bound extent, zoom range, formats and estimated tile count/storage. Require approval above configured limits; do not seed an unbounded world at maximum zoom. Use incremental/cancellable jobs. Private/row-filtered tiles need policy-aware separation or are disabled until safe. Cache identity includes data revision, style, grid, output format and authorization scope. New feature edits trigger revision invalidation rules, never a permanently stale anonymous cache entry.

## 9. CRS and fidelity acceptance

Tests include geographic degrees, meter-based projected coordinates, EPSG:2230 feet-based data, antimeridian behavior where supported, nondefault axis order in OGC requests, null/empty geometry, Z/M, and unavailable transformation grids. Define transform accuracy policies and whether the operation is horizontal-only or includes vertical datum handling. Avoid “reproject to WGS84” as a universal hidden normalizer.

Visual regression compares QGIS desktop and QGIS Server renders with controlled fonts/assets/view extent, then checks the selected GeoServer translation subset separately. Use pixel tolerances and semantic feature checks rather than claiming all anti-aliasing must be identical. Record unsupported symbols and label expressions in the capability matrix. Raster tests verify sample values for coverage outputs and intended resampling for visual outputs.

## 10. Desktop editing and migration boundaries

The plugin's version panel lists only authorized branches, shows base/head information, opens the edit buffer, submits transaction batches, reviews conflicts and invokes reconcile/accept/post. Editing a stale buffer produces a conflict prompt rather than replaying against a new head automatically. Clearing a local buffer after successful submission is contingent on server confirmation or verified idempotency result.

ArcGIS Pro can be considered an external standards/compatibility client in a named test profile. Native Pro publishing and `.sd` execution are not supported by this design. Migration from ArcGIS should use authorized data exports, metadata/style conversion reports and manual rebuilding where semantics differ; never connect a new service directly to Esri's internal version tables or treat a SQL latest-row view as an authoritative branch state.

## 11. Acceptance journeys

Publish synthetic addresses, roads, a raster and a rich-style QGIS project. Obtain map/feature/raster-tile/vector-tile services as applicable without touching upstream administration. Interrupt upload, kill the worker during engine configuration, retry a completed request, cancel tile seeding, overwrite a service, and roll back configuration. In every case verify no duplicate services, leaked private staging data, lost previous service, renumbered layers or corrupted source dataset.
