# F02-04 native QGIS test subset

This selection belongs to owned QGIS `1a4cda5f2620e7374e5926fc955a7d2d06493e15`
(`final-3_44_14`). `native-selection.json` binds the unchanged native source files,
method names, helper modules and retained fixture/golden-output tree. The runner
executes native C++ QtTest binaries and imports the exact native Python test
classes; it does not replace provider assertions with mocks. Native tests use the
fresh build's libraries and bindings. Staged desktop/server startup and spatial
witnesses are separate acceptance evidence.

| Area | Required native selection | Prerequisites |
|---|---|---|
| C++ CRS | Eight coordinate-transform object/2D/error-handling methods | Owned PROJ resources, EPSG 4326/3857; no grid download |
| C++ project | Seven settings/path/CRS methods including save/read of CRS | Core and temporary project directory |
| C++ OGR | Six methods including CSV writes, GeoPackage/3D extents, GeoJSON fields and thread use | OGR CSV, GeoPackage, GeoJSON and Shapefile drivers |
| C++ GDAL | Fifteen raster methods: scale, masks, nodata, GeoTIFF metadata, warped VRT and coordinate mapping | GTiff, MEM, VRT; retained TIFF fixtures |
| C++ PostgreSQL | Fifteen provider methods including real EWKT/PostGIS round trip | `ENABLE_PGTEST=ON`, fresh PostGIS fixture |
| C++ server | Four query validation/default/input parsing methods | Real server library |
| PyQGIS project | CRS, zipped project save/read, vector/raster relative paths | Shapefile, GTiff, lxml |
| PyQGIS CRS | UTM56S to longitude/latitude; full-world Web Mercator bounds | EPSG 32756/4326/3857 and unchanged native tolerances |
| PyQGIS GDAL | Known 3×4 raster values, fixed size, provider cloning | NumPy and matching source-built `osgeo` bindings |
| PyQGIS PostgreSQL | Default values/clauses, query layer, extent, feature count, subset filtering | psycopg2; source `someData` and `some_poly_data` fixtures |
| PyQGIS server | GetCapabilities XML and GetMap basic (five requests with unchanged image controls/masks) | OWSLib, lxml, SpatiaLite and GeoTIFF providers, retained QGIS test fonts |

The exact six build targets are printed by:

```sh
python3 build-support/qgis/native_tests.py --list-targets
```

Configure `ENABLE_TESTS=ON` and `ENABLE_PGTEST=ON`, then build those targets beside
the desktop/server/bindings targets. Do not build all native suites merely to run
this subset. The sixteen selected Python methods and fifty-five C++ method
selectors are specified before their first execution. C++ data rows produce
additional reported cases; initialization/cleanup do not count as selected cases.

The initially proposed C++ `testAttachmentsQgs` and `testAttachmentsQgz` require
OGR's GPX driver, outside the frozen F02-04 profile. During source preflight,
before any QGIS native execution, these were replaced with existing
`testCrsValidAfterReadingProjectFile` and `testDefaultRelativePaths` methods.
The original proposal and reason remain in the selection manifest. The attachment
cases are **unavailable and unexecuted**, not reported as native passes or skips.
Global datum grids, NetCDF/other optional drivers, full database write/auth/TLS
suites, point clouds, provider parity and full WMS conformance are outside this
selection. A failure in a selected case remains a failure; no golden outputs or
assertions may be rewritten to obtain a pass.

The native PostgreSQL fixture is deliberately separate from the desktop/server
runtime fixture. `native_database.py` reuses the existing retained database
identity verifier and supervisor exception. It creates a fresh loopback TCP/SCRAM
cluster, then `qgis_native` and `qgis_native_reader`. The reader has SELECT on
fixture tables and USAGE on fixture sequences (the native default-value method
advances a sequence), plus CREATE in this disposable database's public schema.
The unchanged PostgreSQL-specific `testExtent` creates, populates, indexes,
analyzes and drops `public.test_ext`; it overrides the inherited read-only
extent method. The role cannot edit base fixture tables. Preflight proves the
scratch DDL transaction succeeds and rolls it back, then requires real SQLSTATE
42501 denials for UPDATE, DELETE and INSERT against the base point table. Setup uses the privileged
fixture owner. The controller loads a hash-guarded **unchanged excerpt** of
`tests/testdata/provider/testdata_pg.sql` containing the two required tables and
schemas. The complete donor bootstrap also requires citext/pointcloud/topology
and extra roles, and is not executed or claimed by this selection.

