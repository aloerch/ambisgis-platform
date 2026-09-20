# FND-02 — Java compilation and selected compatibility evidence

The new runner performs actual isolated Java compilation and native tests from
the retained owned GeoTools 34.5 / GeoServer 2.28.5 sources and fixed Class B
MapFish 2.4.1 / GeoFence 3.8.3 candidates. This is an exploratory engineering
checkpoint, not source-closure, product-baseline, license, security or release
acceptance. FND-02 remains **In progress**. The original PR54/55 checkpoints and
all failed attempts remain separate and unchanged by this slice.

[Machine evidence](../verification/java-compatibility.json) records the exact
commands, inputs, output/log hashes and locations. [Reproduction and harness
boundaries](../../build-support/java/compatibility.md) describe the retained
recipe. The implementation starts at local commit
`9c9b3a6`, followed by verified-GDAL support at
`17b30498eb9a8e804743e7df632549f4979c73ef`, on `fnd-02/java-compatibility-probes`; the integration PR records the
final reviewed head.

## Executed component evidence

| Probe | Actual result | Scope remaining |
| --- | --- | --- |
| GeoTools referencing | 675 reported cases: 667 passed, 8 inherited skips, no failures/errors; all 12 selected reactor modules compiled/completed | Broader algorithms, online/stress/image/platform exclusions and source/host closure remain |
| XML broad target | 298 reported cases: 293 passed, 4 inherited skips, 1 error starting WireMock under Internet-socket denial | `SchemaCacheTest` needs an isolated loopback-capable environment |
| XML schema resolver | Both selected real suites passed all 12 tests; owned XML and prerequisites compiled/packaged under socket denial | The selected schema tests do not accept broad XML/cache behavior or schema file-level rights |
| MapFish candidate aligned to GeoTools 34.5 | Main/test sources compiled; 54 distinct tests passed, 6 inherited skips, 17 test identities errored on denied sockets | Real WMS/WMTS/HTTP printing fixtures and rendering acceptance remain |
| GeoFence/PostgreSQL | 62 tests passed: 8 model, 27 H2 persistence, 27 PostgreSQL/PostGIS; no failures/errors/skips | Service-layer GeoTools integration, actual authorization/policy propagation and combined GeoServer classpath remain |
| Importer | All 89 selected reactor modules compiled/packaged; 118 reported tests: 112 passed, 6 skipped, zero failures/errors; 169 built JARs hashed | Three Oracle and three SQLServer fixture tests remain skipped |
| SLF4J witness | Legacy API/binding mismatch reproduced as an expected failed JVM; aligned provider emitted an actual log and passed | Combined application dependency mediation/binding choice remains unaccepted |

Importer main/test compilation includes owned GeoServer platform, OWS, main,
WFS and WMS prerequisites. Their compilation is not native-test acceptance for
those modules. Importer's first successful run passed 108 with 10 skips. The final bounded
follow-up verified all 2,914 installed native files against the retained output
archive, staged only `gdal_translate`, `gdaladdo` and `gdalwarp`, and executed all
four previously skipped GDAL transformations. It passed 112 with only the six
Oracle/SQLServer fixture skips remaining. No native engine was rebuilt.

All Maven JVMs used the verified retained Temurin 17.0.20.1+1 and Maven 3.9.16
with fresh source copies, file mirrors and Maven repositories. The kernel wrapper
actually denied IPv4/IPv6 socket creation. It does not isolate host files/libraries
or Unix services. Referencing's eight skips include an explicitly Windows-only
URL test and inherited ignored tests; reports preserve the exact names. Target
mode deliberately does not execute prerequisite test suites. Online/stress
exclusions inherited from the source POMs remain exclusions, not passing tests.

MapFish's Surefire XML counts repeated setup/teardown errors separately: 84 XML
records include 24 error records, while Maven reports 77 distinct test cases with
17 error identities; both report 54 passing cases and 6 skips. These errors were
not renamed skips or waived. Full XML and MapFish runs first failed in the
prerequisite `gt-http` WireMock fixture. A direct isolated network-namespace probe
also failed with `EPERM`; narrowing subsequent test selection preserved those
broader failures as open acceptance.

## Concrete repairs and retained additional inputs

MapFish's first target compile exposed transitive EMF version ranges in the owned
`xmlcodegen` build plugin without retained discovery metadata. The guarded
[patch](../../build-support/java/compatibility-patches/xmlcodegen-emf.patch) pins
only `org.eclipse.emf.common` and `org.eclipse.emf.ecore` to **2.15.0**, exactly
as declared by the owned platform BOM. The manifest checks original/repaired
POM hashes before compilation; runtime dependencies retain their existing version.
The repaired reactor compiled MapFish against the exact owned GeoTools 34.5.
No donor branch or retained source archive was modified.

Actual test startup exposed inputs that successful `go-offline` had not retained:
Surefire's JUnit 4 provider 3.5.2 and common/provider metadata, protobuf-java 4.33.2
and its parent/BOM, Surefire's JUnit Platform provider 3.5.3, its parent-managed
Platform 1.12.1 inputs, and the actual project-selected launcher 1.11.4. Fixed
binary/source classifiers, POMs and publisher checksum sidecars were retained
through the custody proxy in a new custody tree. Original sources/notices remain
intact; the final inventory separately records source classifier and license
coverage. These additions do not silently resolve the original 64 source gaps.

