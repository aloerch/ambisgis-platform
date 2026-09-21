# F02-04 QGIS supporting input audit

This inventory belongs to the QGIS candidate at `1a4cda5f2620e7374e5926fc955a7d2d06493e15`, independently of the Java ledger and frontend findings. It is supporting-input evidence, not QGIS product acceptance or license clearance.

## Selected family and actual constraints

The owned candidate reports QGIS 3.44.14 Solothurn. Its `CMakeLists.txt` requires CMake 3.22, Python 3.9 and Qt 5.15.2 or later; `INSTALL.md` retains older CMake/Python minimums. The selected host profile is Qt 5.15.19, Python 3.13.14, PyQt5 5.15.10, SIP generator 6.16.1, PyQt-builder 1.19.1 and QScintilla 2.14.1. The retained PyQt5 SIP runtime is package version 12.16.1; that runtime reports generator version 6.9.1, which is distinct from the selected binding generator. The candidate generated-binding contract allows SIP >=5,<7 and PyQt-builder >=1.6,<2; Qt5 bindings request ABI 12.16 when SIP >=6.9.

Top-level required Qt modules are Core, Gui, Widgets, Network, Xml, Svg, Concurrent, Test, Sql and Positioning; PrintSupport and SerialPort remain available. Nested GUI CMake additionally requires Multimedia, MultimediaWidgets, Qml, QuickWidgets and UiTools; application CMake also requires UiTools, native Linux CMake requires DBus, and translation CMake requires LinguistTools. Quick is brought in by QuickWidgets. The Qt tools development package and its Designer/Help/runtime tools are retained together. Qt5UiTools static-link metadata requires GL, supplied by retained libglvnd and Mesa GL/EGL/KHR development headers. Qwt 6.3.0, QCA 2.3.12, QtKeychain 0.17.0, FastCGI 2.4.7, Exiv2 0.28.9, GSL 2.8, libzip 1.11.4 and SpatiaLite 5.1.0 are retained supporting publisher inputs. Native GEOS/PROJ/GDAL/libpq selection is controlled by the actual build recipe and loaded-origin evidence, not these supporting RPM versions.

Keep `BUILD_WITH_QT6=OFF`, `WITH_DESKTOP=ON`, `WITH_GUI=ON`, `WITH_PYTHON=ON`, `WITH_BINDINGS=ON`, `WITH_SERVER=ON`, `WITH_SERVER_PLUGINS=ON`, `WITH_POSTGRESQL=ON`, `WITH_SPATIALITE=ON`, `WITH_ANALYSIS=ON` and `ENABLE_TESTS=ON`. Optional exclusions supported by exact source options include `WITH_3D`, `WITH_PDAL`, `WITH_EPT`, `WITH_COPC`, `WITH_DRACO`, `WITH_GRASS7`, `WITH_GRASS8`, `WITH_QTWEBKIT`, `WITH_QTWEBENGINE`, `USE_OPENCL` and `WITH_SERVER_LANDINGPAGE_WEBAPP`; these exclude 3D/point-cloud/GRASS/embedded browser/GPU/landing-page UI capabilities and cannot be advertised by this profile. `WITH_INTERNAL_SPATIALINDEX=ON` uses retained embedded source and avoids the candidate's explicit rejection of external spatialindex >=2.1. Final chosen options remain the build receipt's authority.

## Retained publisher inputs

`build-support/qgis/support-inputs.json` pins every supporting binary RPM and its corresponding source RPM by exact name, epoch, version, release, architecture, repository path and publisher digest. The binary/source repository metadata and detached signatures are retained. Binary metadata came from the host's cached official `repo-oss`; source metadata was fetched explicitly over HTTPS. All selected RPM payloads have publisher SHA512 checks; `rpmkeys --checksig` also verifies RPM signatures against the host RPM trust store. This is publisher package custody, not an independently rebuilt Qt/general dependency toolchain.

There are 104 selected binary supporting packages (82,048,039 bytes) and 43 exact corresponding source RPMs (298,562,724 bytes). No QGIS binary RPM supplies any product artifact. Native Qt, Python and support development headers, runtime libraries and Python modules are retained together. NumPy, psycopg2, lxml and OWSLib prerequisites support actual donor tests. SWIG is retained for controlled GDAL bindings generation if needed.

