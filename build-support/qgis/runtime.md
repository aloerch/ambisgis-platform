# F02-04 runtime witness

This is a bounded synthetic Linux desktop/server probe. It does not implement
FND-05 publication, multi-platform packaging, full cartographic parity, hostile
project isolation or release acceptance. A harness commit or its guard tests do
not establish QGIS runtime acceptance; only a complete successful attempt receipt
from newly compiled owned artifacts does.

Run on the host (the IDE's `/tmp` is a different filesystem), using an explicit
public JSON configuration and a **new** retained attempt directory:

```sh
/usr/bin/python3 build-support/qgis/runtime.py \
  --config /absolute/path/to/runtime-inputs.json \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/runtime-01
```

Required configuration keys are `python`, `qgis_prefix`, `spatial_prefix`,
`database_prefix`, `database_evidence`, `support_prefix`, `qt_plugins`,
`font_file`, `gdal_library`, `library_paths` and `python_paths`. Paths are absolute;
the last two values are ordered directory lists. `spatial_prefix` may be the
separate QGIS GDAL extension prefix; `database_prefix` remains the verified
PostgreSQL/PostGIS/native prefix. Put the QGIS-only GDAL directory before the
original prefix in `library_paths`. `python_paths` must explicitly include staged
PyQGIS and the selected retained PyQt/SIP support. The default executables are
`qgis_prefix/bin/qgis` and `qgis_prefix/bin/qgis_mapserver`.

Optional explicit path overrides are `desktop`, `server`, `provider_path`,
`proj_data` and `gdal_data`. Both executable overrides must remain inside the
staged QGIS prefix. The compiled library/provider prefix and actual loaded
mappings must match these paths; host QGIS and Qt cannot satisfy the witness.
Support Qt5 mappings must be inside `support_prefix`. General host libraries are
listed in actual mappings and remain the broader dependency-closure gate.

The generator writes three GeoJSON point features: `(id,label,x,y)` values
`(1,alpha,1,1)`, `(2,beta,3,1)`, `(3,gamma,2,3)`. GeoJSON is included in the measured
original retained GDAL profile. The 16×16 one-band Byte GeoTIFF covers longitude
0–4 and latitude 0–4, with northwest/northeast/southwest/southeast quadrants valued
40/90/150/210. Generation uses the explicit retained GDAL C library through
`ctypes`; it requires no unrelated Python GDAL package. Each file's hash is
retained. The same point rows are inserted into a fresh fixture database.

QGIS reads feature IDs, attributes, counts and coordinates through its real OGR
and PostgreSQL providers, and checks raster dimensions, extent and samples through
its GDAL provider. EPSG:4326 `(1°,1°)` must transform to EPSG:3857
`(111319.49079327357,111325.1428663851)` meters within 1 micrometer. These fixed
Web Mercator values are independent of the QGIS function being tested; fallback
and ballpark transforms are disabled. The intersection of squares `[0,2]²` and
`[1,3]²` must equal `[1,2]²` topologically and have area 1 within `1e-12`.
`proj.db`, loaded GEOS/PROJ/GDAL/libpq and the retained font are hashed.

A `.qgs` project uses the local and database points over a grayscale raster. Red
circles show local features and smaller blue squares show equivalent PostgreSQL
features. The project carries only a libpq service name; the SCRAM password is in
a fresh mode-0600 pgpass file. The runtime role has SELECT only, no owner/admin
rights, and a read-only default. A real attempted INSERT must fail even after
disabling that default. No managed branch tables or existing services are used.

Desktop acceptance launches the actual staged `qgis` binary with a fresh profile,
`--noplugins`, `--noversioncheck` and `--code desktop_witness.py`. The profile's
optional news feed is disabled through the selected source's documented setting.
Qt offscreen is explicitly used; this establishes no physical-display acceptance.
The embedded script observes the real desktop event loop and completed canvas
renders, checks layer state, zooms, uses the actual Save Project action, clears the
project, reopens it and checks the second canvas. `saveAsImage` without a supplied
pixmap copies the current map canvas content in this exact source; it does not
substitute a separate standalone render. Application-window captures supplement
these assertions.

Server acceptance launches the staged native `qgis_mapserver` directly on
`127.0.0.1` under the unchanged loopback supervisor. Requests are sequential.
WMS 1.1.1 uses SRS EPSG:4326 and longitude/latitude BBOX `0,0,4,4`, at 512×512.
The first process receives GetCapabilities and combined/local/database GetMap;
after verified shutdown a second process on the same port repeats capabilities
and combined GetMap. These are six real HTTP requests, not CGI or manufactured
responses. XML exception documents, absent layers and non-PNG maps fail.
Raster values are checked at spatially fixed interior positions. Each point must
have its expected marker colors near its independent coordinate. Tolerances allow
8 grayscale levels and 20 color levels within a 24-pixel marker neighborhood;
blank, absent and misplaced features fail. Desktop and server pixel identity is
not required.

Each attempt snapshots the executed scripts, verifies staged/native file hashes
before and after, and retains supervisor probes and cleanup. QGIS subprocesses
inherit the existing loopback-only seccomp supervisor. The existing PostgreSQL
exception is explicit: the fresh owned server alone stays outside that supervisor
because its backend `setsid` is rejected. It listens only on authenticated loopback
TCP, with Unix listeners disabled. This mechanism does not isolate files or block
other pre-existing loopback services and is not a hostile-code sandbox. No browser
sandbox setting is changed. Fontconfig, Qt, Python, settings, caches, auth database,
plugin and temporary paths are task-owned; external fetching cannot supply inputs.

Capture errors, secret diagnostics, runtime assertions, unexpected origins,
integrity changes, failed supervisor proof and cleanup errors fail `result.json`,
even if desktop/server processes exit zero. All fixture roles are made NOLOGIN
and their passwords nulled before PostgreSQL shutdown; private files are scrubbed.
Failed attempt directories must be retained. A later success uses a new directory.

Guard tests:

```sh
python3 -m unittest discover -s build-support/qgis -p 'test_runtime.py' -v
```

Fresh preflight evidence from this implementation is retained under
`build-worktrees/qgis-candidate/runtime-data-preflight-01`,
`runtime-data-preflight-02` and `runtime-database-preflight-01`. Two data generations
had identical GeoJSON SHA-256
`bf60f75d0d4d37cc1d5efd5b37794263b08c67e3077ed0d7e6c1314cefa38f7c`
and GeoTIFF SHA-256
`cd8b73ec7035be3c41deea9011e848d8c5099dc219356744beb6a13300cede4d`.
Retained `gdalinfo`/`ogrinfo` read them, and real restricted PostgreSQL credential
setup, write denial, password invalidation and shutdown passed. These preflights
are data/database setup evidence only; they do not claim QGIS compiled or ran.
The retained complete attempt receipts control desktop/server evidence state.
