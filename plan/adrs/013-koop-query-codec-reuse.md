# ADR 013 — Reuse the retained Koop query encoder behind owned contracts

Status: measured engineering decision under final FND-06 review. Product
integration, release and complete C1 acceptance remain open.

## Decision and authority

Use the retained Koop GeoServices packages for the tested FeatureServer JSON
query encoding. Keep the typed query service, catalog authorization, revision
selection, limits and published capability profile in AmbisGIS modules. The
experiment gives concrete reuse evidence before developing a bespoke feature
encoder; its successful feature responses come from unchanged Koop code.

The selected source is `333518a19d43adf2fd12faed1a3be52d9c90dd3f`, tree
`3357f74aa588b18703f26cdb5b5a5f7809d7d150`: core 10.4.19, GeoServices output
8.1.25, FeatureServer 9.3.0 and Winnow 5.0.4. These are retained Class B inputs
under chapter 11, with exact production closure and source archives. They are
not independently moving product authorities. Permanent changes to inherited
code require a reviewed owned module and manifest change within the authorized
repository boundary. No additional GitHub repository is selected here.

This decision does not adopt Koop's default exposed routes, cache, advertised
capabilities or its query processing as a policy authority. The catalog remains
the only item/metadata/policy/service authority; `ambisgis-geodb` retains schema,
edit, branch, reconcile and post authority. ADR012 controls the shared contracts.

## Actual experiment

[Runtime evidence](../verification/fnd06-koop-runtime/evidence.json) binds the
executed implementation, contracts, retained inputs, original failed attempts,
raw HTTP responses, SQL plans and cleanup. Runtime005 uses
implementation `00036aaa099d2952856d083dc673d39815f8ed04`, shared contract
`a31a285b5e659a08bc6c18c393cfe5a8581bf293` and the reviewed corpus. It passes
227 assertions against 100,000 actual PostgreSQL/PostGIS rows and native GeoNode
policy/OAuth issuance. Runtime acceptance still requires the independent final
evidence review and aggregate FND-06 decision.

| Question | Measured result and consequence |
|---|---|
| Can existing code encode the native result? | Real FeatureServer JSON preserves tested UUIDs, positive int32 ObjectIDs, Unicode/null/empty strings, representable decimals, epoch-millisecond dates and Point XY coordinates. Correct provider field vocabulary and nullable metadata are required. The adapter supplies GeoJSON; Koop performs feature encoding. |
| Does work stay in the database? | Typed bound predicates, bbox, ordering, keyset/offset, count and extent execute in PostgreSQL/PostGIS. There are 29 recorded SQL queries with plans. Every observed feature fetch is at most page size plus one. All seven SQL attributes are fetched, then projected before Node; SQL projection pushdown is not demonstrated. |
| Are counts and extents complete? | Count/extent apply the complete authorized predicate rather than the feature page. Empty count is zero. The owned boundary projects an empty extent to null; raw and projected responses are retained separately. |
| Are pages consistent? | Native cursors preserve tie ordering and NULLS LAST; reject tampering, expiry, changed query/projection/resource/credential context; and reauthorize after revocation. Creating another data revision between page requests leaves the selected snapshot unchanged; this is not an insertion concurrent with an executing read. C1 offsets operate only within the explicitly selected immutable revision. |
| Is authorization effective? | Actual anonymous/private, two-user, group, missing-resource, revoke/restore and disabled-user cases run through native catalog checks. The final audit contains 108 catalog checks. Outage tests deny features/count/extent/metadata and add no SQL queries. The read role is denied INSERT/UPDATE/DELETE and catalog token-table reads. |
| Does inherited caching leak results? | An explicit no-cache implementation records zero inserts. Every request rechecks current policy. This demonstrates the evaluated configuration, not safety of the default cache or future tile/search caches. |
| Are parsing and failure boundaries exercised? | Real requests reject unsupported routes/parameters/encodings, forged internal headers, malformed UTF-8, duplicate inputs and over-budget pages. Native errors validate against the complete shared schema. A real conflicting database lock reaches its deadline and returns a safe limit error. |
| Are source and environment identities real? | Pre/post installed-code and catalog-origin checks match. The loopback-only supervisor and probes are retained; services and the database stop, fixture credentials are invalidated, and diagnostic secret checks report zero hits. This is private evaluation containment, not a hostile-tenant filesystem sandbox. |

The 29 SQL observations span approximately 4.33–18.75 ms in this one fixture run,
including the recorded query/plan work. They are not capacity measurements,
service-level objectives or deep-offset complexity claims. PostgreSQL may scan
an offset prefix; database work is not constant-time simply because transfer and
memory are bounded.

## Measured integration hazards and required controls

