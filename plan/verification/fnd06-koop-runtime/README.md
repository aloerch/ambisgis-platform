# FND-06: actual bounded Koop reuse experiment

[evidence.json](evidence.json) binds the completed private `runtime-005` attempt,
its exact executable inputs, raw responses, SQL observations, cleanup and earlier
attempts. The implementation executed at
`00036aaa099d2952856d083dc673d39815f8ed04`. This is a source reuse experiment for
FND-06, not production C1 acceptance, named-client qualification or distribution
approval. The integrator owns the architectural decision in ADR-013.

The unchanged retained Koop source is
[`333518a19d43adf2fd12faed1a3be52d9c90dd3f`](https://github.com/koopjs/koop/tree/333518a19d43adf2fd12faed1a3be52d9c90dd3f):
core 10.4.19, GeoServices output 8.1.25, FeatureServer 9.3.0, Winnow 5.0.4,
cache-memory 6.0.0 and logger 5.0.0. Candidate002 retains the complete selected
production closure. Fresh `install-002` used the reviewed installer with
`npm ci --offline --ignore-scripts --omit=dev --omit=optional --no-audit --no-fund`.
Its 213 registry packages, six workspaces, 4,187 installed registry files and
447 source files passed byte checks. Thirty-nine optional-only install paths
are omitted; their archives remain retained. No lifecycle ran or dependency
version floated. The runtime independently checks all 4,706 extracted Node
24.18.1 archive entries, including bytes, modes and links, before and after use.

The first-party Python provider consumes the exact shared contract checkpoint
`a31a285b5e659a08bc6c18c393cfe5a8581bf293`. Every consumed schema, validator and
layer example is checked against its Git blob. The selected 100,000-row corpus is
the actual generated `round-005/scale-100000` output from corpus checkpoint
`c0983e6898b991a16c62dab066a9f40ded88c155`; its manifest digest is
`5aeb5aad8a0f47780fdcba69bc6b568689bb14dc6b30927fa1e14b6796e06a88`.
Payload hashes and streaming row counts are checked before loading. Elevations
are parsed directly from JSON text as Decimal and loaded into PostgreSQL numeric.
The owned PostgreSQL 15.19/PostGIS 3.5.7 fixture and actual owned GeoNode catalog
have separate loader, runtime and read-only query roles. The query role cannot
insert, update or delete snapshots, or read the catalog token table. Actual
catalog resource UUIDs are retained in `fixture.json`; descriptor IDs are synthetic
fixture identities, not invented live service registrations.

The final journey passed **227 assertions**. Native GeoNode authorization-code
flows with PKCE issued the test credentials. The completed artifacts contain
108 current catalog checks, 29 SQL statements and 53 raw Koop responses, with no
cache insertions. The connection, statement and EXPLAIN observation elapsed
times ranged from 4.33 to 18.75 ms (median 7.61 ms)
in this one local 100,000-row run. The maximum fetched result was 101 rows: a
100-row page and one lookahead. These observations are not a production capacity
claim. `tests.json` captures some counters before the final outage probes;
`evidence.json` recomputes final totals from the completed files.

The real assertions cover typed filters, inclusive bounding boxes, count and
extent over the entire authorized predicate, null versus empty text, Unicode,
GUID/ObjectID stability, numeric values, epoch-millisecond date output, projected
fields, empty and final pages, and mixed-direction native keyset semantics with
NULLS LAST and a unique tie-breaker. Cursor tampering, expiry, changed query,
projection, resource, credentials and revision fail. Both credential principals
in the isolation case have permission: the outsider owns the group resource.
The final evidence verifier specifically requires its recorded INVALID_CURSOR
400 response, rather than treating an authorization denial as cursor proof.
Creating a different data revision preserves old snapshot pages.

Every native query checks the real catalog before cursor/data processing. Group
removal, public revocation and disabled users take effect without a positive
cache. Stopping the actual catalog process causes feature, count, extent and
metadata requests to fail closed; the SQL count does not increase. Genuine SQL
lock contention exercises the configured deadline. Native JSON errors validate
against the complete shared error schema. Unsupported HTTP methods have safe
errors; HEAD is rejected with an empty body. Strict UTF-8, malformed form escapes,
duplicate parameters, overlong credentials, oversized/compressed bodies, spoofed
internal headers and missing private backend keys have actual negative tests.

Koop still performs feature encoding. Of 53 raw responses, only two change at
the owned boundary: a closed metadata projection and empty extent normalization
to null. No feature attributes or geometries are replaced by an owned C1 encoder.
The correct provider type vocabulary (`Integer`, `GUID`, `Double`, capitalized
`Date`, etc.) produces the expected seven-field Esri schema and date conversion.
The raw metadata defaults are retained for comparison. The projection advertises
JSON and the tested individual read operations; it omits the broad
`supportsAdvancedQueries` claim. Default token issuance, rest-info discovery,
MapServer, renderer/statistics, related-record and PBF/GeoJSON output routes are
unavailable. Named-client discovery compatibility remains unqualified.

Actual calls to the unchanged codec separately confirm that a false
`filtersApplied.where` still removes the predicate, and `filtersApplied.all`
skips conversion. The provider sets only true flags for successfully executed
SQL work and never sets `all`. Count/extent use precalculated authorized SQL
aggregates. Predicate, bounding box, ordering, limit and aggregate work run in
PostGIS. All seven fields are fetched internally; projection occurs in Python
and Koop, so there is no SQL projection-pushdown claim. Native pagination is
signed keyset pagination. The private C1 `resultOffset` adapter requires explicit
immutable revisions and uses SQL OFFSET; deep offsets can scan their prefixes.
Native long decimals and IDs outside the bounded int32 profile are rejected by
the conversion guard. Row/field restriction profiles remain unsupported.

Earlier receipts are immutable. `install-001` completed npm but failed optional
reachability verification, then the reviewed graph repair enabled fresh
`install-002`. `runtime-001` failed because the supplied logger lacked `silly`;
`runtime-002` ran 165 assertions and failed twelve date checks because the
provider supplied Esri output type names instead of Koop input type names.
That run also exposed incorrect metadata field types, which stronger exact type
and nullability assertions now cover. `runtime-003` passed 175 assertions;
`runtime-004` passed 227 with the complete error/outage/method cases. The final
fresh run adds the actual Node archive guard. No failed receipt was relabeled.

All three services and the disposable database stopped. Credentials were
invalidated, private configuration scrubbed, and no secret diagnostics were
detected. The existing reviewed PostgreSQL `setsid` supervisor exception remains
explicit: PostgreSQL alone uses authenticated loopback outside that supervisor;
all application services use the unchanged loopback supervisor. Its 79 parent
and 79 child network probes passed, process-group/broker cleanup passed and no
datagram traffic escaped. This trusted fixture runner does not provide hostile
process/filesystem isolation. Retained SQL plans contain substituted **synthetic**
values and are not a model for production query logging.

The 35 custody/query/runtime-input guard tests pass. Required package validation
on this worker's base passed 457 tests and four schema examples; these are plan
checks, separate from the actual GIS/query journey. Root integration checks cover
the newer shared contract package. Notice/license work is separate: the original
pre-execution tr46 gap remains faithfully recorded in candidate002 evidence;
any later notice supplement must retain its own proof and disposition. This
experiment grants no redistribution or license waiver.

Reproduction requires the retained artifacts and exact contract/corpus inputs.
From the product checkout, use a fresh output directory:

```sh
python3 build-support/koop/runtime.py \
  --python /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation/run-003/venv/bin/python \
  --installation /home/revelberry/Projects/AmbisGIS/build-worktrees/fnd06-koop/install-002 \
  --contract /home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-worktree \
  --corpus /home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-corpus-runtime/round-005/scale-100000 \
  --corpus-manifest-sha256 5aeb5aad8a0f47780fdcba69bc6b568689bb14dc6b30927fa1e14b6796e06a88 \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/fnd06-koop/runtime-NEW
```

`runtime.py` retains the executed child tooling and exact invocation. Outer setup
uses the matching worktree helpers; the final source checkpoint is recorded above.
`outer-invocation-observed.json` transcribes the exact completed host tool command,
its observed exit/output and matching helper hashes after completion. It explicitly
does not claim that a pre-existing launcher captured the outer arguments.
`summarize.py` verifies result/cleanup/origin conditions, the actual credential
cursor result and the narrow response-difference boundary before producing the
public reference inventory. No input acquisition, install or service launch is
performed by that evidence verifier.
