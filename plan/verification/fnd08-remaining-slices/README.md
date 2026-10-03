# FND-08: owned native, catalog and UI paired builds

This evidence records six actual fresh builds around three isolated synthetic
donor changes. It covers the PostgreSQL/PostGIS, catalog and frontend portions
of the initial Linux slice. It does not accept all of FND-08, qualify a release,
or replace the original FND-02 evidence. The integrator owns aggregate acceptance.

The implementation is in `build-support/owned_build/`. [evidence.json](evidence.json)
binds each retained result, source/dependency/output manifest, network receipt,
tooling snapshot, log and comparison. Large inputs and outputs remain under
`/home/revelberry/Projects/AmbisGIS/`; absolute paths in the receipt identify
actual local custody, not public download URLs.

| Build pair | Actual result | Output comparison |
| --- | --- | --- |
| Native `fnd08-native/final-pair-002` | Both passed | 2,153 installed entries; 2,055 identical hashes/link targets, 98 fully attributed differences, zero unexplained |
| Catalog `fnd08-catalog/final-pair-001` | Both passed | Both new owned wheels and the first-party policy capsule are byte-identical |
| UI `fnd08-frontend/final-pair-001` | Both compilations passed; original raw comparator failed | 1,038 logical assets each; 1,005 have identical content after explicit generated-name matching; 33 differ only in recorded webpack hash references and, in two chunks, job paths |

The UI raw failure remains in its original receipt. The separate
`fnd08-frontend/attributed-comparison-final.json` records zero unexplained content
changes. It does not turn the original raw byte comparison into a pass. Native
and UI comparisons retain original names, hashes and bytes; diagnostic
substitutions occur only in memory. Unknown content changes fail the command
after the diagnostic report is written. A subprocess regression proves that
changed JavaScript logic fails the UI comparison.

## Source and input authority

| Owned repository | Exact selected commit |
| --- | --- |
| PostgreSQL | `2ff1375b5dd8bf09d8cb0e795974528180fd75ca` |
| PostGIS | `9816f82458db774e62906cfb2c4f01f8b262c862` |
| GeoNode | `2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4` |
| GeoNode MapStore client | `a0d3f434cea69dadc93d35e13bc969b844aceea1` |
| MapStore | `88064efbf20ef0aaffebe357f7a99a1ab4fb23b8` |
| First-party policy source in platform | `0876999d7535d792d0024586981c762b2f9bf513` |

The producers verify exact Git trees and export every original blob and
executable mode, including files marked `export-ignore`. Unexpected gitlinks
fail; the client explicitly declares the selected MapStore commit. Existing
canonical compatibility/security changes are already source-owned. These
producers neither reapply historical patches nor select source from old archive
or donor branch tips. The UI creates job-owned Git metadata for inherited
version plugins without checking out or transforming exported blobs.

Each pair prepares a marked synthetic repository and fake default/API response
before build one. Only that fixture changes between completed build one and
fresh build two. A deliberately floating resolver observes a different sentinel
payload, proving the fixture is nonvacuous. Product builds continue selecting
the same exact owned commits and retained input manifests. No real donor or
owned repository references are changed by this experiment.

Builds use fresh source, home/cache and output directories, with IPv4/IPv6 socket
creation denied in the producer and descendants. The receipts verify seccomp,
no-new-privileges and actual denied socket probes. AF_UNIX and host filesystem
access remain available: this trusted build check is not a hostile-code sandbox.
Existing support libraries, third-party wheels and npm archives are deliberately
reused from recorded custody. Full dependency/toolchain source bootstrap is not
claimed.

Native support uses the fully hashed `postgis-slice/run-003/prefix`; all 18 native
source archives and retained notices were reverified. Both fresh builds run
217 PostgreSQL regression tests, one fuzzystrmatch regression, 413 PostGIS
CUnit cases (51,347 assertions), and 13 real private-cluster spatial/raster/
topology assertions. PostgreSQL and PostGIS original source files remain
unchanged. Each marked disposable database is stopped after the test. Supported
`SOURCE_DATE_EPOCH` removes generated SQL/build-date differences. Remaining
differences are exact job paths, ELF build-id notes and static archive member
mtime fields; archive payload and non-date metadata are compared.

