# ADR 012 — Initial shared contracts and authority boundaries

Status: engineering proposal under final FND-06 review. The executed Koop
comparison and measured reuse decision are recorded in ADR013; no product API
or phase acceptance follows from this ADR. API-01 still owns the complete
OpenAPI specification before handlers.

## Context and decision

The accepted identity, branch, desktop and owned-build spikes establish useful
foundations, but do not define a complete shared product API. We retain one
versioned contract package in `ambisgis-platform/plan/contracts`, consumed by
the geodatabase, portal, notebook and desktop modules. The integrator controls
incompatible contract changes and migration order. Chapter 11 authority and
chapters 02–07 domain invariants remain controlling.

The catalog owns items, metadata, policy, service identity/active revision and
durable jobs. `ambisgis-geodb` owns typed schemas, feature identity, branches,
reconcile/post and audit. Product configuration belongs to the platform. Engine
configuration, caches and indexes are derived projections. A provider, corpus
fixture, translation layer or client cannot become another policy/schema owner.
Catalog object authorization must precede each read, including discovery,
metadata, count, extent, pagination and error paths. Unsupported policy modes
fail closed; field selection is not field authorization.

The four existing publication/edit/post/application starter envelopes remain
intact. New shared definitions describe identity, typed values and geometry;
new schemas cover a layer descriptor, bounded query, native errors, job status,
notebook execution request and application events. The machine-readable
`contract-package.json` maps every R01–R24 requirement to its original tasks and
tests, preserves all P0–P7 exit demonstrations and explicitly leaves product
acceptance open. It is a boundary index, not a new release lock or capability
authority.

## Bounded query experiment

The first executable contract profile is `fnd06-addresses-v1`: read-only Point
XY in EPSG:4326, UUID feature identity and a stable positive int32 ObjectID.
The provider uses real retained PostgreSQL/PostGIS state and the existing
catalog permission endpoint. It accepts only typed predicates, selected fields,
ordered keyset pagination, bbox, count and extent. Both service and data
revision are explicit. An unavailable revision fails; it never falls through
to current rows. Only immutable, retained revisions can back a page sequence.

Strings and identifiers have separate validation. Logical fields resolve via a
trusted schema mapping; values are database parameters. Null comparisons use
explicit `is_null`/`is_not_null` operators and ordinary SQL three-valued logic
elsewhere. Text ordering uses the database C collation, all sorts use NULLS
LAST, and a unique ObjectID resolves ties. Native decimal/int64 values use
strings; compatibility conversions need exact range/precision evidence.
No reprojection, Z/M flattening, empty geometry coercion or approximate CRS
transformation occurs in this profile. EPSG:2230 and broader corpus cases stay
required with explicit unsupported results until their implementations pass.

The shared validator and cursor helper are an executable contract prototype,
not production handlers or a policy cache. A cursor binds the entire normalized
query, immutable revisions, ordering position and authorization context with a
runtime HMAC key and a maximum five-minute lifetime. It conveys no permission.
Every page reauthorizes against the catalog. The current catalog endpoint returns
only allow/deny/unavailable: it does not expose policy revision or stable subject.
The spike may bind a credential-scope HMAC and an explicit live-check context;
it must not pretend this is a catalog policy revision. A credential change then
requires a new page sequence. Cursor integrity is not encryption; ordering
values must be visible under the same policy. Production key storage/rotation,
principal/revision policy APIs and general branch queries remain API/SEC work.

## Compatibility and reuse

Native APIs remain authoritative. C0 covers individually tested OGC operations;
C1 is a separately measured read facade; C2 calls native edit semantics; C3
remains optional and deferred. Native branch support is mandatory independently
of C3. No sync, federation, Esri token service or `isDataBranchVersioned=true`
claim follows from a native branch or FeatureServer-shaped response.

Before selecting a C1 encoder, FND-06 must execute the retained Koop packages
with an authorized bounded native provider. Measure query pushdown, pagination
under concurrent changes, actual output/error encodings, truthful metadata,
permission revocation/outage/cache isolation, limits and source/notices. A
FeatureServer success cannot establish MapServer export/legend/identify or named
proprietary-client interoperability. New bespoke encoding is deferred until the
measured adoption/rejection decision. Exact-version archive supplementation for
missing historical lock identities is recorded separately from original-lock
evidence and independently reviewed before package execution.

[ADR013](013-koop-query-codec-reuse.md) records that executed comparison and
selects the unchanged, retained query encoder behind the owned boundaries. Its
finite tested profile and remaining implementation/distribution obligations are
part of the decision; selection does not complete the C1 facade.

## Consequences and verification

Schema and semantic guard tests establish the boundary only. The actual Koop,
database and catalog experiment supplies its runtime evidence. Later API-01,
API-02/API-03, domain, browser, desktop, notebook and recovery tasks implement
the remaining routes and acceptance tests. Human-only pilot and manual
assistive-technology gates remain open. See [contract semantics](../docs/fnd-06-contracts.md),
[threat model](../docs/fnd-06-threat-model.md) and the unchanged
[complete requirement matrix](../docs/delivery-requirements-matrix.md).
