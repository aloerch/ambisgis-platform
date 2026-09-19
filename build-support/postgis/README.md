# Experimental owned PostgreSQL/PostGIS build

This is the FND-02 database candidate slice on PR #51. It builds owned PostgreSQL
15.19 and PostGIS 3.5.7 from retained exact source archives, including raster,
MVT/Geobuf, GeoJSON, XML and topology. It does not approve production baselines,
licenses, the full component tuple, or FND-07/FND-08 acceptance. The complete
input/license inventory and excluded capabilities are in [dependency-audit.md](dependency-audit.md).

Run as the existing unprivileged user on the inspected Linux x86_64 host, with
Python3.12+, C/C++ compiler, CMake/Ninja, Make, Autotools, Perl, Bison/Flex and
standard shell tools. These host tools and libc/compiler runtime sources remain
unretained. No system installation, external package manager or inherited
workflow is invoked. Full source/command/library evidence is collected separately.
The prefix is intentionally local and includes both build tools and runtime
libraries; it is not a minimal supported deployment image.

## Verify and build

From the platform feature worktree, set paths to retained custody and a **new**
run directory. The initial observed workspace is `/home/revelberry/Projects/AmbisGIS`.
A run directory must not be shared by simultaneous builders; a process-held lock
prevents that. Each run has its own prefix, extracted sources, build tree and logs.

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
cd "$TASK_ROOT/ambisgis-platform-source"
TASK_INPUTS="$TASK_ROOT/source-archives/postgis-slice"
TASK_RUN="$TASK_ROOT/build-worktrees/postgis-slice/run-004"
python3 build-support/postgis/acquisition.py --custody "$TASK_INPUTS"
python3 build-support/postgis/build.py --custody "$TASK_INPUTS" --run "$TASK_RUN" --jobs 8 \
  --components zlib sqlite libxml2 cunit googletest json-c jpeg libpng tiff geos curl proj \
  protobuf protobuf-c gdal postgresql postgis-upgrade
```

`--components` is an explicit resume selection, not a dependency resolver.
The order above supplies prerequisites. A selected component is reconfigured,
built and tested; existing artifacts are not mistaken for a test run. Existing
source extraction requires the same retained archive hash. Use a new run for a
clean rebuild. Recipes never fetch; only acquisition's explicit `--fetch` may
restore missing inputs from recorded URLs/owned clones and must match the pins.

PostgreSQL enables retained zlib/libxml2 and builds/tests its owned fuzzystrmatch contrib module for inherited TIGER extension installation. Readline, SSL, ICU, LLVM and TAP are
not enabled for this private UNIX-socket experiment; production TLS/authentication
and the full PostgreSQL optional/contrib/TAP test matrix remain separate work.
PROJ uses retained HTTP-only curl for the native API variant expected by its unchanged CLI tests; PROJ networking remains OFF, projsync is disabled, and HTTPS/internet grid fetching is not supported by this experimental transport. PostGIS requires JSON/protobuf/CUnit and uses explicit installed `pg_config`,
GEOS/GDAL config tools and owned prefix libraries. SFCGAL, address standardizer
and GUI are excluded. Exact flags and native test limitations are in the driver
and audit; no omitted feature is advertised as implemented product capability.

## Real earlier-version upgrade and spatial checks

The first command must run **before** target PostGIS is installed. It asserts
3.5.6 runtime/SQL versions, executes 13 spatial checks, retains geometry/raster/
topology data and stops its own cluster. It prints the actual report and writes
`upgrade-state.json` alongside it. Keep that observed path for the final phase.

```sh
python3 build-support/postgis/validate_database.py prepare-upgrade \
  --prefix "$TASK_RUN/prefix" --work-root "$TASK_RUN/databases" \
  --expected-geos 3.13.1 --expected-proj 9.6.2 --expected-gdal 3.10.3 \
  --expected-json-c 0.18 --expected-protobuf-c 1.5.2
python3 build-support/postgis/build.py --custody "$TASK_INPUTS" --run "$TASK_RUN" --jobs 8 --components postgis
# Supply the exact upgrade-state.json path printed/retained by prepare-upgrade:
python3 build-support/postgis/validate_database.py finish-upgrade \
  --prefix "$TASK_RUN/prefix" --work-root "$TASK_RUN/databases" \
  --upgrade-state "$TASK_UPGRADE_STATE" \
  --expected-geos 3.13.1 --expected-proj 9.6.2 --expected-gdal 3.10.3 \
  --expected-json-c 0.18 --expected-protobuf-c 1.5.2
