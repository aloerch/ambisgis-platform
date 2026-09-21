# F02-04 owned QGIS candidate

This directory builds owned QGIS desktop, native HTTP/FCGI server and Python
bindings at `1a4cda5f2620e7374e5926fc955a7d2d06493e15` (`final-3_44_14`).
The [finite checklist](../../plan/docs/fnd-02-completion.md) controls acceptance.
An acquisition, configure, scaffold or build receipt alone does not complete it.
The [support audit](../../plan/docs/qgis-dependency-audit.md),
[runtime contract](runtime.md) and [native selection](native-tests.md) explain
independent dependencies and acceptance checks.

## Inputs and custody

`source-inputs.json` binds the owned source tar, notices, repository identity and
unchanged historical database/native evidence. `support-inputs.json` lists exact
publisher development/runtime RPMs and matching source RPMs. `profile-inputs.json`
hash-binds the chosen extracted support inventory, successful separate spatial
profile and the exact executed spatial recipe. The historical native prefix is
verified against the original hash-bound retained prefix archive before use.
None of these manifests is a release lock or license approval.

Large retained inputs live under
`/home/revelberry/Projects/AmbisGIS/source-archives/{qgis-candidate,postgis-slice}`.
Attempts and large outputs live under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate`.
Every attempt requires a new output directory; failures remain immutable evidence.
Publisher packages are extracted privately without installation or scriptlets.
The host bridge is `flatpak-spawn --host`; the IDE and host have different `/tmp`
mounts, so retained paths use the shared project directory.

The existing PostgreSQL 15.19/PostGIS 3.5.7 prefix remains unchanged. GEOS 3.13.1
is reused. The separate spatial profile rebuilds the same retained SQLite 3.50.4
with RTree and column metadata plus a SONAME, PROJ 9.6.2 against that SQLite, and
GDAL 3.10.3 with the required CSV/SQLite/GeoPackage drivers and GEOS. The original
minimal GDAL lacked those native-test drivers. Rebuilding PROJ avoids its old
absolute SQLite dependency loading a second SQLite implementation. Explicit
linker `-rpath-link` prevents an indirect dependency from selecting old SQLite.
`python_gdal.py` generates matching wrappers from the retained GDAL source and
compiles only Python extensions against the selected spatial prefix.

`xml_profile.py` builds the same retained libxml2 2.14.6 with HTTP support into
a separate QGIS-only prefix. Retained SpatiaLite requires `xmlNanoHTTPCleanup`,
which the earlier minimal XML build omits. The producer proves the symbol and
actual SpatiaLite loading with strict relocation and exact native origins.
QGIS configure/runtime/native tests explicitly select this new XML prefix; the
original database environment and prefixes stay unchanged. HTTP implementation
is compiled, while existing socket controls still deny external fetching.

## Execute

Use host Python 3.13 and the exact absolute prefixes recorded by the manifests.
Run acquisition first using the commands in the support audit. Build commands
use `common.run`, which invokes the unchanged `postgis/offline_exec.py`, records
actual kernel denial probes and rejects incomplete/failed proof. Each attempt
has empty HOME/XDG/temp/cache paths, no Python usersite, no pip index, no compiler
cache, no CMake package registry and no PROJ network access. This socket control
is not filesystem or hostile-code isolation; observed host tools/libraries still
have unresolved broader source/bootstrap closure.

```sh
python3 build-support/qgis/native_profile.py --help
python3 build-support/qgis/xml_profile.py --help
python3 build-support/qgis/python_gdal.py --help
python3 build-support/qgis/build.py --help
python3 build-support/qgis/reconcile.py --help
python3 build-support/qgis/runtime.py --help
python3 build-support/qgis/native_database.py --help
```

The executed command JSONs in each retained attempt provide complete arguments,
environment, start/end times, return codes and log hashes. `build.py` requires
`--native`, `--spatial`, `--support`, `--support-inventory`, `--xml`, `--output` and bounded
`--jobs` (selected: four). It freshly extracts the exact owned tar, runs configure,
compiles production and six selected native-test targets, privately stages the
artifacts, checks CRS database synchronization, inventories outputs and verifies
input/source integrity. Executed recipes are copied into the attempt.
The exact inherited GRASS metadata generator writes one new source-tree JSON
file during configure. All original source entries must remain unchanged, no
other addition is accepted, and that JSON must reproduce byte for byte offline
and match the staged copy. `reconcile.py` separately audits the already completed
build-06 whose original equality guard rejected this sole addition; it preserves
the failure and never recompiles, reinstalls or calls that audit a rebuild.

Desktop/core/GUI, server/services/plugins, analysis, Python/bindings, PostgreSQL,
SpatiaLite, auth/OAuth2, GSL, printer and serial support stay enabled. The profile
excludes 3D, PDAL/Draco, GRASS, Oracle/HANA, QtQuick application, gamepad,
WebKit/WebEngine, OpenCL, crash-handler integration, QScintilla API generation and
the server landing-page webapp. These excluded native features cannot be advertised as tested or
available in this profile. The inherited build still generates and installs GRASS
processing-plugin descriptions; their presence does not supply a GRASS engine. Excluding the landing-page webapp also removes its
inherited yarn network hook. Internal o2/spatialindex/poly2tri/MDAL/JSON use retained
source; vcpkg and donor synchronization are disabled. COPC/EPT stay enabled with
embedded laz-perf and retained ZSTD because the source has unconditional
core/GUI VPC dependencies when those options are disabled. These optional paths
are compiled but unexercised; no point-cloud capability acceptance is claimed. No QGIS distribution binary
or preinstalled host PyQGIS may supply acceptance artifacts.

## Verification and scope

```sh
python3 -m unittest discover -s build-support/qgis -p 'test_*.py' -v
cd plan
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