The first runtime stopped because the supplied logger omitted Koop's `silly`
method. The second failed twelve timestamp assertions: the adapter supplied
Esri output type names where Koop requires its provider vocabulary. Metadata
also exposed wrong types/nullability. The corrected adapter uses
Integer/Double/Date/GUID/String and explicit nullability. Those failures remain
failed receipts. Runtime003 passed its then-current assertions, but still had
incomplete native error envelopes; runtime004 adds the complete envelopes and
broader negative tests. Runtime005 also binds the extracted Node toolchain to
its retained archive and repeats the actual experiment. An earlier failed
offline-install verifier and rejected incomplete custody candidate are also preserved.

Actual unchanged-codec diagnostics show that a present `filtersApplied.where`
key with value false still suppresses the filter. The `all: true` shortcut also
skips conversion and can return GeoJSON-shaped features in the compatibility
envelope. The provider therefore supplies only explicit true flags for work
already performed by the validated native query, and never uses the all shortcut.
Neither flag is accepted from an external caller.

Inherited metadata advertises operations/formats beyond this provider. The owned
boundary allows only the inspected fields and tested per-operation capabilities,
JSON output, maximum page size 1,000, and no Z/M. It removes statistics, PBF,
GeoJSON and other unimplemented claims. The broad `supportsAdvancedQueries` flag
is omitted; explicit ordering/pagination flags describe this finite profile.
Discovery behavior in named clients remains untested.

The raw encoder's permission response uses compatibility code 400 and an
inaccessible-or-missing message. Native permission errors remain distinct 403
envelopes. The experiment verifies denial and safe existence behavior; it does
not equate these encodings or certify all ArcGIS error conventions. API-03 must
define and test the final per-route mappings against the named reference clients.

## Custody, licenses and security

[Custody evidence](../verification/fnd06-koop-custody/README.md) records exact
source, 238 retained archives and the derived production lock. Historical lock
entries missing integrity information are supplemented by retained exact-version
metadata; they are never represented as original-lock identities. The fresh
offline install verifies 213 registry packages and six source workspaces,
omits 39 optional-only packages, and executes no lifecycle hooks. The mandatory
closure is computed from reachability, including required/shared paths, rather
than trusting incomplete optional flags. Runtime then executes the independently
reviewed installed packages with the recorded isolation controls.

Koop's Apache-2.0 notices and the transitive notices remain required. The selected
geojson-validation package includes LGPL-3.0 obligations; retaining its source
and license does not certify a future installer or combined binary's compliance.

The exact tr46 0.0.3 archive lacks its full notice. Historical source equivalence
recovers a direct successor that adds only the MIT notice; all prior code is
identical. Its generated table reproduces byte for byte from retained Unicode
8.0.0 data, whose historical grant is also recovered. The [separate checked notice supplement](../docs/fnd-06-tr46-notice-supplement.md)
accompanies staged software and documentation, including the transformation
statement and retained rebuild inputs. Its exact commit `cb5a1a945bd94b80f2d52cc0faa6e0bf93303485`
has independent source/grant review, fourteen adversarial checks and an independently
reproduced stage whose own retained verifier passes. The missing-notice finding is
remedied for that exact supplement/layout. A product artifact must actually carry
those notices and source obligations; the original archive/lock remain unchanged
and broader distribution is not approved here.

The selected protobufjs version is in the affected range of
[GHSA-xq3m-2v4x-88gg](https://github.com/protobufjs/protobuf.js/security/advisories/GHSA-xq3m-2v4x-88gg).
This private JSON-only profile denies PBF/reflection routes and does not accept
attacker-selected protobuf schemas. This is a bounded mitigation, not a finding
that the dependency is unaffected. A product source/security disposition and
regressions remain required before enabling another path or shipping an artifact.
Native optional farmhash code is omitted; the reviewed pure-JavaScript path and
explicit stable ObjectIDs are used.

## Remaining implementation and acceptance

This is a private synthetic, object-policy-only, read-only Point XY/EPSG:4326
experiment. Each query explicitly supplies serviceRevision and dataRevision;
these extra prototype parameters are not a drop-in ArcGIS client contract.
Native keyset cursors and C1 resultOffset remain separate contracts. Production
revision discovery/binding, key rotation and lifecycle behavior require API work.

API-01/02/03 and their domain tasks still own the complete native API and C1
service directory, service descriptors, map export, legend/identify, supported
geometry/CRS/type combinations and named-client conformance. Date-only, large
integer, arbitrary decimal, Z/M/null/empty geometries, row/field policy, general
transforms, statistics, attachments, edits, sync and version protocols are not
implemented by this profile. Unsupported secure modes fail closed.

All original R01–R24 requirements, five product goals and P0–P7 exit demonstrations
remain in the shared contract index. FND-06's measured reuse decision does not
pass T-COMPAT-C1, T-AUTH-ALL, T-SEC-ABUSE or any full product journey. Source repair,
installation, desktop platforms, browser/accessibility, notebook isolation,
restore, human-only pilots and release gates remain with their original tasks.
