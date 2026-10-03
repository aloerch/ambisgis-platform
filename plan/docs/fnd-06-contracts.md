# FND-06 shared contract semantics

These initial contracts are under engineering review. Schemas validate envelopes;
they do not implement a server or grant capabilities. API-01 creates the complete
OpenAPI specification, generated clients, request/response contracts and version
policy before production handlers. Existing v1 starter payloads remain accepted
by package checks. Incompatible changes require a new contract version and a
coordinated consumer migration, not silently permissive parsing.

## Authoritative boundaries

| Boundary | Authority and contract | Required behavior |
|---|---|---|
| Authentication | Configured OIDC provider; verified server-side session/credential | Issuer, audience, expiry and flow checks; no caller-supplied identity headers. Existing opaque-token spike is bounded evidence, not complete OIDC product acceptance. |
| Catalog/metadata/sharing | Owned GeoNode extension | One item UUID and optimistic metadata revision; discover, metadata read and feature read are separate permissions. Original imported metadata is retained as an attachment. |
| Services | Catalog service registry; `layer.schema.json` | Stable service UUID/slug, layer UUID and numeric layer ID; immutable service revisions; dataset namespace survives overwrite. A descriptor references schema authority, never creates a second schema. |
| Features/schema/versions | `ambisgis-geodb`; query/edit/post envelopes | Typed values and constraints, stable feature UUID and ObjectID mapping, explicit schema/data revision and branch head. No direct SQL/WFS-T/notebook writes to managed branches. |
| Publication/jobs | Catalog durable records; publication/job envelopes | Private staging, step idempotency and ownership, safe activation, compensation and retry. Queue delivery is only a wake-up. |
| Apps/maps/dashboard | Catalog app revisions; application/app-event envelopes | Declarative registry-validated widgets, authorized data-source operations and dependencies; publishing a public app never grants its data permissions. |
| Notebooks | Catalog notebook/environment/run records; notebook-run envelope | Isolated origin/runtime, exact source/environment/input revisions, scoped execution and publication through the same saga. No credentials in notebook/app JSON. |
| Configuration/assets | Platform configuration; content-addressed blobs with manifests | One configuration authority; immutable verified assets. Render/cache/search state is disposable and revocable. |

Object UUIDs are not authorization tokens. Names/aliases are presentation. Layer
numbers are assigned once and never recomputed from display order. Native large
integer IDs use decimal strings where necessary; the initial C1 experiment uses
only positive int32 ObjectIDs. No silent rounding to JavaScript number precision.
Decimal literals are base-10 strings with declared precision/scale. Date-only
values remain dates; timestamps require a zone and are compared as instants.
Field nullability differs from an omitted edit field. Geometries declare type,
SRID and XY/XYZ/XYM/XYZM; no silent dimension loss.

## Native query profile used by the Koop experiment

`native-query.schema.json` plus `tools/native_contracts.py` define the bounded
`fnd06-addresses-v1` provider input. The example layer binds synthetic identities;
these are fixture IDs, not invented live catalog IDs. Runtime bindings must use
the actual created synthetic catalog resource and record that mapping.

Required request context is schema version, layer UUID, service revision, data
revision and result mode (`features`, `count`, `extent`). Only the following
optional inputs are accepted:

- `filter`: typed `eq/ne/lt/le/gt/ge`, explicit null tests, `and/or`. At most
  eight expression levels, 128 nodes and 16 children per Boolean node. UUID and
  Boolean ordering predicates are unsupported. Unknown operators/fields fail.
- `bbox`: `[xmin,ymin,xmax,ymax]` in EPSG:4326, finite coordinates within the
  geographic ranges, inclusive point intersection. Antimeridian-wrapped bounds
  are unsupported. Spatial index candidates must still meet exact predicates.
- Feature projection: unique logical field names in requested order; absent
  selection means declared schema order. Native UUID identity remains the
  feature envelope identity even when omitted from selected attributes. Geometry
  is always Point XY in this profile; null/empty/Z/M and other types fail closed.
- Feature ordering: up to three non-unique fields plus the unique ObjectID
  tie-breaker, or a declared order already ending in ObjectID. C collation,
  NULLS LAST for both directions; ordered columns and cursor values share types.
- Feature page size: 1–1,000, default 100. An opaque native keyset cursor binds
  query/revisions, page size, projection, sort, principal context and expiry.
  Count/extent requests reject projection, order, page size and cursor.
