# 04 — Portal, metadata, maps, dashboards and applications

## 1. Backend reuse and frontend modernization

Adopt the selected GeoNode catalog/content source into the AmbisGIS-owned catalog. Its inherited model is the starting implementation, not an immutable external contract. Extend or refactor it directly as needed; own and test its migrations. There is one AmbisGIS item/metadata/permission authority, not a parallel product database competing with an independently administered GeoNode instance. Preserve useful inherited behavior while replacing redundant configuration and policy logic. [S06–S08]

Create a new coherent React/TypeScript shell and integrate MapStore using the GeoNode MapStore client and supported MapStore extensions. Pin compatible frontend dependency versions together; do not arbitrarily upgrade React in one repository while embedded modules require another version. A MapStore page inside an unexplained iframe is not the finished product experience. Use owned embedded/module interfaces with shared design tokens and explicit routing/auth boundaries. Inherited hooks may be changed jointly in the owned forks; upstream hook availability is not a veto on the required UX.

Existing MapStore dashboards are a meaningful starting point, not an absent feature. Reuse their widget and connection capabilities where suitable. Application contexts likewise reduce the work but do not satisfy a general responsive Experience-like composer automatically. [S09–S10]

## 2. Item model and lifecycle

Supported conceptual item types: dataset, service, style, web map, dashboard, application, notebook, file/document, registered data source, and version workspace. Some map directly to existing GeoNode resources; others are product extension models referring to those resources. Every item has immutable ID, type, title, summary, owner, tags, canonical metadata, extent/CRS when meaningful, thumbnail, revision, policy reference, lifecycle state, and dependencies.

Lifecycle is `draft -> validating -> published -> archived`, with explicit validation failure and deletion states. A published application references an immutable configuration revision. A mutable draft can be edited without changing public behavior. Deletion is tombstoned first and checks inbound dependencies. Reassigning an owner is an audited privileged operation and does not automatically expose private resources.

Content search indexes metadata visible to the requesting principal. Full-text snippets, counts, facets, thumbnails and related items must not leak private entries. PostgreSQL search is sufficient for initial scale; a dedicated search service is optional later and remains a rebuildable projection.

Dependencies distinguish dataset-to-service, service-to-map, map-to-dashboard/app, notebook-to-inputs/outputs, and style/font/image assets. A public map that references private data does not grant data access. The share dialog shows dependencies and requires a clear decision: keep restricted with an explicit viewer warning, change authorized sharing deliberately, or publish an approved derived output. Do not recursively make dependencies public.

## 3. User roles and permissions

Initial role templates: Viewer, Editor, Publisher, Data Steward, Notebook User, and Administrator. Roles are named bundles, not the entire policy model. Permissions distinguish discover, read metadata, read features, download source, edit features, create branch, edit branch, reconcile, post, publish service, change schema, manage sharing, run notebook, and administer infrastructure.

Group grants and item ownership interact through one policy evaluator. A branch's access cannot exceed underlying dataset access. A publisher does not automatically gain database administrator privileges. An app author cannot use a dashboard aggregate to bypass row/field restrictions. Public read may be granted intentionally without making edits or source downloads public.

Identity comes from OIDC. Catalog roles/groups are authoritative for resource policy; identity-provider groups may be mapped by an explicit synchronization policy. GeoFence/GeoServer ACL configuration is derived state, with automated setup and reconciliation. A user cannot add themselves to an administrative group by editing a profile field.

## 4. Product navigation and design system

Use persistent navigation and predictable page structures, with a global search, Publish action, job notifications, account menu and context help. The service details and portal-item details share components, preventing two different metadata/sharing experiences.

The design system defines typography, spacing, color contrast, focus behavior, compact/comfortable table density, consistent forms, error summaries, map tool affordances, loading/progress patterns and high-contrast theme support. Target WCAG 2.2 AA and verify keyboard navigation, visible focus, screen-reader names/status announcements, reduced motion and 200% zoom. Avoid automatic focus changes during map requests. Map content has an accessible feature table and text summaries, not only canvas interactions.

“Modern” is tested through tasks: a first-time administrator can publish a fixture without reading component-specific manuals; an editor can find and resolve an error; a keyboard user can configure a chart; a viewer understands why a private layer is unavailable. Cosmetic screenshots alone do not establish success.

## 5. Metadata workflow

A basic editor exposes title, summary, description, tags, contact, rights/license, source/lineage, access constraints and geographic/time coverage. Extent/CRS/schema are derived when available and marked as derived. A steward may correct descriptive text, but cannot mislabel stored coordinates by simply changing CRS metadata.