The runtime controller uses a deterministic local vector/GeoTIFF/PostGIS fixture,
real staged desktop event loop/canvas under Qt offscreen, native HTTP WMS service
and one restart. The native controller runs unchanged selected QGIS C++/Python
assertions against a separate disposable database. Missing prerequisites, zero
cases, selected skips, assertion/capture/integrity/network/cleanup failures cannot
produce a successful overall receipt. PostgreSQL retains the documented narrow
supervision exception; fixture credentials are invalidated and scrubbed.

No physical-display, Windows/macOS, full OGC/cartographic/provider parity,
FND-05 publishing, release-signing/deployment or full FND-02 acceptance is implied.
Historical database, Java, frontend and Jupyter passes are reused only within
their exact prior scope. The frontend five lint errors/five webpack warnings,
nonidentical replay and source/rights findings remain F02-06; the Java
48 structural/12 unresolved/four partial ledger is separate from QGIS inputs.

## Proposed F02-06 resource-selection profile

`resource_selection.py` creates a separate private stage from a verified compiled
prefix. It derives exact named exclusions from the recorded notice scopes,
corrects only affected catalogues, relocates their original metadata/notices, and
preserves every unrelated file/mode. It binds complete before/after inventories,
source archive members, executed tooling and all alternate copies. It does not
rebuild or edit the baseline. Future reviewed source/build baselines must update
the explicit inventory/source pins, not bypass their verification.

The [resource handoff](../../plan/docs/qgis-resource-selection-handoff.md) records
the 1,129 omissions, 265 unchanged ColorBrewer palettes, successful fresh native
palette/desktop/server evidence, and the separately unresolved GMT/td byte alias.
`resource_witness.py` runs through the real desktop with `resource_manifest` and
`resource_selection` hash bindings in the runtime configuration. Native file
availability/model checks deliberately do not trust the inherited `loadFile()`
boolean for a missing palette. All pre-existing distribution and acceptance gates
remain separate from this proposed resource profile.