- `output_crs`: EPSG:4326 only. EPSG:2230 is reserved in shared CRS definitions
  for the required corpus; this profile returns `TRANSFORM_UNAVAILABLE` instead
  of an approximate transform or relabelled coordinates.

The complete JSON request has a 32-KiB validation budget. HTTP body/decompression,
SQL time/connection, result-byte and response limits must also be enforced at
their real boundaries in the experiment. These validation limits alone do not
bound an HTTP server or database. Values remain parameters, including strings
containing SQL-looking text; identifiers resolve from trusted schema mappings.
Unknown compatibility clauses are rejected, never stripped to broaden a query.

All modes apply the same current authorization and predicate before aggregation
or pagination. The initial policy profile supports catalog object permission
only. Declaring row/field policy returns `UNSUPPORTED_CAPABILITY`; projection
allowlists cannot masquerade as row/field policy. Counts/extent describe the full
authorized result, not merely the current page. Empty results have count zero
and null extent. Compatibility output adapters must test those exact semantics.

Dataset revisions are immutable snapshots for the experiment. Mutation creates
a distinct revision; old pages either retain their exact snapshot or receive
`REVISION_UNAVAILABLE`. A C1 `resultOffset` can only be adapted within an explicit
immutable revision. It is not the native pagination contract or an authorization
boundary. Measure ties, new revisions created between page requests, changed
query/identity/revision, expiry and tampering. Simultaneous read/write and general
concurrent-edit tests remain required in the later API/database tasks. The
database role is read-only on snapshots and cannot write
managed branches. The ephemeral fixture loader is a separate controlled role.

The existing catalog read probe returns HTTP 204/403/503 and carries no stable
subject or policy revision. The provider must reauthorize every request and use
no positive permission/data cache. A cursor may bind a runtime-keyed credential
scope and the explicit `live-catalog-object-check-v1` context. This is not a
fabricated policy revision; changing credentials starts a new sequence. HMAC
keys remain generated private runtime material, not source defaults. Cursor
contents are integrity-protected, not encrypted or independently authorized.

## Errors and capability profiles

Native errors carry a stable code, safe message, correlation UUID, retryability
and remediation category. Never include SQL, credentials, private paths, request
contents or backend traces. Error existence policy must be consistent: private
and nonexistent resources use the same unauthorized response. Actual native
HTTP status mapping and C1 error fidelity are API-01/API-03 contracts; they must
be tested through the facade, not inferred from a schema.

The experiment distinguishes an unavailable policy authority (`POLICY_UNAVAILABLE`)
from an unavailable database/provider dependency (`BACKEND_UNAVAILABLE`). A
transient dependency outage returns native HTTP 503 with `retryable: true` and
`remediation: retry_later`. An unexpected persistent backend fault uses a safe
message, `retryable: false` and `contact_operator`; it never promises that retrying
will repair a fault. Executed statement/lock budgets use `LIMIT_EXCEEDED`.
All native error paths require the complete versioned envelope and a generated
correlation UUID. Compatibility errors use their separately tested output shape;
they must not expose backend exceptions or weaken authorization.

Advertised capabilities come from a tested per-service profile. Omit or reject
operations/encodings not executed. A C1 facade must guard discovery, metadata,
query and direct backend routes, not only a provider callback. Koop's default
capabilities/cache/auth routes are review targets, not accepted product defaults.
C0 selected OGC operations, C1 read operations, C2 edits and optional C3 version
protocol remain distinct; native branches never imply C3 or sync support.

## Writes, jobs and lifecycle

Existing `edit-request.schema.json` requires group/branch IDs, expected head,
idempotency key and atomic operations. Updates/deletes carry feature revision
tokens. The geodatabase validates types/domains/relationships and complete
candidate state in the transaction. Idempotency binds actor, operation scope
and payload digest; a repeated key with changed payload fails. Clients only
clear edit buffers after a confirmed response or verified idempotent result.

Reconcile captures base/source/target heads and schema/rule revisions; explicit
resolutions revise that immutable plan. Accept applies the resolved candidate
to the branch only. Post uses the accepted plan, its resolution revision and
both expected heads, checks current post permission, locks/revalidates constraints
and atomically advances DEFAULT. Stale heads/acceptance fail with the named
native errors. No compatibility adapter owns or weakens these transactions.