| Source package | Version-release | Publisher license metadata |
|---|---|---|
| FastCGI | 2.4.7-1.7 | OML |
| Mesa | 26.2.2-2.1 | MIT |
| exiv2 | 0.28.9-3.1 | BSD-3-Clause AND GPL-2.0-or-later |
| expat | 2.8.4-1.1 | MIT |
| freexl | 2.0.0-1.9 | GPL-2.0-or-later OR MPL-1.1 OR LGPL-2.1-or-later |
| gsl | 2.8-5.4 | GPL-3.0-or-later |
| libglvnd | 1.7.0-2.4 | MIT |
| libqt5-qtbase | 5.15.19+kde96-1.3 | LGPL-3.0-only or GPL-3.0-with-Qt-Company-Qt-exception-1.1 |
| libqt5-qtdeclarative | 5.15.19+kde23-1.3 | LGPL-3.0-only OR (GPL-2.0-only OR GPL-3.0-or-later) |
| libqt5-qtlocation | 5.15.19+kde7-1.3 | LGPL-3.0-only OR (GPL-2.0-only OR GPL-3.0-or-later) |
| libqt5-qtmultimedia | 5.15.19+kde2-1.3 | LGPL-3.0-only OR (GPL-2.0-only OR GPL-3.0-or-later) |
| libqt5-qtserialport | 5.15.19+kde0-1.3 | LGPL-3.0-only OR (GPL-2.0-only OR GPL-3.0-or-later) |
| libqt5-qtsvg | 5.15.19+kde5-1.3 | LGPL-3.0-only OR (GPL-2.0-only OR GPL-3.0-or-later) |
| libqt5-qttools | 5.15.19+kde3-1.9 | (LGPL-3.0-only OR (GPL-2.0-only OR GPL-3.0-or-later)) AND GPL-3.0-only WITH Qt-GPL-exception-1.0 |
| librttopo | 1.1.0-3.7 | GPL-2.0-or-later |
| libspatialite | 5.1.0-1.11 | MPL-1.1 |
| libzip | 1.11.4-1.5 | BSD-3-Clause |
| python-OWSLib | 0.36.0-1.1 | BSD-3-Clause |
| python-certifi | 2026.7.22-1.1 | MPL-2.0 |
| python-charset-normalizer | 3.4.9-1.1 | MIT |
| python-idna | 3.19-1.1 | BSD-3-Clause |
| python-lxml | 6.1.1-2.2 | BSD-3-Clause AND GPL-2.0-or-later |
| python-numpy | 2.5.3-1.1 | BSD-3-Clause |
| python-psycopg2 | 2.9.12-1.3 | LGPL-3.0-or-later AND (LGPL-3.0-or-later OR ZPL-2.0) AND LicenseRef-SUSE-GPL-2.0-with-openssl-exception |
| python-pyproj | 3.8.0-1.1 | LicenseRef-SUSE-Public-Domain AND X11 |
| python-pyqt-builder | 1.19.1-1.1 | BSD-2-Clause |
| python-python-dateutil | 2.9.0.post0-2.8 | Apache-2.0 OR BSD-3-Clause |
| python-pytz | 2026.3.post1-1.1 | MIT |
| python-qt5 | 5.15.10-4.8 | SUSE-GPL-2.0-with-FLOSS-exception OR GPL-3.0-only OR NonFree |
| python-qt5-sip | 12.16.1-2.6 | BSD-2-Clause |
| python-requests | 2.34.2-1.2 | Apache-2.0 |
| python-sip6 | 6.16.1-1.1 | BSD-2-Clause |
| python-six | 1.17.0-2.1 | MIT |
| python-urllib3 | 2.7.0-2.3 | MIT |
| python313-packaging | 26.3-1.1 | Apache-2.0 AND BSD-2-Clause |
| python313-setuptools | 80.9.0-3.2 | Apache-2.0 AND MIT AND BSD-2-Clause AND Python-2.0 |
| qca-qt5 | 2.3.12-1.1 | LGPL-2.1-or-later |
| qscintilla-qt5 | 2.14.1-3.6 | GPL-3.0-only |
| qtkeychain-qt5 | 0.17.0-1.1 | BSD-2-Clause |
| qwt6-qt5 | 6.3.0-1.7 | SUSE-QWT-1.0 |
| swig | 4.4.1-2.3 | BSD-3-Clause AND GPL-3.0-or-later |
| timezone | 2026d-1.1 | BSD-3-Clause AND LicenseRef-SUSE-Public-Domain |
| zlib | 1.3.1-3.3 | Zlib |