The logging witness compiles a small real Java client against SLF4J API 2.0.17.
With `log4j-slf4j-impl`/API/core 2.24.3 it produces `NOPLoggerFactory` and exits 1.
With `log4j-slf4j2-impl`/API/core 2.25.3 it resolves `Log4jLoggerFactory`, finds no
legacy binder and emits the error-level witness. GeoFence's isolated native
classpath currently selects the older API and reports multiple legacy bindings;
the successful database tests do not approve that ambiguity. The witness's new
provider candidate must be tested in the combined application before adoption.

## PostgreSQL fixture and preserved failures

The GeoFence persistence target initially compiled and passed its model/H2 tests
but its PostgreSQL tests could not connect to the inherited localhost:5432 fixture
under socket denial. The new test-only JDK 17 `UnixSocketFactory` and the reviewed
owned database helper create a fresh private Unix-only fixture. All 72 runtime
artifact hashes match the prior database snapshot. The fixture verifies
PostgreSQL **15.19**, PostGIS **3.5.7**, its exact data directory and empty
`listen_addresses`; socket directory/permissions are 0700 and host HBA rejects
connections. No existing database service is contacted.

The first adapter attempt failed because GeoFence's inherited Java 11 test
release cannot compile `UnixDomainSocketAddress`. The next attempt explicitly
uses test release 17; main-source compilation is unchanged. Both the successful
initial fixture and the final guarded repeat passed all 62 tests and stopped
their clusters with readback. This is new GeoFence integration evidence using
existing owned binaries; historical PostgreSQL/PostGIS native suites and Jupyter
runtime suites were not rerun.

The adapter has no TCP fallback and does not emulate socket read timeouts; the
runner bounds the complete test process and cleans up on exceptions/timeouts.
It is experimental test transport, not a production JDBC implementation. The
cluster process itself is Unix-only by checked PostgreSQL configuration; Maven
and its Java descendants additionally have kernel Internet-socket denial.

The GDAL follow-up first failed before Maven because the frozen archive contains
hardlinks. Explicit safe in-archive hardlink byte verification repaired that
preflight; three harness tests cover hardlinks and installed/archive drift. Its
failed receipt remains intact. The passing follow-up had a 180-second process
bound and completed normally.

One earlier receipt flagged the generated POM unpacked inside
`target/original-test-sources/META-INF/maven/...` as a source change. Inspection
proved no original source changed. The runner now inventories such generated
POMs separately while rejecting changed original configuration or unexpected
new `.mvn` files. That failed receipt remains intact. An initial package-check
command used a root-relative output path that did not exist; it exited before
launching package tests. The documented checks were subsequently run from
`plan/` using the verified validation environment.

## Verification and next action

**155 Java tooling tests**, **175 package tests** and strict plan/four-schema
validation passed. They are separate from the native counts above. The harness
regressions require immutable output directories, original-source stability,
valid target-module reports and network-denial evidence; they also exercise
cluster cleanup after result-parsing failure and report shutdown failures.

The frozen compatibility snapshot verifies **33,580 files / 1,504,362,368
bytes**, manifest SHA256
`5271a16c0080bac41575807a10eafb311e999221c5d5572049c78f07899254ca`.
It includes all 22 task-owned attempts and the original failed receipts.
Custody is under `source-archives/java-compatibility`; every exploratory run is
under `build-worktrees/java-compatibility`. New acquisition receipts, originals,
failed logs/reports, actual native XML reports, built JAR hashes, exact tool recipes
and source manifests are retained. The preceding Java-resolution frozen snapshot
was reverified unchanged at 34,118 files / 1,682,220,066 bytes, SHA256
`2a9cc548d2d7709e39c6bef547e9befa7176a897fa6859a8bb7bae2ed14c7f07`.

Continue the remaining source/provenance dispositions and host/toolchain closure,
then complete the importer native-profile and loopback HTTP/WMS/WMTS fixtures and the combined
GeoServer/GeoFence logging graph. These persistence tests do not cover GeoFence's
GeoTools-dependent service modules, OAuth, WPS, publication, catalog authority,
managed branch editing, full rendering or release acceptance. Owner review can
accept this bounded implementation/evidence checkpoint without approving a
product baseline or licensing/security gates; no such approval is needed to
continue the listed engineering work. No PR merge or external publication was
performed by this delegated slice.

## Combined-branch review verification

The combined source/compatibility branch passed **212 Java tooling tests**,
**175 package tests** and **four schema/example checks**. Final GDAL guards also
reject directory symlinks, extra installed files, relative-path ambiguity and
changes during copying. Seven targeted guard tests passed. A fresh staging check
reverified all 2,914 real installed files and the three exact tool outputs; it
did not rerun Java or historical database suites. Importer-07 retains its original
runner hash and remains the native-test evidence. Initial path-normalization
regression failure is retained in `java-closure-gdal-guard-initial.json`.
