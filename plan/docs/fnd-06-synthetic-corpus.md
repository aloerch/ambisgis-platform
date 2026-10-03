# FND-06 synthetic corpus

The corpus implements the inputs required by [chapter 09 §4](09-roadmap-and-acceptance.md#4-test-corpus). It supplies inspectable native data, deterministic generation and independent correctness expectations. It does not implement the product query API, geodatabase schema, catalog policy, publication pipeline or mandatory Koop spike. Those retain their own contracts and acceptance tests. All R01–R24 requirements and P0–P7 gates remain in force.

The [checked-in small corpus](../fixtures/synthetic-corpus/small/) contains twelve addresses and every other fixture. The [generator](../tools/synthetic_corpus.py) uses Python 3.11 or later and the standard library. The generated first-party data, expectations and QGIS project use `GPL-3.0-or-later` under the existing chapter 08 policy; they contain no organization data, proprietary samples, private schemas, connection credentials or real-person records. The retained runtime and QGIS Vera font keep their existing third-party terms. Their bytes are not copied into this corpus.

## Generate and inspect

Run from `plan/`, choosing a new output directory whose parent already exists:

```sh
python3 tools/synthetic_corpus.py generate --output /existing/private-work/corpus-small --seed 2409 --addresses 12
python3 tools/synthetic_corpus.py generate --output /existing/private-work/corpus-100k --seed 2409 --addresses 100000
python3 tools/synthetic_corpus.py generate --output /existing/private-work/corpus-1m --seed 2409 --addresses 1000000
python3 -m unittest discover -s tests -p test_synthetic_corpus.py -v
```

Generation refuses existing destinations and symlink ancestors. It does not delete, overwrite, download or contact services. Partial outputs from a failed run remain for diagnosis; select another new destination to retry. Address count is an integer from 12 through 1,000,000; seed is an unsigned 32-bit integer. The defaults are twelve rows and seed 2409. `iter_addresses(seed, count)` streams features for importers. Both FeatureCollection GeoJSON and one-feature-per-line NDJSON are written in one pass; the generator does not materialize the large address collection.

Each manifest records seed, rule version, producer SHA-256 and every payload file's size/hash. The manifest excludes itself. A complete regenerated small corpus must match the checked-in manifest byte for byte. Verification rejects missing, extra, changed, symlinked and traversal members. Manifests establish identity, not upload safety or source trust.

The committed [native authoring recipe](../fixtures/synthetic-corpus/author_project.py) recreates the QGIS project in a disposable generated corpus using the selected owned PyQGIS runtime and retained font. It removes author/time metadata and replaces randomly assigned layer IDs with fixed fixture IDs. The committed template is the selected input; ordinary fixture generation copies it unchanged. Do not run authoring against the canonical checked-in `small/` directory: QGIS creates working project files.

In the prepared FND-08 stage-002 environment, native verification is:

```sh
/usr/bin/python3 build-support/postgis/offline_exec.py --evidence /existing/private-work/native-network.json -- \
  /usr/bin/python3.13 plan/tools/synthetic_corpus.py verify-native /existing/private-work/corpus-small \
  --report /existing/private-work/native-result.json \
  --runtime-config /existing/private-work/runtime-002-config.json
```

This command runs from the platform root and requires the selected QGIS, GDAL, PROJ, Qt, Python bindings and font environment; it does not install them. The exact executed commands and selected environment are in [verification](../fixtures/synthetic-corpus/verification/). The runtime configuration comes from the accepted FND-08 owned build, not a configuration fabricated for this corpus. The verifier requires owned QGIS commit `86af40542b219b0da6df1a43914413443330c0c0`, checks binding location, retained stage-manifest hash and exact font hash, and records actual runtime identities. A passing result is written only after native application shutdown succeeds.

The native verifier accepts this trusted, self-generated profile. Before native parsing it requires exact known file membership, the committed QGS template and exact canonical VRT/raw raster bytes. A rewritten manifest cannot authorize external QGS or VRT references. This is not a general hostile-upload validator or parser sandbox. The offline wrapper denies new non-AF_UNIX sockets; it does not isolate the filesystem or local Unix services. Use the product publication validation and isolation controls for untrusted submissions.

## Fixture contents and expected semantics

| Chapter 09 input | Concrete data and boundary |
|---|---|
| Address points | `addresses.geojson` and `.ndjson`, XY Point in EPSG:4326; exactly `fid`, `object_id`, `name`, `district`, `population`, `elevation`, `observed_at`. |
| Stable identities | UUIDv5 URL namespace over generator version/seed/dataset/index; `fid` also equals GeoJSON feature `id`. Positive unique `object_id = index + 1` is independent of result sorting and stays in the bounded C1 signed-32-bit range. |
| Unicode, null, empty and numeric domains | A fixed twelve-row scalar cycle includes accented Latin, Japanese, Greek, apostrophe and newline; null and empty names remain distinct. District has four values; population is nonnegative; elevation has three-decimal values. `schema.json` describes these fixture expectations only. |
| Dates, zones, decimal precision and large native IDs | `inspections.csv` plus `.csvt` has date-only values; addresses contain three zoned spellings of the same instant. `native/typed-values.csv` preserves exact decimal text and IDs 2147483648 and 9007199254740993 without JavaScript-number conversion. Import into appropriate typed native columns; do not coerce them into C1 ObjectIDs. |
| Roads and complex parcels | Three roads with numeric speed limits; two polygons, one with a hole and one with a 32-vertex exterior. |
| Relationships and attachments | Three inspection rows reference actual address UUIDs. `attachment-references.json` binds a local synthetic text attachment by parent UUID, media type and hash. The catalog remains the policy authority. |
| Multiband raster | Inspectable GDAL VRT plus local UInt16 little-endian raw bands: 4×3 pixels, three bands, EPSG:4326, known samples and NoData=65535. This does not assert that VRT is an accepted publication upload format. |
| Later time/mosaic capability | Two adjacent native rasters with different values and a timestamp index. Their presence does not advertise time/mosaic service support. |
| Projected feet | `native/epsg2230.csv` supplies WKT, explicit SRID 2230 and US-survey-foot coordinates. Native verification records the actual selected horizontal transformation and grid availability. |
| Z/M and empty geometry | WKT CSV preserves XYZ, XYM, XYZM and POINT EMPTY without ambiguous four-coordinate GeoJSON. A separate GeoJSON distinguishes null geometry from an empty GeometryCollection. These are native fidelity fixtures, not claims of generic API or publication support. |
| Rich QGIS project | Four local layers, categorized address symbols, expression labels, dashed roads, polygon fill/hole and a multiband raster; all reopen and render with the selected owned runtime and font. No cross-engine pixel-fidelity result is inferred. |
| Policy corpus | `policy-scenarios.json` lists public/private/group, row-filtered, field-restricted and grant/revoke cases across feature, raster, tile, search facet, attachment, app, notebook and job-log surfaces. These are setup expectations to apply through the authoritative catalog; they are not persisted grants or passing authorization tests. Unsupported secure rendering must deny. |

`expected-small.json` is a hand-authored oracle separate from the query implementation. The tests check fixed IDs selected by null/empty/district/population predicates, exact decimal sums, equivalent timestamp instants and Unicode code-point sorting with nulls last. This sorting oracle is explicit and does not imply a database locale collation. For any scale, the first twelve rows retain these semantics and identities. Geometry uses a 1,000-column grid: longitude −117 plus column/10,000 and seed offset; latitude 32 plus row/10,000 and the same offset, rounded to six decimals. Other geometries and raster rules are fixed and recorded in the producer.

`invalid/` deliberately contains duplicate ObjectIDs, duplicate UUIDs, a self-intersecting polygon, an orphan child, invalid domain/type/timestamp/C1-ID values and inert query/path/SSRF-abuse strings. Tests verify that the duplicate and orphan cases are actually invalid; the native run verifies that the invalid polygon can be parsed and is rejected by GEOS validity. No hostile string is executed or URL dereferenced. These inputs must still be connected to real database/API rejection tests by the relevant implementation tasks.

## Actual evidence and limits

[evidence.json](../fixtures/synthetic-corpus/verification/evidence.json) binds the source files, templates, small/large manifests, native results, offline receipts and package checks. Large outputs remain local and are reproducible with the commands above; only their manifests and selected evidence are committed.

The selected native run reopens all vectors, verifies the first twelve address IDs/geometry and six scalar fields, reads actual raster samples/NoData, checks Z/M/empty geometries, rejects the invalid polygon, reopens all four QGIS layers and performs a real 512×384 render. Zoned timestamp equivalence and exact high-precision text are separately checked by the scalar oracle; they are not mislabeled as native typed-column roundtrips. The same native verifier also runs on the actual 100,000- and 1,000,000-row artifacts.

EPSG:2230 verification disables PROJ networking, fallback and ballpark transformations. Its available operation is the inverse California zone 6 projection followed by NAD83-to-WGS84 (1), with reported accuracy 4 metres and no grid dependencies. The inverse roundtrip tolerance is 0.01 US survey foot. That roundtrip establishes consistent units and operation behavior; it does not turn a 4-metre operation into centimetre-accurate geodesy or verify other grid-dependent transformations.

The actual large generation/check runs found 100,000 and 1,000,000 distinct UUIDs and preserved ordered ObjectIDs. Independently accumulated population sums were 5,499,840 and 54,999,840; null and empty counts were each 16,667 and 166,667. Every payload hash was rechecked. Final generation took approximately 0.901 and 8.237 seconds and produced 63,115,396 and 632,065,398 payload bytes on this recorded host. These are single fixture-generation observations, not service capacity, database/query performance, latency distributions or support quotas. The verification script's UUID uniqueness set is intentionally not a bounded-memory benchmark of the generator.

An initial QGIS authoring attempt and initial native run terminated with exit 139 because provider objects survived application shutdown. Those failed receipts are retained. The initial native script wrote an internal passing result before that failed shutdown; it is explicitly not accepted evidence. Object lifetimes and receipt ordering were corrected. Independent review then identified that the feet check used a literal point instead of reading the CSV and that the address comparison did not require all twelve rows. Both were corrected. An actual truncated-NDJSON regression exposed a second shutdown problem: an exception traceback retained provider objects. The verifier now clears inspected-frame locals while QGIS is alive and reports a plain failure after clean shutdown. Final round-005 runs bind all corrections and regenerated manifests; original receipts are unchanged.

Actual final negative subprocesses select a wrong owned source, truncate NDJSON with a rewritten manifest, and change the feet point with a rewritten manifest. Each exits 1 and leaves no passing report. The native feet transformation now consumes and verifies actual CSV SRID, UUID and WKT coordinates and records the file hash and input point. The twelve-row comparison requires exactly twelve rows with ObjectIDs 1 through 12. The executed positive/negative orchestration script is retained in verification alongside its commands, results and network receipts.

The complete plan suite passes 474 tests (including 17 corpus tests), and all four package schemas/examples pass. These are plan/package checks, not GIS product acceptance. Real query authorization, PostGIS constraints, publication, renderer fidelity, client compatibility, notebooks, concurrency, recovery and the mandatory Koop/PostGIS/catalog spike require their own evidence. This corpus does not waive them.
