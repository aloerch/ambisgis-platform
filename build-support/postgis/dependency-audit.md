# FND-02 PostgreSQL/PostGIS dependency input audit

This directory records the inputs for the bounded owned PostgreSQL 15.19 / PostGIS
3.5.7 experiment. These are candidate build inputs, not approved product
baselines, a license decision, a security assessment, or the whole-product
release lock. Build and database results belong in the integrator's evidence
record; acquisition and source inspection alone do not establish compatibility.

`inputs.json` contains actual SHA256 values for 20 retained archives, totaling
320,548,182 bytes, and 93 original license/notice/source-header records. Large
archives, extracted inspection trees and notice copies are outside Git at
`source-archives/postgis-slice/` relative to the existing multi-repository
workspace. Archive names, root directories and original notice paths are
recorded individually. `licenses/<input>/<original-path>` retains original bytes,
including filenames and source headers where there is no standalone license.
Some evidence files are source headers or READMEs, not license grants themselves.

## Exact owned source identities

| Input | Retained owned commit | Purpose |
|---|---|---|
| PostgreSQL 15.19 | `2ff1375b5dd8bf09d8cb0e795974528180fd75ca` | Server, client, libpq, headers and PGXS |
| PostGIS 3.5.7 | `9816f82458db774e62906cfb2c4f01f8b262c862` | Target extension |
| PostGIS 3.5.6 | `9aa71a8e5059959929825926db5ebefafde471db` | Actual earlier extension for upgrade testing |

Snapshots were made with `git archive --format=tar --prefix=<archive_root>/`
from existing owned clones after resolving retained tags to commits. Original
histories remain in the previously verified PostgreSQL/PostGIS Git bundles;
their paths, hashes and repository IDs are linked from each owned manifest
entry. Archive creation did not change donor references, owned defaults or
workflows. An archive hash is byte-integrity evidence, not verification of an
upstream release signature or approval of canonical mirror provenance.

## Selected dependency profile

The exact target PostGIS `configure.ac` requires PostgreSQL >=12, GEOS >=3.8,
PROJ >=6.1, GDAL >=2.4 with OGR enabled, and protobuf-c >=1.1 plus `protoc-c`.
`README.postgis` additionally describes json-c >=0.9 and GEOS >=3.12 for the
newer coverage functions. Missing json-c or CUnit only warns during configure;
the recipe must assert their presence and execute their capabilities/tests.