`native_database.py` accepts the runtime configuration keys `python`,
`database_prefix`, `database_evidence`, `spatial_prefix`, `qt_plugins`,
`library_paths`, `python_paths`, plus `qgis_source` and `qgis_build` for the fresh
native source/build. `proj_data`, `gdal_data`, `fontconfig_file` and
`fontconfig_path` can explicitly identify retained resources. The QGIS binding and
library origins are forced to the fresh build; supporting Python paths must
include both retained `usr/lib64/python3.13/site-packages` and
`usr/lib/python3.13/site-packages`, plus the matching built GDAL bindings.

```sh
python3 build-support/qgis/native_database.py \
  --config /absolute/retained/native-config.json \
  --output /absolute/new/native-attempt
```

The database controller executes the native runner under `loopback_exec.py` and
checks its network receipt. PostgreSQL itself uses the inherited documented
exception: its backend `setsid()` is incompatible with that supervisor. Only the
task-owned PID is stopped. Role passwords are randomized, kept in a private local
service file, invalidated with NOLOGIN/PASSWORD NULL and scrubbed from configured
files before shutdown. There is no global PostgreSQL service or user profile
change. The inherited database helper creates an unused `fixture_geofence`
database within this fresh cluster; the receipt identifies it as unused.

The runner preflights import origins, loaded spatial libraries, providers,
required GDAL drivers and fixture database identity/count before test execution.
It isolates HOME/XDG/temp/Qt/QGIS settings, disables PROJ network acquisition and
keeps server requests sequential. Source and fixture/golden-output integrity are
checked before and after execution. Missing discovery, zero tests, selected
skips/expected failures, assertion failures, process exits/timeouts, origin errors,
network enforcement errors and cleanup errors fail the corresponding overall
receipt. Per-command logs, Qt XML, Python result JSON and fixture receipts remain
available even when another test fails.

Engineering status at initial implementation: eleven evidence-guard tests passed;
these are not native QGIS results. A real owned PostgreSQL fixture preflight at
`build-worktrees/qgis-candidate/native-fixture-preflight-001/result.json` verified
five point rows and four polygon rows, invalidated credentials and stopped the
cluster. QGIS native execution must be recorded separately after compilation;
the presence of this selection or passing guard tests does not complete F02-04.

The native controller uses `Popen.wait` with graceful supervisor termination on
timeout or interruption, allowing the unchanged supervisor to reap descendants
before database cleanup. The fourteen harness guards include real child-process
timeout/KeyboardInterrupt checks and database cleanup ordering. An additional
real loopback-supervisor timeout witness at
`build-worktrees/qgis-candidate/native-supervisor-cleanup-01/result.json` confirmed
its expected failed exit, stopped process group and disappearance of both owned
child PIDs. These lifecycle checks are not QGIS native acceptance results.

The native configuration must explicitly provide `xml_prefix`, the separate
compatible libxml2 profile selected for QGIS. Its library directories precede
the original native prefix in the native client environment. The preflight
requires exactly one resolved libxml2 in actual process mappings, inside that
prefix; missing, original-prefix, host, or duplicate XML loading fails. This
profile supplies the HTTP-enabled ABI required by retained SpatiaLite; the
existing loopback network restrictions remain in force. The PostgreSQL helper
continues using its original retained database environment.

Native preflight also requires the exact selected GDAL, PROJ and SQLite shared
libraries from the spatial prefix, and GEOS, GEOS C and libpq from the original
database prefix. Missing, duplicate or cross-prefix mappings fail. Every loaded
Qt5 library and QCA library must resolve to its selected support library; every
Qt plugin must belong to the configured plugin tree, including the exact
offscreen platform plugin. `QT_QPA_PLATFORM_PLUGIN_PATH` pins that private
platform directory. No original-native PROJ override is accepted.