Catalog builds retain 209 selected third-party wheels, 199 corresponding sdists
and ten historical `no-sdist-published` records. The supplemental source coverage
receipt lists each of those wheels' embedded Python source, compiled members
and metadata identity leads. Embedded implementation is inspectable, but this
does not prove complete standalone build inputs or source rebuild qualification.
Both builds install hashed dependencies in new Python 3.12 virtual environments,
pass `pip check`, import native GDAL 3.10.3 and the owned modules, and compile the
exact selected first-party policy source into a source/bytecode ZIP. That capsule
is not described as a wheel. Runtime policy/database acceptance is outside this
build check. The Python client wheel includes inherited static files; runtime
assembly must stage the separately newly compiled UI assets.

Frontend builds use retained Node 24.18.1 and 2,022 recorded registry archives.
They install with offline npm and ignored automatic lifecycle hooks, then invoke
the explicitly reviewed MapStore postinstall and real webpack compilation.
Inherited generated static directories are removed before compilation. All six
native entry points are present. The original webpack `[name].[hash].chunk.js`
rule explains 506 generated chunk-name changes. Two outputs still contain
literal build-root strings from `@spz-loader/core` and `@zip.js/zip.js`; the
attribution receipt preserves their names and occurrence counts. This remains
a distribution limitation, not a normalized artifact claim.

On fresh UI build one, retained sandboxed Chromium ran 358 client and 152 selected
framework assertions: zero failures, errors or skips. Five inherited lint errors
remain (one `react/wrap-multilines` in `ResourceDetails.jsx`, four `indent` errors
in `UploadUtils.js`). Therefore the combined native runner is still failed.
No lint rule or assertion was disabled. The loopback browser test does not claim
the socket denial used by the separate compilation.

## Reproduction and validation

Run from the platform root, choosing new output directories. All required
archives and source repositories must already be retained; these commands do
not acquire missing inputs:

```sh
python3 build-support/owned_build/pair_native.py --repos "$OWNED_REPOS" --custody "$NATIVE_CUSTODY" --support "$NATIVE_SUPPORT" --output "$NEW_NATIVE_PAIR" --jobs 4
python3 build-support/owned_build/pair_catalog.py --repos "$OWNED_REPOS" --custody "$CATALOG_CUSTODY" --support "$NATIVE_SUPPORT" --python /usr/bin/python3.12 --output "$NEW_CATALOG_PAIR"
python3 build-support/owned_build/pair_frontend.py --repos "$OWNED_REPOS" --inputs "$FRONTEND_INPUTS" --output "$NEW_FRONTEND_PAIR"
python3 build-support/owned_build/compare_frontend.py --pair "$NEW_FRONTEND_PAIR" --output "$NEW_UI_COMPARISON"
python3 -m unittest discover -s build-support/owned_build -v
```

The raw frontend pairing command can fail after both successful compilations;
inspect its preserved receipt and run the separate attribution command. The
recorded invocations provide the actual custody and output paths. Native
`final-pair-001` is also retained: both builds succeeded, but its comparator
correctly failed on then-unattributed generated dates. The final native pair
uses a fresh rerun with the supported build-date setting.

Validation: nine new helper tests; 22 existing native, 118 catalog and 39
frontend helper tests; 457 plan unit tests; and four JSON Schema/example checks
passed. Package tests are not GIS product acceptance. The final tooling path
audit matches the build snapshots except for one trailing empty line removed
from `common.py` after the builds; it records the exact original/final hashes
and verifies this precise byte difference. Snapshots remain untouched, and no
filesystem race prevention is claimed. Pair/comparator
analysis changes have separate final identities and do not relabel historical
producer snapshots. Host executable/library observations were sent to the
integrator for the selected host source/binary custody union; resolved-library
inspection is not represented as captured process memory maps.