| Input | Use and direct inputs in this experiment | Original evidence and review notes |
|---|---|---|
| GEOS 3.13.1 | Runtime geometry; CMake >=3.15, C++14; own tests | `COPYING` contains LGPL 2.1 text. Subtree notices are retained too. |
| PROJ 9.6.2 | Runtime CRS; SQLite library + shell >=3.11, TIFF and HTTP-only libcurl; CMake >=3.16, C++17; GoogleTest/PyYAML for tests | `COPYING`, embedded JSON header and SQL provenance README retained. MIT-style notice does not substitute for review of CRS/data provenance. |
| curl 8.14.1 | Runtime PROJ transport API and remote-data status; retained zlib, no TLS or optional protocol libraries | Original `COPYING` retained. HTTP-only compatibility experiment, network disabled and denied; no production HTTPS capability or security approval. |
| GDAL 3.10.3 | Runtime raster; PROJ, TIFF, PNG, JPEG, zlib; embedded GeoTIFF and other bundled sources | `LICENSE.TXT` aggregates differing notices; relevant embedded notices/headers retained. |
| GDAL autotest 3.10.3 | Test only; separate official release archive, installed under the isolated GDAL source's `autotest` | Source-file notices retained; fixture provenance and redistribution still require human review. |
| protobuf-c 1.5.2 | Runtime C wire format and build-time `protoc-c`; Google protobuf >=3.0 | BSD-style `LICENSE`; library/compiler are both required by PostGIS MVT/Geobuf. |
| Google protobuf 21.12 | Build-time dependency of protoc-c; zlib, GoogleTest | BSD-style `LICENSE` and subtree notices; chosen bounded 21.x compiler path avoids adding Abseil, not a claim of current support or security approval. |
| json-c 0.18 | Runtime PostGIS GeoJSON; CMake | `COPYING` and bundled notices retained. |
| CUnit 2.1-3 | Test only; Autotools | `COPYING` states GNU Library GPL; source files must be considered by license review. |
| SQLite 3.50.4 | Runtime PROJ database access and build-time sqlite3 shell; retained amalgamation | Copyright disclaimer/blessing in `sqlite3.h` and `shell.c`; separate autosetup/TEA notices retained. Full SQLite Tcl tests are absent from this archive. |
| TIFF 4.7.0 | Runtime grid/raster images; zlib/JPEG codecs | `LICENSE.md` plus retained notices; optional LZMA/Zstd/WebP/JBIG/libdeflate codecs disabled explicitly. |
| JPEG 9f | Runtime raster JPEG codec; Autotools | Original `README` contains the IJG terms; no invented LICENSE filename. |
| libpng 1.6.58 | Runtime raster PNG codec; zlib | `LICENSE` contains PNG Reference Library License v2; selected with the official published hash check described below. |
| zlib 1.3.1 | Runtime compression and dependent builds | Original `LICENSE` and subtree notices retained. |
| libxml2 2.14.6 | Runtime PostgreSQL XML/PostGIS XML; zlib | `Copyright` and source-specific notices retained; Python/LZMA/iconv optional bindings/features disabled by the bounded recipe. |
| GoogleTest 1.15.2 | Dependency tests only | BSD-style `LICENSE`; exact version requested by PROJ's fallback source recipe, supplied locally instead of fetched by CMake. |
| PyYAML 6.0.2 | PROJ CLI tests only, pure Python `lib/` on PYTHONPATH | MIT-style `LICENSE`; PyPI sdist hash compared with computed SHA256. No pip install or C extension build is required. |

These selections satisfy declared minimums; ABI and behavior still require the
actual build/test results. Full source and test archives may contain unused
modules with additional notices. The inventory deliberately retains these
original notices rather than representing the entire distribution as one
license. Review must also account for PostGIS's embedded Wagyu, geometry,
FlatGeobuf/FlatBuffers, Ryu and uthash notices already retained in its archive.

