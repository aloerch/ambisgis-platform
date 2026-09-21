# FND-02 / F02-04 owned QGIS checkpoint

FND-02 remains **In progress**. The [finite checklist](fnd-02-completion.md)
retains its four original criteria and eight rows. The checkpoint begins from
verified owner-merged [PR #62](https://github.com/aloerch/ambisgis-platform/pull/62),
reviewed head `0db4c9190cee633b973a1f5ee9c87e1fa4061bf1`, merge/main
`8e1717ddc9ea33d28f5460c858904723aec05949`. That merge accepts the bounded
frontend/checklist checkpoint, not all FND-02 criteria or license clearance.
The frontend branch/artifacts and original plan checkout's user edits remain.

Platform branch: `fnd-02/qgis-candidate-build`; worktree:
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-qgis`.
Platform repository ID `1376927351`; owned QGIS ID `1376927721`.
Authenticated owner and both remotes were verified before scoped writes.
The [claim](https://github.com/aloerch/ambisgis-platform/issues/3#issuecomment-5756630487)
identifies only F02-04. No source fork, workflow, secret, default branch, deployment
or release change is authorized or made by this checkpoint.

## Candidate and exact profile

Owned QGIS commit `1a4cda5f2620e7374e5926fc955a7d2d06493e15`, tag `final-3_44_14`,
tag object `3f5297ac71ddb19fc959bdff15147608f8901b38`, source tree
`c8542e82e3c3810950f32ce8d58a16bfed12e6c8`.
The retained owned tar is 1,230,551,040 bytes, SHA-256
`229ce420ccf5f993eff29e58dc500f2fe7337395595989f947481c34c8cfb875`.
Its [manifest](../../build-support/qgis/source-inputs.json) also records 133
source notices. QGIS artifacts must be compiled from that owned source; no
publisher QGIS binary or preinstalled host Python package supplies acceptance.

Host: openSUSE Tumbleweed 20260916, x86_64; selected GCC/G++ 15.3.0,
CMake 4.4.3, Python 3.13.14. Four parallel compile jobs were selected after
checking roughly 31 GiB RAM and 2.8 TB available disk. The Qt5 family is
5.15.19 with publisher KDE patches; PyQt5 5.15.10, SIP generator 6.16.1,
PyQt-builder 1.19.1, QScintilla 2.14.1 and SWIG 4.4.1 are retained supporting
inputs. The [separate support/rights audit](qgis-dependency-audit.md) and exact
[package manifest](../../build-support/qgis/support-inputs.json) control details.
The selected `support-07` contains 106 binary packages and 44 corresponding
source RPMs, signature/hash checked; 338 notice files and all 13,469 inventory
entries are retained. This is not an independently bootstrapped Qt/compiler
toolchain. Its full 25-component Qt and actual FastCGI link/runtime preflight
passed, with no dangling shared-library links or unresolved probe dependencies.

The original `postgis-slice/run-003/prefix` stays unchanged and is compared to
its original retained output archive, not a newly asserted snapshot. It supplies
PostgreSQL 15.19, PostGIS 3.5.7 and GEOS 3.13.1. The separate `spatial-04/prefix`
compiles retained SQLite 3.50.4 with RTree/column metadata and a SONAME,
PROJ 9.6.2 against that SQLite, and GDAL 3.10.3 with CSV/GeoPackage/SQLite/GEOS.
This supplies the local-format and unchanged native-test prerequisites without
overwriting the verified database/backend combination. Actual dynamic origins
and resource hashes are acceptance evidence beyond matching version labels.

The QGIS-only `xml-profile-01/prefix` additionally supplies unchanged retained
libxml2 2.14.6 with HTTP enabled, restoring the cleanup API required by retained
SpatiaLite. The original database environment still selects original native XML.
All QGIS clients must map exactly the separate XML artifact. HTTP implementation
availability does not bypass the existing socket controls or establish HTTP
feature/security acceptance.

The [recipe](../../build-support/qgis/README.md) documents required enabled
capabilities and exclusions. Desktop/server/PyQGIS, vector/raster/CRS/PostGIS,
authentication and service support stay enabled. 3D, PDAL/Draco, GRASS,
Oracle/HANA, embedded web engines, OpenCL, QtQuick application, gamepad,
crash-handler integration and landing-page web UI are excluded. COPC/EPT and
embedded laz-perf are enabled because this exact source has unconditional
core/GUI dependencies on them; their optional capabilities remain unexercised
and unaccepted. Required vector/raster/CRS/PostGIS scope is unchanged. Optional MDAL
HDF5/NetCDF mesh formats are absent; the local GeoTIFF witness is unaffected. No Windows/macOS,
physical-display or full provider/cartographic/OGC acceptance is inferred.

## Retained attempts and measured evidence

Common retained root:
`/home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate`.
Sources/packages: `/home/revelberry/Projects/AmbisGIS/source-archives/qgis-candidate`;
existing native sources: sibling `source-archives/postgis-slice`.
Every attempt has fresh state and failed attempts are preserved.

- `spatial-01`: configure rejected SQLite without RTree.
- `spatial-02`: first extended GDAL built; subsequent ELF audit found old PROJ's
  absolute SQLite dependency, so this is not the selected spatial output.
- `spatial-03`: new SQLite/PROJ compiled, but an indirect application link selected
  old SQLite and failed for missing column-metadata symbols.
- `spatial-04`: explicit private linker search fixed that selection; SQLite/PROJ/
  GDAL compilation, RTree/driver/CRS probes and input-integrity checks passed.
- `build-01`: QGIS configure failed for missing QCA OpenSSL provider; retained
  publisher main QCA package fixes it without changing the owned QGIS revision.
- `build-02`: QGIS configure failed for missing nested Qt Multimedia dependencies.
  Full nested-module audit also identified UiTools' OpenGL development prerequisite.
- `build-03`: QGIS configure reached server setup, then rejected missing FastCGI.
  Its development package contained dangling library symlinks; the exact runtime
  payload and three SpatiaLite development linker packages are retained in fresh
  support-06. Explicit FastCGI/Qwt header paths fix inherited finder assumptions.
- `build-04`: full effective configuration passed, then compilation failed at
  `qgspointcloudlayer.cpp` because COPC-off removes VPC headers still used
  unconditionally by core/GUI. Source review found broader COPC/EPT dependencies;
  the next profile enables those native default paths with bundled laz-perf and
  retained ZSTD, keeping PDAL/3D disabled. No owned-source patch is required by
  this repair. Two unused uppercase SQLite cache hints are preserved in this
  failed attempt; effective `SQLite3_*` paths were correct and the next recipe
  pins the correctly cased variables. CMake deprecated-target warnings remain
  unsuppressed.
- `python-gdal-01`: initial source-built bindings and supplemental raster/origin
  audit passed; review required stronger recipe/source integrity receipts.
- `python-gdal-02`: corrected fresh build passed all six offline commands, real
  NumPy raster round trip, exact extension/spatial origins and full producer/input
  integrity checks. All 3,696 original source files remain unchanged; exactly
  seven generated egg-info metadata files are recorded. Its support producer is
  preserved support-05; later support-06 adds the missing C++ dependencies and
  retains the same Qt/Python payload versions. Final support-07 preserves every
  support-05 payload byte/mode/symlink; only its package manifest changes while
  additional inputs are retained. The output has 106 files.
- `elf-preflight-01`: all 58 selected ELF inputs resolve their dependencies;
  grouped strict relocation clears standalone GSL/CBLAS cross-library warnings
  and proves one real SpatiaLite ABI failure: missing `xmlNanoHTTPCleanup` in
  original minimal libxml2. Host transitives remain separately enumerated.
- `xml-profile-01`: unchanged retained libxml2 2.14.6 compiled with HTTP enabled
  into a separate prefix. All 48 build steps and five offline phases passed;
  116 output files and 3,913 unchanged source files are inventoried. Required
  symbol export and actual SpatiaLite strict relocation/origin checks pass.
- `build-05`: passed the previous failing point-cloud compilation, then was
  deliberately interrupted after the independent actual XML ABI failure proof.
  Its 2,716 completed production steps are partial compilation, not acceptance
  or an invented compiler failure. Exact owned Ninja received SIGINT; no task
  process remains and the overall receipt is failed.
- `elf-preflight-02`: fresh grouped strict load passes all 58 selected libraries,
  with one actual XML mapping from xml-profile-01 and correct Qt/spatial origins.
  This repairs the measured ABI gap; final executable maps remain mandatory.
- `build-06`: fresh production compilation completed all 3,989 steps; private
  staging, explicit CRS synchronization (zero errors), six native executable
  targets (24 steps) and desktop/server linkage passed. The final source equality
  guard rejected one generated `grassprovider/description/algorithms.json`; all
  33,579 original source files remain unchanged. The exact inherited CMake rule
  generates this 307-record processing metadata even with native GRASS disabled.
  The failed receipt is preserved. `build06-audit-01` subsequently verified all
  seven completed phases, their commands/logs/kernel denial probes, original
  inventory against the retained tar, all selected input inventories and all
  staged/native artifacts. The metadata reproduces byte for byte offline and
  matches the installed copy. Its separate manifest has **9,235 entries /
  473,998,759 regular-file bytes**, SHA-256
  `931e5f0523e1d9bdba6b2fbd27e6c208297456db696265beb961a57e77ed82c9`.
  No compilation or installation was repeated; this is verification of the clean
  build, not a warm replay or a byte-identical rebuild claim.

**F02-04's bounded Linux engineering result is demonstrated.** The exact
compiled desktop/server/bindings, selected native tests and complete runtime
witness have passed. [The compact evidence index](../verification/qgis-candidate/evidence.json)
binds their inputs, commands, artifacts and receipts. Owner review of this
checkpoint remains separate from whole-task, distribution or license acceptance.

Runtime failures remain preserved: `runtime-01` passed fixture/provider/CRS/GEOS
checks but the Unix desktop launcher required `DISPLAY` presence before Qt setup.
An empty task-local value permits its check while Qt remains explicitly offscreen.
`runtime-02` passed six actual canvas renders, zoom, save/reopen and exact origins,
then crashed during shutdown because the harness bypassed the native File Exit
cleanup. The harness now uses that action and retains exact process return codes.
Independent visual review also found missing UI text: a supervised font probe
showed an empty offscreen default family, zero rendered text pixels, and correct
retained QGIS Vera Sans rendering when explicitly selected. These are harness/
private-profile repairs; the compiled candidate and native-test results stay fixed.
Neither failed runtime attempt demonstrates the full row.

The real synthetic-data preflights generated identical GeoJSON/GeoTIFF hashes;
the fresh owned PostgreSQL fixture verified restricted write denial, then
invalidated credentials and stopped. The separate native fixture loaded five
point and four polygon donor rows. These establish prerequisites only.
The [runtime contract](../../build-support/qgis/runtime.md) requires a real Qt
offscreen desktop event loop/canvas, interaction/save/reopen and six real native
HTTP WMS requests over two sequential server processes. The [native selection](../../build-support/qgis/native-tests.md)
executed unchanged tests in `native-01`: six C++ targets, 55 selected methods
expanding to **66 passing QtTest cases**, plus **16 passing Python tests** across
six groups. There were zero failures, errors or skips. The selected source/golden
fixture tree stayed unchanged; exact spatial/XML/Qt/offscreen origins and kernel
network probes passed. The separate disposable native database permitted scratch
DDL needed by the inherited extent test, while real base-table INSERT/UPDATE/DELETE
attempts all failed with SQLSTATE 42501. Credentials were invalidated and the
supervised processes and database stopped. This does not claim the full QGIS suite.

Fresh package validation passed **203 tests** and all four schema/example
checks using `/tmp/ambisgis-validation-venv/bin/python` in the IDE namespace.
The host `/tmp` is different. Fresh integrated harness checks passed **57 tests**;
**15 shared loopback-supervision regressions** passed. Historical database, Java,
frontend and Jupyter native results were not rerun or relabeled as fresh.

## Executed desktop/server witness

`runtime-04` passes the full controller, fixture, desktop and server receipts.
The actual staged desktop executes under **Qt offscreen**: six completed canvas
renders, zoom by 0.8, native Save Project, clear/reopen, and native File Exit with
process exit zero. Retained QGIS Vera Sans 12pt supplies readable interface text;
its actual glyph witness has 1,098 dark pixels. Captures were independently viewed; retained review previews are the
[real desktop window](../verification/qgis-candidate/desktop-reopened-window.png)
and [native HTTP GetMap](../verification/qgis-candidate/server-combined.png).
There is no physical-display or full browser/accessibility acceptance.
The earlier functionally passing `runtime-03` showed a blocked optional Open Sans
font-download warning. The final disposable profile sets the exact supported
`fonts/downloadMissingFonts=false`; the desktop verifies it and rejects any
remaining font-installation warning. No font is fetched or warning dismissed.

Both local GeoJSON and restricted PostGIS reads return IDs 1/2/3, expected
attributes and points `(1,1)`, `(3,1)`, `(2,3)`. The 16×16 GeoTIFF spans `[0,4]²`
and its four known quadrants read/render 40/90/150/210. EPSG:4326 `(1,1)` maps to
`(111319.49079327357,111325.1428663851)` in EPSG:3857 within `1e-6` meters,
without ballpark/fallback. The GEOS intersection equals the independently fixed
unit square, area 1. The fixture role's attempted INSERT fails even after turning
off its default read-only setting.

Native `qgis_mapserver` serves six **real HTTP** requests sequentially: first
GetCapabilities and combined/local-only/database-only GetMap, then capabilities
and combined GetMap after one restart on the same loopback port. WMS 1.1.1 uses
SRS EPSG:4326, longitude/latitude BBOX `0,0,4,4`, size 512×512. Both server processes
exit zero. All images have expected raster values and point placement; isolated
responses also have zero omitted-layer marker pixels. These checks do not require
pixel-identical desktop/server output or establish full OGC conformance.

Actual process maps require singleton selected GDAL/PROJ/SQLite, original
GEOS/libpq, separate XML and staged QGIS/PostgreSQL provider, retained Qt/QCA
modules/plugins and offscreen plugin. Prefix/tooling integrity stays unchanged.
All 79 parent and 79 exec-child loopback probes pass. The process group/listeners
and disposable database stop, all fixture login secrets are invalidated, private
files scrubbed, and diagnostic secret scans report zero hits.

## Reproduce or resume

Run host commands from the platform worktree. Use a **new output path** for every
attempt; do not overwrite these receipts. The exact complete build command is in
`build-06/*-command.json`, with source extraction and bounded four-job compilation
in the executed `build-06/recipe/build.py`. Its failed final guard and successful
separate reconciliation must be read together. Future builds use the corrected
committed recipe, which reproduces the single generated metadata file itself.

```sh
flatpak-spawn --host python3 build-support/qgis/reconcile.py \
  --attempt /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/build-06 \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/build06-audit-NEW
flatpak-spawn --host python3 build-support/qgis/runtime.py \
  --config /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/config-preflight-04/runtime-config.template.json \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/runtime-NEW
flatpak-spawn --host python3 build-support/qgis/native_database.py \
  --config /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/config-preflight-04/native-config.template.json \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/native-NEW
```

These are executable reproduction commands, not an instruction to rerun successful
checks without changed inputs. Artifact paths are `build-06/prefix`,
`build-06/build/output/bin`, `spatial-04/prefix`, `xml-profile-01/prefix`,
`python-gdal-02/python`, `support-07`, and unchanged `postgis-slice/run-003/prefix`.
The config templates identify all fonts, Qt plugins, Python paths and CRS resources.

## Containment, decisions and finite continuation

Build subprocesses use the existing Internet-socket-denial runner with measured
kernel probes, task-local empty caches and retained inputs. Runtime subprocesses
use the existing loopback supervisor. Neither mechanism is hostile-code/file
isolation. The documented PostgreSQL-only supervision exception remains explicit:
fresh owned server, loopback TCP/SCRAM only, no Unix listeners, task-owned shutdown
and secret invalidation/scrubbing. No global installs/profile edits or security
controls are disabled. Host base-library/source/bootstrap closure stays open.

Frontend five inherited lint errors, five webpack warnings, nonidentical replay
and web-ifc/other rights findings remain F02-06. The Java ledger remains
48 structural / 12 unresolved / four partial and does not describe this new
QGIS/Qt/binding inventory. Retaining licenses does not grant legal clearance. The selected resource install
rules include 256 palettes with noncommercial terms and 138 palettes explicitly
marked `distribute="no"`, plus custom ElvenSword/Mossman/ColorBrewer conditions
and an icon notice absent from generated installation. Exact source hashes and
reachability are in the separate support evidence. These are F02-06 selection/
redistribution questions requiring disposition, not blanket deferred clearance;
no distribution or commercial-use approval is claimed.

Stop engineering at F02-04. When its full bounded result is demonstrated, the
next finite focus is F02-05's missing selected-combination evidence, including
the embedded GeoWebCache tile-response gap; then F02-06/07/08 consolidation,
maintenance binding and explicit owner acceptance. FND-05 publishing, new role/
cache milestones, installers/rebranding and unrelated Java recovery remain out
of scope. Human review gates merging and later license/security/release decisions. No owner
acceptance of the whole task is inferred. The final runtime implementation is
`041f5c1`; the executed build snapshot and subsequent strict audit have separate
hashes in the evidence index.

## Published review checkpoint

[PR #63](https://github.com/aloerch/ambisgis-platform/pull/63) is open against
`ambisgis/main`, branch `fnd-02/qgis-candidate-build`. Tested runtime implementation:
`041f5c1d9601ac3f4c2ea6f3dc4ab73b3d88fbcd`; initial evidence/publication head:
`4e99852fc981d4b2e929c81cce292aedc933b526`. Later commits bind publication evidence
only; the live PR and final issue comment identify the latest review head.

[Project reconciliation](../verification/qgis-candidate/project.json) verifies
75 prior items unchanged and one new PR item: **76 items**, saved `is:pr is:open`
queue **#63 only**. Exactly two authorized mutations added the actual PR content
identity and set its Evidence link to the PR and issue #3. The immediate API read
was stale and failed; a later complete read-only reconciliation proves the result
without replaying writes. All represented prior fields/archive decisions and
Project/view configuration remain unchanged. No Task ID or parent Delivery was
assigned to the PR; FND-02 stays In progress. No UI setup claim is made.

Owner action is bounded review of this PR's build, runtime/native evidence,
omissions and recorded rights blockers before any merge. Review does not block
independent F02-05 engineering and does not accept all four FND-02 criteria or
clear distribution rights. The original plan checkout's STATUS.md user edit and
all prior frontend/source/build branches and artifacts remain preserved.