An advanced profile adds field descriptions, quality statements, lineage steps and chosen ISO mappings. Preserve the original uploaded metadata document and a structured mapping report. No standards validation claim is made merely because an XML file was emitted. A configured profile must have validation tests and representative exported records.

Only one metadata write API exists. GeoServer description fields, service capabilities, pycsw records and search documents update as projections. Conflicts use item revisions/ETags. Service status reports stale projection errors with retry; a projection failure must not create a second editable authoritative copy. [S02, S25–S26]

## 6. Web map contract

A web map stores a versioned declarative definition: coordinate system, initial view, layer references, style references, order/visibility, scale/time range, opacity, popup definitions, field aliases, filters, labels where supported, basemap attribution, bookmarks and interaction settings. References point to stable AmbisGIS service/layer IDs; transient signed URLs and credentials are never saved in map JSON.

The MapStore adapter converts the product contract into the selected MapStore representation and back only for fields explicitly supported. Preserve unknown configuration under a versioned extension namespace instead of dropping it. Schema migrations have old/new fixture tests. Do not claim ArcGIS Web Map JSON equivalence or automatic `.aprx` conversion.

Maps initially use native feature layers, WMS/map images, raster tiles and vector tiles with defined renderers. Layer-level capabilities control edit/time/legend/identify controls. Changing CRS, applying filters, and feature selection use shared contracts, not widget-specific hidden SQL.

## 7. Dashboard requirements

Reuse MapStore foundations for map, table, chart and counter widgets. Add AmbisGIS data-source bindings, sharing, draft/publish, responsive layout, and accessible configuration. Required chart types initially include bar, line and pie/donut where accessible tabular alternatives exist; KPI supports count/sum/average/min/max with a defined null/empty-data state.

Aggregation occurs through an authorized server API. Never download an unbounded dataset to count it in a browser. Debounce filter changes and cancel obsolete requests. Requests include data/style/revision context, and widget loading/error states distinguish no data, permission denied and service unavailable.

Cross-filtering uses a typed event contract with source widget ID, data-source ID, selected stable feature IDs or filter AST, time range and event lineage. Prevent loops and incompatible field joins. A chart selection does not silently apply a same-named but unrelated field filter to another dataset.

## 8. Application composer requirements

The first composer is deliberately constrained but genuinely useful. Required widgets: map, feature table, chart, KPI/counter, text, image with alt text, legend, layer list, search, filter controls, and basic action/button/navigation. Required layout: pages and named regions, desktop/tablet/mobile breakpoints, row/column or grid containers, padding, size constraints, and accessible reading order.

Support template selection, widget property forms, live preview, undo/redo, save draft, validate, publish revision and rollback. The same definition can be edited via a schema-aware JSON view for advanced users, but a JSON editor is not a substitute for the visual composer.

The event bus supports selection, filter, extent and time events. Widgets declare input/output schemas and supported data-source capabilities. All data flows through the authenticated query/aggregation client. Widgets cannot store service credentials. Keep content and presentation separate so a template can be reused against another compatible dataset after analyzer checks.

Third-party widgets are a later controlled extension mechanism: signed/versioned packages or administrator-installed trusted builds with a reviewed capability manifest. **No arbitrary user-supplied JavaScript, HTML script tags, npm packages or browser eval** in default apps. Rich text is sanitized, image URLs are validated, and user uploads never share executable origin privileges with the application shell.

This is not an Esri Experience Builder plugin host. No automatic import of Esri widgets, themes, app JSON or Arcade expressions is promised. The migration experience reports unsupported constructs and helps rebuild supported layouts.

## 9. Collaboration and publishing

Use optimistic editing revisions initially; concurrent app edits produce a meaningful conflict rather than last-write-wins. Real-time multi-user composition is optional later. Published apps pin configuration revisions while layer data may remain live according to their references; the UI must distinguish these concepts.

Publication validation checks missing widgets/assets, invalid bindings, circular event dependencies, inaccessible data, unsupported capabilities, mobile overflow, missing text alternatives and configured external links. Warnings may be acknowledged where safe; authorization or schema errors block publication. Preview runs under the author's credentials, and “preview as viewer/public” uses actual restricted authorization, not CSS hiding.

## 10. Acceptance journeys

A publisher imports a layer, creates a web map, builds a dashboard with map/table/KPI linked selection, then creates a responsive application from a template without touching GeoServer or Django settings. Sharing the app publicly leaves restricted data restricted. Revoking a group grant prevents new map, chart, table, tile and download requests. A mobile layout remains usable without overlapping controls. A keyboard user can complete the widget configuration flow. Restoring an earlier app revision does not corrupt the current draft or change service IDs.