The [official libpng page](https://libpng.org/pub/png/libpng.html) identifies
1.6.58 and its SHA256. It describes security fixes in 1.6.57 and a follow-up
palette regression fix in 1.6.58; this is why the PNG input was selected instead
of an arbitrary older 1.6.x patch. Its downloaded archive matches the published
`28eb403f51f0f7405249132cecfe82ea5c0ef97f1b32c5a65828814ae0d34775`.
Other official acquisition URLs are in the manifest, including the
[protobuf release](https://github.com/protocolbuffers/protobuf/releases/tag/v21.12),
[protobuf-c releases](https://github.com/protobuf-c/protobuf-c/releases),
[json-c release source](https://github.com/json-c/json-c/wiki),
[CUnit releases](https://sourceforge.net/projects/cunit/files/CUnit/), and
[IJG source](https://www.ijg.org/). This limited source check is not a complete
vulnerability review of the selected dependency graph.

## Features, CRS data and test boundaries

The intended experimental PostGIS profile includes vector geometry/geography,
spatial indexing, topology, raster, MVT/Geobuf, GeoJSON and XML. SFCGAL,
GTK importer GUI and address standardizer are explicitly deferred. This does
not narrow AmbisGIS's product requirements or establish QGIS/rendering parity.
The PostgreSQL experiment enables XML and zlib; server SSL/ICU/LLVM/TAP and
production authentication/deployment remain outside this local database slice.
The integrator's `build.py` and runtime evidence are authoritative for actual
flags and observed libraries; no feature is established by this document alone.

GDAL raster regression requires GTiff, PNG and JPEG: PostGIS
`raster/test/regress/check_gdal.sql:28-30` enables those three and checks a count
of three. MEM, VRT and EHDR support internal raster paths and driver permission
tests. AAIGrid/DTED and OGR Shape allow additional retained GDAL C++ tests.
OGR remains enabled as PostGIS configure requires it. Optional GDAL drivers and
network/CURL access are excluded explicitly. With `GDAL_USE_EXTERNAL_LIBS=OFF`,
only explicitly enabled external libraries are used: merely building GEOS or
SQLite does not enable GDAL's corresponding optional integrations.

PROJ's retained SQL generates `proj.db` during the local build. Its metadata
declares layout 1.5, EPSG `v12.013` dated `2025-05-26`, and compatible
PROJ-data version `1.22`. The manifest separately hashes 62 included `.tif`,
`.gsb` and `.gtx` test resources plus `data/sql/metadata.sql`. These contain
synthetic grid fixtures, selected/downsampled real-grid fixtures and malformed
files for negative tests. They are test inputs and must not be installed or
advertised as a complete production grid collection. The standalone global
PROJ-data 1.22 archive was not acquired. Offline transforms requiring other
regional/vertical grids remain unproven; EPSG identifiers alone are not proof
that the needed transformation grid exists.

Source audit identified these build/test traps:

- PROJ defaults `TESTING_USE_NETWORK=ON`, probing Google with curl/ping.
  Set it and `RUN_NETWORK_DEPENDENT_TESTS` to OFF. Keep `BUILD_PROJSYNC=OFF`.
  The final candidate compiles CURL support using the retained HTTP-only
  libcurl input while leaving `PROJ_NETWORK=OFF`; see the failed clean-build
  investigation below. Use `USE_EXTERNAL_GTEST=ON` with
  retained GoogleTest; otherwise the unit-test CMake file can fetch GitHub.
- GDAL's main release archive omits autotest. The matching separately retained
  archive is required for real C++ tests; its CMake can also download GoogleTest
  unless `USE_EXTERNAL_GTEST=ON`. Python bindings/tests are not enabled by this
  C++ raster profile and must be disclosed as unrun, not silently counted.
- Protobuf uses `protobuf_USE_EXTERNAL_GTEST=ON` to resolve retained GoogleTest.
  Its compiler is a build input; it is not required for PostGIS runtime MVT.
- SQLite's autoconf amalgamation does not contain its full Tcl test suite.
  Explicit shell/version/integrity/math probes are partial evidence only.
- CUnit's `make check` is not its internal test execution. Run
  `CUnit/Sources/Test/test_cunit`. Its main returns zero unconditionally, so
  require a nonzero final assertion count and `Failures: 0` in the final
  `CUnit Internal Test Results` block.
- PostGIS top-level `make check` also invokes docs and lint. Core/raster CUnit
  and database regressions must run and have real counts independently of
  documentation/tool availability. A configure success with missing CUnit or
  JSON is not acceptance. The retained earlier 3.5.6 must actually create a
  database extension before target 3.5.7 is installed/updated for upgrade proof.
- Default tool/library searches can pick host binaries. Explicit `pg_config`,
  prefix PATH/pkg-config/CMake paths, runtime library paths, and actual version
  queries are required. Host libc/libstdc++, compiler, linker, headers and
  tools are not retained by this manifest; the slice is not a complete
  independently reconstructable product toolchain.


## Clean-build findings and the curl addition

Run-001's initial PROJ CMake cache omitted eleven YAML CLI wrappers because
PyYAML was unavailable at the first configure. Its 55 registered passing
wrappers were incomplete coverage. The clean run-002 registered all 66 and
failed unmodified `test_projinfo.yaml`, case 49: `projinfo --remote-data` with
`PROJ_NETWORK=OFF` expected the normal disabled-network reason, while the
CURL-free build reported that curl support was absent. The expected output and
test selection were not changed. The candidate profile now includes the
required compiled libcurl API, retaining curl 8.14.1 from the
[official source archive](https://curl.se/download/curl-8.14.1.tar.xz).
This exact archive is an experimental compatibility input selected for the
bounded 8.x build, not a claim that it is the current or security-approved curl.

The minimal transport build enables HTTP and retained zlib, disables TLS,
external IDN/PSL/GSS/SSH/HTTP2/HTTP3/resolver libraries and compression libraries
other than retained zlib, and disables
other protocols explicitly. `--enable-debug` enables the retained unit-test
library. Build `lib/libcurlu.la`, then the five individual unit programs 1300,
1302, 1305, 1307 and 1309. Run each with a dummy URL argument: these source
bodies test linked lists, Base64, hash/DNS-cache data structures, wildcard
matching and splay trees without issuing a transfer. `UNITTEST_STOP` returns the
failure count. The full server/protocol test harness and HTTPS are outside
this profile; version probes or these five cases do not test real transport.
Actual run results remain the integrator's evidence, not asserted here.

Enabling CURL also compiles more PROJ network unit cases. Its `initial_check`
attempts an HTTPS CDN request regardless of the CMake network-test option;
the HTTP-only curl cannot perform HTTPS, and the offline run denies network
sockets. Later cases often return early when `networkAccessOK` is false instead
of reporting GTest skips. These returned cases must be recorded as unavailable
network coverage even when their wrapper reports success. The local callback
and network-disabled behavior tests remain applicable.

A separate run-001 omission was detected by reading GDAL's internal skips:
`GDAL_ENABLE_DRIVER_EHDR` is not a supported 3.10.3 CMake option. EHdr and ENVI
belong to `GDAL_ENABLE_DRIVER_RAW`; the former switch was unused and RAW was
OFF. Three internal cases therefore skipped unexpectedly (ENVI layout, ENVI
multithreaded writing and EHdr virtual memory). The corrected recipe uses RAW
and verifies actual runtime driver names. Other inspected intended switches
were recognized and their runtime formats present. Do not treat the initial
24 successful GDAL wrappers as proof of the originally intended raster profile.

## Repeatable acquisition and recovery

Run from the platform checkout. The default command is read-only and performs
no network requests; it verifies archive size/hash and retained notice bytes.

```sh
python3 build-support/postgis/acquisition.py \
  --custody ../source-archives/postgis-slice
```

For missing inputs, explicit `--fetch` uses only recorded HTTPS URLs and exact
hashes. It also reproduces original notice copies. Owned archive recovery uses
the existing clones, checks their owned origins and exact commits, and calls
`git archive`; it does not fetch Git or initialize submodules.

```sh
python3 build-support/postgis/acquisition.py \
  --custody ../source-archives/postgis-slice --fetch --source-workspace ..
```

Extract into a fresh directory with `--extract <directory>`; `--only <name>`
is repeatable for a subset. Extraction verifies the original archive first,
requires the recorded root, rejects traversal/devices/duplicate files, uses
Python's data extraction filter, and refuses to replace an existing source
tree. Internal symlinks needed by json-c tests are preserved. Corrupt existing
archives are not overwritten. A failed download remains temporary and cannot
replace retained evidence. TLS and recorded integrity are not a substitute
for independent release-signature/provenance review.

The original inspection tree at `inspected/` is outside build directories and
must stay separate from build-time generated files. Source manifests and
recipes belong in Git; these archives, working builds and logs do not. The
retained bundles can recover owned history before the snapshot recipe is run.

## Acquisition validation and open review

Eight offline acquisition regressions cover read-only verification, archive
and notice corruption, corrupt-input preservation, traversal and unsafe entry
rejection, internal symlink preservation, destination reuse, directory-link
escapes, incomplete downloads, manifest bounds and earlier upgrade identity.
The initial 19 actual retained archives and 92 original notice copies were
verified by the recipe, and every archive was safely extracted to a fresh
temporary directory. The later curl input was separately verified and safely
extracted; read-only verification of all 20 inputs and the eight acquisition
regressions passed after the addition. These results and log hashes are retained
in `acquisition-verification.json`.
The existing schema-validation environment subsequently passed all 151 package
tests with no skips and the schema-aware package validator; the initial default
Python run lacked jsonschema and had seven skips plus a schema-validator failure.
Commands, outcomes and retained logs are linked in `acquisition-verification.json`. These are tooling checks, not PostgreSQL/PostGIS product tests.

Human license/brand, source provenance and security reviews remain pending.
The extracted notice inventory is evidence for that review, not an SPDX
legal conclusion or authorization to relicense/publish. Full source-history
mirroring for these external libraries, toolchain/base-OS custody, global CRS
grid coverage, unrun language/driver suites, and the full eleven-component
tuple remain outside this bounded acquisition completion.