The publication envelope retains upload/registered-source references, desired
outputs, renderer, metadata, sharing and stable overwrite bindings. Its durable
stages are exactly chapter 06: CREATED, UPLOADING, SCANNING, ANALYZING,
AWAITING_CONFIRMATION, STAGING_DATA, BUILDING_SCHEMA, BUILDING_STYLES,
CONFIGURING_SERVICES, optional BUILDING_TILES, VERIFYING, READY_TO_ACTIVATE,
ACTIVE; preactivation failure/cancel enters COMPENSATING then FAILED/CANCELLED.
`job.schema.json` gives the coarse job status plus the exact publication stage.
The schema rejects successful publication before ACTIVE. It does not execute
transitions or certify crash recovery. A durable implementation must persist
step inputs/completion, payload digest, leases and resource ownership; retries
inspect those records. Compensation never deletes another job's/shared resource.

Activation changes one catalog active-revision pointer after source, output,
metadata and permission verification. In-flight requests resolve a single
revision. Failed overwrite preserves the previous active service and stable
layer IDs. After activation, rollback is explicit to a retained revision or a
corrective publication, not preactivation cleanup. PUB-01/PUB-02/SRV/QGIS tasks
retain actual cancel/crash/retry/overwrite acceptance.

## Applications and notebook execution

The existing application envelope still requires widget-specific registry
validation, referential integrity, sanitized content and responsive semantics.
`app-event.schema.json` defines selection, filter, extent and time payloads;
server/client registries must check source/target/data-source membership and
capabilities, time ordering and revocation. It does not allow code or credentials.
Every table/chart/KPI uses the authenticated query/aggregation client; a public
layout does not recursively publish restricted dependencies. Immutable published
configuration and a mutable draft have distinct revisions and rollback rules.

The notebook-run envelope pins notebook revision, environment and package-lock
digests, SDK version, input revisions, typed parameters, declared read/publish
targets, timeout and idempotency key. Zero digests in the example are synthetic
placeholders and must never be accepted as a real retained environment. The
server validates actual custody, compatible SDK/environment, input membership,
current permissions and quotas. Execution identity is server-established, never
accepted from this request. A run record adds actual start/end, execution scope,
cell progress, resource use, sanitized failures, output digests and publication
job references. Scheduled execution separately records timezone, concurrency,
DST missed/duplicate behavior and retention. None of these schemas supplies a
scheduler or notebook isolation; NB-01–NB-05 retain their real tests.

## Verification and remaining work

The original five product goals retain their complete acceptance families:

| Goal | Original requirements | Required product acceptance tests |
|---|---|---|
| Service and metadata administration | R01–R03 | T-INSTALL-01, T-SRV-01, T-API-01, T-QUERY-01, T-COMPAT-C1, T-META-01 |
| Managed geodatabase and branch editing | R04–R07 | T-DB-SCHEMA, T-DB-IDENTITY, T-EDIT-01, T-EDIT-RETRY, T-VERSION-SNAPSHOT, T-VERSION-ORACLE, T-VERSION-RACE, T-VERSION-POST, T-VERSION-RECOVERY |
| Modern portal, maps, dashboards and apps | R08–R10 | T-PORTAL-01, T-A11Y-01, T-WEBMAP-01, T-DASHBOARD-01, T-APP-01, T-APP-SHARING |
| Integrated spatial notebooks | R11–R13 | T-NB-ISOLATION, T-NB-ENV, T-SDK-01, T-NB-PUBLISH, T-NB-SCHEDULE |
| QGIS publication | R14–R17 | T-QGIS-PUBLISH, T-PUBLISH-CRASH, T-TILES-01, T-RASTER-01, T-CARTO-01, T-INGEST-01, T-OVERWRITE-01 |

Cross-cutting R18–R24 retain authorization, recovery, release, source ownership,
independent maintenance, consolidation and Project evidence. The machine-checked
index preserves each original goal ID, task mapping and test family. Its initial
review/status text is a frozen input snapshot, not a command to reset live task
progress; the delivery ledger and accepted ADRs record subsequent decisions.

The initial tests exercise schema examples, typed-query rejection/normalization,
cursor integrity and complete requirement/phase mapping. Every original
requirement, task mapping and named test family remains in `contract-package.json`.
No product test family changes to passed from these checks. The reviewed corpus
and [measured Koop decision](../adrs/013-koop-query-codec-reuse.md) have separate
native/runtime evidence. API-01/02/03,
domain and journey tasks remain necessary, including Windows/Linux desktop,
manual accessibility, representative-user pilots, installation/restore/upgrade,
disconnected repair and release artifacts.