The table copies publisher classification; it does not resolve all combination, redistribution, notice, trademark or source-offer obligations. Original RPMs and source archives are retained unchanged. The extracted private prefix retains publisher notices under `usr/share/licenses`; the final selected support-06 prefix contains 334 notice files. A broader source bootstrap and host runtime closure remain later gates, as authorized by this bounded checkpoint.

## Acquisition, extraction and private paths

Run `acquisition.py fetch`, `fetch-sources` and `extract` with the committed manifest, retained root and a fresh task prefix. `fetch` is the only network operation. Downloaded bytes must match recorded publisher hashes and RPM signatures. Partial downloads are preserved. Extraction queries RPM identity and records scriptlets, then reads `rpm2cpio`; it never installs an RPM or executes its scriptlets. It rejects traversal, unsupported special files, writes through symlink ancestors and nonidentical collisions. It strips special permission bits. Large RPMs, payloads and inventories stay outside Git.

```sh
python3 build-support/qgis/acquisition.py fetch --manifest build-support/qgis/support-inputs.json --retained /home/revelberry/Projects/AmbisGIS/source-archives/qgis-candidate
python3 build-support/qgis/acquisition.py fetch-sources --manifest build-support/qgis/support-inputs.json --retained /home/revelberry/Projects/AmbisGIS/source-archives/qgis-candidate
python3 build-support/qgis/acquisition.py extract --manifest build-support/qgis/support-inputs.json --retained /home/revelberry/Projects/AmbisGIS/source-archives/qgis-candidate --prefix /home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate/support-FRESH
```

The host executes these tools through `flatpak-spawn --host` where required. That bridge is not hostile-code isolation. Extraction prefixes are task-owned. The final selected supporting prefix is `build-worktrees/qgis-candidate/support-06/usr`; its adjacent `support-06-inventory.json` records every file hash and symlink. The existing `support`, `support-02`, `support-03`, `support-04`, `support-05` prefixes and unsuccessful/incomplete extraction snapshots are preserved. The selected inventory contains 13,454 entries and has SHA256 `06de03811bcd7da6df84ece3f995c84a7493397dceacbe1d75b19f26b0402eac`; its embedded support manifest has SHA256 `0a58fccd0103ed8d8309f01d51a07bd3a3577ad489242b6a4fd2ee6882ebf1de`. Compact acquisition, metadata, source/notice, preflight and limitation evidence is in `plan/verification/qgis-candidate/support.json`.

Qt qmake self-relocates to this private prefix; no `qt.conf` or CMake import edits were required by the observed query. Set `CMAKE_PREFIX_PATH` to include the selected native and supporting prefixes. Add `-isystem <support>/usr/include` to both C and C++ flags because retained GL headers are beside, rather than inside, Qt include directories; set both private Python `lib64/python3.13/site-packages` and `lib/python3.13/site-packages` paths; keep `PYTHONNOUSERSITE=1` and `PYTHONDONTWRITEBYTECODE=1`. Explicitly select `SIP_BUILD_EXECUTABLE=<support>/usr/bin/sip-build-3.13`: generic publisher `sip-build -> alts` requires unexecuted system integration and is not the selected executable. `pyuic5` is explicitly remapped to its retained versioned Python3.13 launcher. `lrelease` and `lupdate` come from the separate `libqt5-linguist` runtime package; its development package alone contains only CMake support.

Five exact alternatives targets are replaced only inside the extracted prefix: pylupdate5, pyrcc5 and pyuic5 point to their `-3.13` tools; pyqt5-sip points to `usr/share/pyqt5-sip-3.13`; pyproj points to `pyproj-3.13`. Twelve unused publisher Python command aliases still point to `alts`; selected build commands use the retained versioned launchers. Retained timezone data resolves the selected pytz module's private zoneinfo link. Other absolute `/usr` symlinks become equivalent private relative links. Unknown external absolute targets still fail. No `/etc/alternatives` or user/global configuration is changed.

## Observed failures and coherence checks

