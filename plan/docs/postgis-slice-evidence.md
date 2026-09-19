# FND-02 owned PostgreSQL/PostGIS candidate slice

This extends open [PR #51](https://github.com/aloerch/ambisgis-platform/pull/51)
on `fnd-02/source-evidence`. FND-02 remains **In progress** because the complete
component tuple is unfinished. These experimental builds do not approve licenses,
production baselines, source-fork defaults, FND-07/FND-08 or P1 entry. The verified
integration base remains PR #50 merge `3e7581a06b000856ea9b27468cc415612c28b4b0`.

## Inputs and repeatable implementation

The [manifest](../../build-support/postgis/inputs.json) pins 20 archives totaling
320,548,182 bytes, with 93 retained original license/notice records. Actual hashes,
source URLs, owned commit identities, build/runtime use and required inputs are
recorded there. The [audit](../../build-support/postgis/dependency-audit.md)
explains source requirements and unresolved license/data questions. Original
owned Git bundles remain retained; these three archives were derived from those
owned histories, without donor synchronization:

| Source | Candidate | Owned commit |
|---|---|---|
| PostgreSQL | 15.19 | `2ff1375b5dd8bf09d8cb0e795974528180fd75ca` |
| PostGIS target | 3.5.7 | `9816f82458db774e62906cfb2c4f01f8b262c862` |
| PostGIS earlier upgrade fixture | 3.5.6 | `9aa71a8e5059959929825926db5ebefafde471db` |

Selected dependencies are GEOS 3.13.1, PROJ 9.6.2, GDAL 3.10.3, json-c 0.18,
protobuf-c 1.5.2, protobuf release 21.12 (protoc reports 3.21.12), CUnit 2.1-3,
curl 8.14.1, zlib 1.3.1, SQLite 3.50.4, libxml2 2.14.6, JPEG 9f, libpng 1.6.58,
TIFF 4.7.0, GoogleTest 1.15.2 and PyYAML 6.0.2. GDAL's matching test-data archive
is separate. These versions follow the inspected candidate requirements; they
are not claims of current security suitability or final baseline approval.

[Reproduction commands](../../build-support/postgis/README.md) cover acquisition,
isolated build prefixes, native tests, real earlier-version upgrade, regression
runs, network denial and evidence export. Recipes verify archives before use,
reject unsafe archive paths, isolate build environments, preserve actual commands,
working directories, input/recipe/log hashes, exit status and failures. A build
lock prevents overlapping writers to one run. The database harness checks actual
`pg_config`, server/executable identity and prefix-resolved GIS libraries, uses
private UNIX sockets with TCP disabled, and stops only its own marked cluster.
Regression Perl invocations retain separate artifact directories and immutable
driver snapshots. No expected source test output was changed.

## Experimental feature profile

PostgreSQL is rebuilt with retained XML/zlib and its owned `fuzzystrmatch` contrib
module. Readline, SSL, ICU, LLVM, TAP and the remaining optional/contrib matrix
are excluded from this private-socket experiment. This does not establish the
production authentication, transport, backup or migration profile.

PostGIS enables geometry/geography, raster, topology, XML, GEOS, PROJ,
GeoJSON/json-c, MVT/Geobuf/protobuf-c and internal Wagyu. The driver refuses missing
JSON, protobuf or CUnit support. SFCGAL, GUI and address standardizer are excluded.
TIGER extension installation/self-upgrade is exercised by the inherited suite;
its own source leaves functional geocoding regression coverage as a TODO.

GDAL provides GTiff, PNG, JPEG, RAW (including EHdr/ENVI), AAIGrid, DTED, VRT/MEM
and Shapefile for the selected native fixtures. Installed driver names are
asserted. GDAL's additional drivers, language bindings, GEOS integration, CURL
and iconv are excluded. PostGIS's geometry operations use retained GEOS directly.
PROJ builds its local `proj.db` from retained SQL and has retained source test
grids; broad external grid coverage remains incomplete. PROJ networking is OFF.
An HTTP-only/no-TLS curl build supplies the compiled API variant required by
unchanged PROJ CLI tests; real internet grid transport is unavailable.

## Actual results

Final clean run `build-worktrees/postgis-slice/run-003` uses fresh source
extractions and a fresh local prefix. The earlier 3.5.6 fixture passed 13 spatial
checks. After installing genuinely changed 3.5.7 libraries, all three extensions
were upgraded and existing geometry/raster/topology witnesses matched. The
upgraded database passed 13 checks and a separate fresh database passed 13.
Checks include GEOS geometry operations, a real GiST plan over 10,000 points,
EPSG 4326→3857 using the installed `proj.db`, GeoJSON, nonempty MVT, GTiff raster
round-trip and topology data. PostgreSQL's executable stayed unchanged across
the upgrade. Both fixture phases stopped their own cluster successfully.

Both native SQL modes passed: **672 source-mode and 672 installed-extension
regressions**, with zero failures or skips. Each mode comprises 336 ordinary and
336 same-target self-upgrade cases; those self-upgrades remain distinct from the
real 3.5.6→3.5.7 fixture. The final reviewed linkage guard also passed another
13 spatial checks in a separate fresh database. All validation clusters stopped.

| Native validation in run-003 | Actual result |
|---|---|
| PostgreSQL core; fuzzystrmatch | 217 + 1 tests passed |
| PostGIS 3.5.6 CUnit | 412 tests; 51,344 assertions passed |
| PostGIS 3.5.7 CUnit | 413 tests; 51,347 assertions passed |
| GEOS | 493 wrappers; 3,116 TUT and 11,313 XML successes; two malformed-case omissions below |
| PROJ | 66 wrappers; 813 YAML and 7,901 GIE cases; network omissions below |
| GDAL | 24 wrappers; 858 internal passes, 31 feature skips |
| libxml2; GoogleTest; json-c | 7; 63; 25 wrappers passed; corpus/self-test gaps below |
| libpng; TIFF | 37; 154 wrappers passed |
| protobuf; protobuf-c | 3 wrappers / 2,431 internal passes + 1 ASan skip; 11 passes |
| CUnit framework; curl | 3,915 assertions; five active socket-free unit programs passed |
| zlib; JPEG; SQLite | Three modes; seven output comparisons; three bounded SQL probes passed |

[Machine-readable evidence](../verification/postgis-slice.json) records exact
source/input/output hashes, native counts, remaining omissions, recipe identities,
command references, library resolution, host dependencies and offline receipts.
Its full local snapshots preserve commands, working directories, environments,
exit statuses, all regression invocations and artifact hashes. Final run-003 has
103 completed build commands, all zero exit; historical failures remain in their
own runs. The independently checked final snapshot had no hash mismatches or
collection problems. The collector deliberately does not infer task acceptance.

Current tooling checks: **175 package tests and 22 database-harness tests passed,
with no failures or skips**; strict dependency/reference validation and all four
schema/example checks passed. Retained outputs:
[package tests](../verification/postgis-slice-package-tests.txt),
[harness tests](../verification/postgis-slice-harness-tests.txt),
[schema checks](../verification/postgis-slice-schemas.txt).
These are tooling checks, separate from the real native/database tests.

## Failures and omissions remain part of the evidence

Exploratory `run-001` preserved four failed build commands: CUnit's distributed
`config.status` rejected out-of-tree configure; PROJ's default projsync required
CURL; protobuf's parallel build lacked generated lite-test headers; PostgreSQL's
regression socket path exceeded its native length limit. The recipes now
configure CUnit in its isolated extraction, explicitly generate the unchanged
protobuf fixtures using retained protoc, and use a unique short PostgreSQL
socket directory. The original startup logs remain retained. Early exploratory
commands predated immutable recipe snapshots; the final clean run has them.

Two initial database preflight attempts failed on the harness's incorrect raster
module filename and its rejection of native version-plus-revision strings.
Targeted tooling regression tests now cover both corrections. The subsequent
run-001 real upgrade passed. Its source regressions passed 672 tests; its
extension-mode suite failed before cases ran because `fuzzystrmatch.control`
was absent. The corrected profile builds, tests and installs that owned module.

Reading internal test results found omissions hidden by successful wrappers.
Run-001's cached PROJ configuration omitted 11 YAML wrappers. Fresh offline
`run-002` executed them and failed unchanged `projinfo --remote-data` case 49
because the CURL-free build reports a different capability. That run remains a
failed partial offline attempt. The retained HTTP-only curl input fixes the
compiled variant without enabling runtime networking. Run-001's unused
`GDAL_ENABLE_DRIVER_EHDR` option left three RAW tests skipped; the source's actual
`GDAL_ENABLE_DRIVER_RAW` option fixes this. All three cases execute in run-003.
Review also found curl unit1307's body empty when FTP is disabled; the original
pass is not assertion-bearing coverage. The final five active units are 1300,
1302, 1303, 1305 and 1309, rerun with socket denial and unchanged source assertions.

Remaining omissions are explicit: SQLite has bounded SQL integrity/version/math
checks rather than its unavailable full Tcl suite; libxml2 lacks three external
XSD corpora and the separate xmlconf corpus; GEOS's native XML runner silently
skips two malformed inherited fixture cases (unresolved fixture defects).
GoogleTest self-tests contain intentional skips/disabled fixtures; protobuf has
one ASan-only skipped test in this non-ASan build. GDAL has 31 documented optional
feature skips after the three RAW omissions were corrected. PROJ reports 12
network cases as passed after early return, plus partial `basic` coverage and an
unsuccessful `initial_check`; these are unavailable live-network coverage, not
successful transport tests. Full curl protocol/server tests, global PROJ grids,
PostgreSQL check-world/TAP and the excluded PostGIS extensions remain unrun.

## Network denial, custody and remaining acceptance

The build, curl correction, old fixture, target build, actual upgrade and native
regressions run through the Linux x86_64 seccomp/no-new-privileges wrapper.
Each invocation tests IPv4/IPv6 socket creation returning EPERM and UNIX socket
operation succeeding. The filter is inherited by child processes and closes
extra inherited descriptors. The report's command exit code, not its generic
`completed` status, determines command success.

This demonstrates a database dependency slice rebuilt from retained inputs
without upstream network sockets. Host filesystem and local UNIX services remain
accessible; the wrapper is not hostile-code isolation. Compiler/binutils,
CMake/Ninja/Make, Autotools, Perl, Python, shell tools and libc/compiler runtimes
are observed and hashed but their source/build closure is unretained. No
whole-product disconnected rebuild, byte-identical reproduction, synthetic
repair, release signing or deployment is established.

Large artifacts remain outside Git under the multi-repository workspace:
`source-archives/postgis-slice/` for retained inputs/notices;
`build-worktrees/postgis-slice/run-00{1,2,3}/` for source/build/prefix/log/database
evidence, and adjacent offline receipts and full evidence snapshots. These are
local retained artifacts, not remotely published release downloads. The PR
contains recipes, manifests, compact results and hashes.

Outstanding review includes exact canonical/mirror provenance, candidate baseline
selection, included-file license/data/notice obligations, production security
profile, toolchain closure and the remaining owned component tuple. FND-02 stays
In progress; FND-07/FND-08 and P1 gates remain unsatisfied. GOV-02 independently
remains Blocked on owner verification of saved grouping, sorting, filters,
roadmap date fields and Delivery/Status behavior. No importer reapply, source-fork
default/workflow change, secret installation, release or merge is part of this slice.
