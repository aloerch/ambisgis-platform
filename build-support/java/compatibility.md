# Exploratory compilation and compatibility probes

This runner compiles exact retained owned source and executes real selected
native tests in disposable copies. Every result remains an **exploratory probe**:
full source/toolchain closure, source-to-binary correspondence, legal/security
review and capability acceptance are separate gates. See
[results and limitations](../../plan/docs/java-compatibility-evidence.md).

`compatibility.py` permits only fixed inspected targets and `test`/`package`,
with explicit aligned candidate properties from ADR 003. It verifies the local
Temurin 17/Maven 3.9.16 installation, retained source archives and Maven custody,
creates a fresh source tree, file mirror and empty local repository, then runs
under the existing seccomp IPv4/IPv6 socket-denial wrapper. No `install`, `deploy`,
network acquisition during a build, inherited workflow, donor checkout or source
fork mutation occurs. Early exploratory runs predate complete recipe snapshots;
current runs retain the exact Python/Java/patch recipes in `tooling/`.

Original source hashes are checked after execution. Any intentional source
patch or test fixture overlay is recorded before hashing. Maven's generated
`target/**/pom.xml` from unpacking test-source JARs is inventoried separately;
new Maven configuration outside generated targets or any new `.mvn` fails closed.
Result parsing cannot turn malformed/missing reports, absent selected-module
tests, ignored failures or a missing denial receipt into success. `--tests target`
compiles prerequisite main/test sources and packages their test JARs, but executes
only the selected package's tests. That is deliberately narrower than a full
reactor test run; inherited online/stress exclusions are retained. `compile-only`
is explicitly recorded as skipping test execution.

Run from the platform worktree with a new output directory each time:

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
python3 build-support/java/compatibility.py \
  --audit-custody "$TASK_ROOT/source-archives/java-audit" \
  --custody "$TASK_ROOT/source-archives/java-compatibility/maven" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --tools "$TASK_ROOT/build-worktrees/java-resolution/toolchain" \
  --output "$TASK_ROOT/build-worktrees/java-compatibility/new-referencing-run" \
  --target referencing --stage test
```

For XML's two offline schema suites use `--target xml --stage package --tests
schema-resolver`. For MapFish or importer, use `--target mapfish` or `--target
importer`, `--stage package --tests target --repair xmlcodegen-emf`. The guarded
patch uses EMF 2.15.0 already declared by the owned platform BOM for the build
plugin's otherwise unmanaged transitive ranges. It records exact input/output
POM hashes and does not fetch moving metadata or adopt another source revision.

For GeoFence, use `--target geofence --stage package --tests target`, plus:

```sh
  --postgres-prefix "$TASK_ROOT/build-worktrees/postgis-slice/run-003/prefix" \
  --postgres-evidence "$TASK_ROOT/build-worktrees/postgis-slice/run-003-evidence-final.json"
```

The fixture rechecks all 72 retained runtime artifact hashes, uses the reviewed
`validate_database.Probe` helper and creates a new private cluster/role/database
with PostGIS 3.5.7. It verifies PostgreSQL 15.19 and `listen_addresses=''`; local
HBA trust is protected by an owner-only 0700 socket directory and host HBA rejects
connections. The injected test-only `UnixSocketFactory` uses JDK 17's Unix socket
channel without TCP fallback. Test compilation explicitly uses release 17;
GeoFence main-source release remains unchanged. The adapter does **not** emulate
socket read timeouts, so the runner's overall timeout is required. This fixture
is not a supported production JDBC transport, managed-geodatabase migration,
authorization boundary or browser/SSO proof. Exceptions and timeouts stop the
owned cluster; all failed fixtures and logs remain retained.

For importer raster transformations, add `--gdal-prefix` pointing to the verified
`run-003/prefix` and `--gdal-archive` pointing to `run-003-prefix.tar.gz` from the
same retained native build. The archive checksum must match committed database
evidence; every installed regular file/hardlink and symlink is checked before
only `gdal_translate`, `gdaladdo` and `gdalwarp` are staged on the task-local PATH.
Owned library/data paths are explicit and PROJ networking is off. The successful
run used `--timeout 180`; unavailable Oracle/SQLServer fixtures remain skips.

`logging_probe.py` separately compiles a small logging witness and runs the
exact legacy/provider candidate classpaths with Internet sockets denied. It
requires an actual Log4j logger factory, no legacy binder on the repaired path,
and emitted log output. Its passing case establishes only that isolated
classpath; it does not lock the combined GeoServer/GeoFence application graph.

Supplemental inputs exposed by actual lifecycle execution have their own
acquisition receipts under `source-archives/java-compatibility`. These retain
fixed binary/source classifiers, parent/BOM POMs and publisher sidecars with
origin URLs and computed hashes. Existing `java-resolution` custody remains
unchanged. Full source/notice inventory and a frozen checksum manifest accompany
this slice; the original 64 source gaps are handled by the separate source-closure
work, not silently cleared by compilation.

Verification:

```sh
python3 -m unittest discover -s build-support/java -p 'test_*.py' -v
cd plan
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```