The first extraction safely rejected `/etc/alternatives/pylupdate5`; `support-extract001-failed` preserves its partial outputs. The narrowly enumerated private replacements repair that packaging assumption. `support-extract002-missing-linguist` preserves the snapshot before discovering the separate translation-tool runtime. The subsequent `support` prefix was used by a failed QGIS configure: the package named `qca-qt5-plugins` supplies optional providers, while the required OpenSSL provider resides in `qca-qt5`. The new `support-02` retains that exact additional package and leaves the earlier prefix untouched. A later QGIS configure exposed nested GUI Multimedia requirements; support-03 adds multimedia/tools packages and preserves a full-component preflight failure on missing GL linker metadata. Support-04 retains GL dispatch/runtime/development libraries, passes Qt configuration, and preserves the next C++ probe failure on separately packaged Mesa headers. Support-05 adds exact Mesa GL/EGL/KHR headers and passes configuration of 25 Qt components, real C++ compilation and linkage using Multimedia/MultimediaWidgets/QuickWidgets/UiTools, and an ldd check with no unresolved libraries. The source, configure, build and loaded-library logs are under `build-worktrees/qgis-candidate/support-05-qt-probe`; these checks do not execute QGIS or establish product acceptance.

The subsequent actual QGIS configure failed FastCGI discovery. Complete symlink-target inspection established that `FastCGI-devel` supplied linker symlinks while `FastCGI` supplied the launcher; the actual libraries require `libfcgi0`. Support-06 retains that runtime, the freexl/minizip/rttopo development linker names required by SpatiaLite, and timezone data for pytz. Full Qt and FastCGI C++ configuration/compilation/linkage pass, actual `FCGX_Init()` returns zero, and both executable dependency checks have no unresolved libraries. The complete prefix has no dangling shared-library symlinks. QGIS requires explicit `FCGI_INCLUDE_DIR=<support>/usr/include/fastcgi` and `QWT_INCLUDE_DIR=<support>/usr/include/qt5/qwt6` because these publisher subdirectories are not inferred by the candidate's find modules. The support-06 probe evidence is retained beside its prefix.

Optional MDAL HDF5 and NetCDF dependencies were unavailable in the actual candidate configure; dependent formats are excluded from this profile.

A preflight with the owned spatial prefixes revealed two SQLite artifacts in the SpatiaLite process dependency graph: `libsqlite3.so.0` selected the task RTree build, while original owned PROJ had an absolute dependency on the prior `libsqlite3.so`. This observation is a required native-profile repair input; the root build records the isolated repair and final loaded origins. Version labels alone do not establish compatibility.

The private Qt xcb plugin resolves its Qt libraries from the retained prefix and still uses host X11/xcb, fontconfig/freetype, ICU, graphics drivers, libstdc++, libc and other base libraries. These are explicit host inputs; the retained Qt set is not a fully closed runtime. Supporting Qt/PyQt/QScintilla/SIP/NumPy/psycopg2/lxml/OWSLib imports were executed with private paths. Actual QGIS executable startup and provider tests remain separate build/runtime evidence.

## Build-hook audit and donor-test boundary

`WITH_VCPKG=OFF` prevents dependency bootstrap through vcpkg. `resources/CMakeLists.txt` invokes `yarn install --frozen-lockfile` and `yarn build` only for `WITH_SERVER_LANDINGPAGE_WEBAPP`; that UI is excluded. `cmake/DownloadO2.cmake` contains a historical download hook, but the selected OAuth2 CMake path uses retained `external/o2` sources directly. No `.gitmodules` is present in this candidate. SIP invokes local binding generation, not pip installation. Relevant native tests use retained testdata; broad WCS/public-server suites contain external-service assumptions and must not be described as local passes.

Candidate server targets include both `qgis_mapserv.fcgi` and the native `qgis_mapserver` development HTTP executable. The latter supports an explicit `127.0.0.1:PORT`; it avoids introducing a production web server. Native PostgreSQL tests honor `QGIS_PGTEST_DB` and otherwise use `service=qgis_test`; donor fixture scripts and role/topology requirements require a separate disposable database preflight. The readonly runtime fixture credentials remain distinct from donor test setup/edit credentials.

Fourteen acquisition guard tests exercise real malicious/invalid payload cases and committed input consistency. Package-wide tests and schema validation are reported by the integrator; none of these tests proves QGIS desktop/server acceptance.
