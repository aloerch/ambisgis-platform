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
Publisher packages and corresponding source RPMs are retained and signature/hash
checked; this is not an independently bootstrapped Qt/compiler toolchain.

The original `postgis-slice/run-003/prefix` stays unchanged and is compared to
its original retained output archive, not a newly asserted snapshot. It supplies
PostgreSQL 15.19, PostGIS 3.5.7 and GEOS 3.13.1. The separate `spatial-04/prefix`
compiles retained SQLite 3.50.4 with RTree/column metadata and a SONAME,
PROJ 9.6.2 against that SQLite, and GDAL 3.10.3 with CSV/GeoPackage/SQLite/GEOS.
This supplies the local-format and unchanged native-test prerequisites without
overwriting the verified database/backend combination. Actual dynamic origins
and resource hashes are acceptance evidence beyond matching version labels.

The [recipe](../../build-support/qgis/README.md) documents required enabled
capabilities and exclusions. Desktop/server/PyQGIS, vector/raster/CRS/PostGIS,
authentication and service support stay enabled. 3D/point clouds, GRASS,
Oracle/HANA, embedded web engines, OpenCL, QtQuick application, gamepad,
crash-handler integration and landing-page web UI are excluded. No Windows/macOS,
physical-display or full provider/cartographic/OGC acceptance is inferred.

## Retained attempts and currently measured evidence

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
- `python-gdal-01`: matching source-built Python bindings passed import and a
  separate actual NumPy raster round trip/origin audit. A review required stronger
  recipe/source integrity receipts; the corrected recipe requires a fresh run.

At this documentation stage, **actual QGIS desktop/server compilation and native/
runtime acceptance remain pending**. Planned tests or successful fixtures do not
establish the row. Final attempt receipts and the final evidence index must
supersede this interim statement before any demonstrated result is claimed.

The real synthetic-data preflights generated identical GeoJSON/GeoTIFF hashes;
the fresh owned PostgreSQL fixture verified restricted write denial, then
invalidated credentials and stopped. The separate native fixture loaded five
point and four polygon donor rows. These establish prerequisites only.
The [runtime contract](../../build-support/qgis/runtime.md) requires a real Qt
offscreen desktop event loop/canvas, interaction/save/reopen and six real native
HTTP WMS requests over two sequential server processes. The [native selection](../../build-support/qgis/native-tests.md)
requires unchanged six C++ targets and sixteen Python methods; planned counts are
not results. Native source/golden outputs cannot be rewritten to obtain a pass.

Fresh package validation currently passed 190 tests and all four schema/example
checks using `/tmp/ambisgis-validation-venv/bin/python` in the IDE namespace.
The host `/tmp` is different. Fresh integrated harness checks passed 32 tests;
15 shared loopback-supervision regressions passed. Historical database, Java,
frontend and Jupyter native results were not rerun or relabeled as fresh.

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
QGIS/Qt/binding inventory. Retaining licenses does not grant legal clearance.

Stop engineering at F02-04. When its full bounded result is demonstrated, the
next finite focus is F02-05's missing selected-combination evidence, including
the embedded GeoWebCache tile-response gap; then F02-06/07/08 consolidation,
maintenance binding and explicit owner acceptance. FND-05 publishing, new role/
cache milestones, installers/rebranding and unrelated Java recovery remain out
of scope. Human review gates merging and later license/security/release decisions.