```

The final phase requires changed extension libraries and an unchanged PostgreSQL
binary, performs three actual `ALTER EXTENSION ... UPDATE TO '3.5.7'` operations,
compares retained geometry/raster/topology witnesses, and executes 13 checks each
on upgraded and fresh databases. Checks include an observed GiST plan/results,
GEOS operations, EPSG4326→3857 using prefix `proj.db`, MVT, GeoJSON, GTiff raster
round-trip and topology. PROJ's writable resources are private and networking
disabled. Native raster/script version strings include the archive build revision
`0`; exact owned commit identity is recorded independently in archive manifests
and binary hashes. A fresh-target no-op update is never counted as this upgrade.

## Source and extension regressions

```sh
python3 build-support/postgis/regress_database.py \
  --prefix "$TASK_RUN/prefix" --work-root "$TASK_RUN/regressions" \
  --build-dir "$TASK_RUN/build/postgis" \
  --expected-geos 3.13.1 --expected-proj 9.6.2 --expected-gdal 3.10.3 \
  --expected-json-c 0.18 --expected-protobuf-c 1.5.2
```

This invokes actual `make check-regress` and `make installcheck-base` against a
fresh private cluster, with separate artifacts for each native Perl invocation.
Normal and same-target source self-upgrade suites remain distinguished from the
earlier-version upgrade above. Missing summaries and unexpected SQL skips fail
the wrapper. Failed suites remain recorded; both targets are attempted. CUnit
runs as part of the build and cannot be silently omitted. Documentation/lint and
unselected extensions are not included in these database targets.

All clusters use private short socket directories and disabled TCP listeners.
The scripts stop only their own clusters and retain database/log directories for
inspection. Do not install into a prefix while one of its validation clusters is
running. The host environment's database connection settings are not inherited.

## Clean rebuild with network denied

Choose a fresh run, omit the earlier-version fixture if only rebuilding the
target, and wrap the entire build. The evidence filename must be new.

```sh
python3 build-support/postgis/offline_exec.py --evidence "$TASK_ROOT/build-worktrees/postgis-slice/offline-run003.json" -- \
  python3 build-support/postgis/build.py --custody "$TASK_INPUTS" --run "$TASK_RUN" --jobs 8 \
  --components zlib sqlite libxml2 cunit googletest json-c jpeg libpng tiff geos curl proj \
  protobuf protobuf-c gdal postgresql postgis
```

The Linux x86_64 wrapper applies inherited seccomp/no-new-privileges rules, probes
IPv4/IPv6 denial and UNIX socket success, closes inherited nonstandard descriptors
and records the command's actual exit. Local UNIX sockets remain usable by
PostgreSQL. This is network denial for trusted build processes, not a hostile-code
sandbox: local services and host filesystem/toolchain remain accessible. It does
not demonstrate all-component custody, byte-identical outputs, synthetic repair,
release signing, deployment, or whole-product T-OWN-04 acceptance.

After rebuild, wrap the `validate_database.py smoke` and `regress_database.py`
commands likewise with distinct evidence paths to check the rebuilt runtime.
Smoke explicitly records its lack of an earlier-version fixture; retain the
separate successful real upgrade evidence from the first run.

## Evidence and tooling checks

```sh
python3 build-support/postgis/collect_evidence.py --run "$TASK_RUN" \
  --inputs build-support/postgis/inputs.json --custody "$TASK_INPUTS" \
  --workspace "$TASK_ROOT" --output "$TASK_ROOT/build-worktrees/postgis-slice/run-004-evidence.json"
python3 -m unittest discover -s build-support/postgis -p 'test_*.py' -v
cd plan
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 -m unittest discover -s tests -v
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 tools/validate_package.py --require-schemas
```

The collector preserves historical failures, command/input/log hashes, tool and
library identities, and wrapper versus internal test counts/skips. It does not
infer task acceptance from a build stamp. Full logs, receipts, snapshots and
outputs stay outside Git; the PR records their hashes and summaries. The existing
validation venv is a host input, not a newly resolved package environment.
