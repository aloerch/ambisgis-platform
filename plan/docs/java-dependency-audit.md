# FND-02 Java rendering dependency audit

This checkpoint inventories and retains the exact source declarations needed to
plan the Java build. **The transitive Maven/toolchain closure is incomplete and
no Java build or runtime test was run.** FND-02 remains In progress; FND-07,
FND-08, P1 and full-tuple acceptance remain open.

It starts from current `ambisgis/main` at
`12bd2c5c88ab8573add1b483f1d53b4024649b39`. GitHub reports that owner `aloerch`
merged [Jupyter PR #53](https://github.com/aloerch/ambisgis-platform/pull/53) at
that commit on 2026-09-19T20:58:39Z. That supersedes the previous handoff's open-PR
observation; it does not establish additional notebook/security acceptance.
The Jupyter input manifest was reverified: 5,510 files / 817,990,927 bytes, same
SHA256 `fc0b29f213d4613f5a0595bca7e8d179f0b2e8f40fc8ddff9e3d56c771d7d2b5`.
Database/Jupyter native and runtime tests were not repeated.

## Selected owned source

| Root | Tag | Exact commit | Tracked POMs |
|---|---|---|---:|
| GeoTools | 34.5 | `aac73e9b89821331e77f67f1dd0921e541a78cfc` | 196 |
| GeoWebCache | 1.28.5 | `59640420454b73f1e04e8409cc6ed43f4b24fed2` | 22 |
| GeoServer | 2.28.5 | `e0673323400321c0f3409fbae68b4871dc328d8a` | 301 |
| GeoNode | 5.1.0 | `a1db97e81dfc26c16bb4ee1a5d2b408877af66c9` | 0 |

All four tags are lightweight references equal to the listed commits. Existing
owned `origin` URLs were checked. The original clones/HEADs and full-history
bundles remain intact. Four new exact Git archives retain 894,259,200 bytes of
source and 77 files selected by license/notice/authorship basename heuristics.
This notice count is a discovery aid, not a file-level license conclusion.
Original texts remain inside the retained source archives.

The Java POMs agree on GeoTools 34.5 / GeoWebCache 1.28.5 / GeoServer 2.28.5.
Each requires Maven `[3.8,4.0)` and Java `[17,)`, with compiler release 17.
See [GeoServer's root POM](https://github.com/aloerch/ambisgis-geoserver/blob/e0673323400321c0f3409fbae68b4871dc328d8a/src/pom.xml),
[GeoWebCache's root POM](https://github.com/aloerch/ambisgis-geowebcache/blob/59640420454b73f1e04e8409cc6ed43f4b24fed2/geowebcache/pom.xml), and
[GeoTools' root POM](https://github.com/aloerch/ambisgis-geotools/blob/aac73e9b89821331e77f67f1dd0921e541a78cfc/pom.xml).
No `java`, `javac` or `mvn` executable was found on this session's PATH, and no
Java toolchain was installed or selected. Minimum constraints are not tool pins.

## Required behavior and reactor selection

The selected [GeoNode settings](https://github.com/aloerch/ambisgis-geonode/blob/a1db97e81dfc26c16bb4ee1a5d2b408877af66c9/geonode/settings.py#L1073)
enable GeoFence, GeoNode OAuth and both printing flags by default; WPS defaults
false. Its [server helper](https://github.com/aloerch/ambisgis-geonode/blob/a1db97e81dfc26c16bb4ee1a5d2b408877af66c9/geonode/geoserver/helpers.py#L1875)
constructs importer and GeoFence clients. These requirements must be accounted
for in the eventual profile even if a deliberate product decision replaces a
particular inherited integration later.

| Requirement | Owned GeoServer source/profile | Closure consequence |
|---|---|---|
| Import/upload | `importer`; `src/web/app/pom.xml:869` adds importer web/rest | Include tests and dependencies, not just the aggregator. |
| GeoNode login | `oauth2-geonode`; community security core/web/geonode; WAR profile at `src/web/app/pom.xml:1336` | Security behavior needs actual tests and review. |
| GeoFence policy | `geofence-server` reactor plus `geofence-server-postgres` WAR profile (`src/web/app/pom.xml:1061`) | External GeoFence 3.8.3 source/modules; PostgreSQL backend dependencies. H2 is a separate profile. |
| Printing | `printing`; `src/extension/printing/pom.xml:44` | Consumes `org.mapfish.print:print-lib:2.4-SNAPSHOT`. Cannot silently omit an enabled default. |
| Broader donor recipe | See retained GeoNode recipe research below | Recipe inclusion and product requirements are distinct; establish explicit selection. |

GeoNode's bare-install document discourages H2 for GeoFence, but its installation
example names GeoServer 2.24.2 while the selected compose file references
`geonode/geoserver:2.28.5-latest`. Neither floating image nor stale example is a
controlled replacement recipe. The exact source profiles need reconciliation.

GeoServer includes extension/community aggregators by default without their
child modules. A passing default reactor is therefore insufficient. Conversely,
GeoWebCache's default reactor includes cloud storage (S3/Azure/Swift/GCS), SQLite,
MBTiles and web modules. Explicit scope is needed before sizing/retaining the
closure. The separate community ACL `2.3-SNAPSHOT` is not GeoFence and is not
implicitly selected. Broad `release`/`allExtensions` profiles include printing
and additional features; they are not a safe shortcut around profile selection.

## Printing and external source evidence

Observed OSGeo snapshot metadata resolves MapFish to
`2.4-20260810.133736-29` (metadata lastUpdated `20260816092601`), listing jar and
POM only. The POM was retained with hash; its SCM tag is `main`, and it declares
GeoTools 34.4. This does **not** establish an exact corresponding source for the
snapshot jar. No snapshot jar was accepted or installed.

The [MapFish 2.4.1 source](https://github.com/mapfish/mapfish-print-v2/tree/da1f37cfc0d7a235cb2c0ec5677010495d9f664b)
was retained at `da1f37cfc0d7a235cb2c0ec5677010495d9f664b` as an evaluation
candidate. It also declares GeoTools 34.4 and a GPL-3.0-or-later license entry;
original source/license text is preserved. Adopting it requires explicit
source/dependency alignment and tests; **no MapFish override is made here**.
Its own source describes the v2 line as no longer actively developed. Independent
maintenance must cover any retained printing implementation.

[GeoFence 3.8.3 source](https://github.com/geoserver/geofence/tree/132a1d16901b7039f974c8c30d7e7df042d8af4c)
was retained at `132a1d16901b7039f974c8c30d7e7df042d8af4c`. GeoServer's inherited
extensions consume its API/model/implementation modules. Retaining the source
archive does not prove artifact correspondence or retain its transitive inputs.
These are Class B audit inputs, not new approved public source roots.

## GeoNode recipe and bootstrap provenance

Two exact public recipe sources are retained as Class B audit candidates:

| Recipe | Observed ref | Retained commit |
|---|---|---|
| `GeoNode/geonode-docker` | `gs2.28.5` | `0fef6e4ea794d2bb225e1e7d392b580ebf885a1c` |
| `GeoNode/geoserver-geonode-ext` | `2.28.5` | `b4e2fc4b7596cae051ee233417f39e3e33b5e6c5` |

All 34 + 234 archive files were checked against their Git tree blob identities;
no gitlinks, missing or unexpected files were found. The retained research
manifest has SHA256 `6e984a35ee43fd32a53e4f2dce855fb4709fa23b70295c9550d771b1c8962f15`.
This establishes recipe-source custody, not the identity of a published image.

The [extension build workflow](https://github.com/GeoNode/geoserver-geonode-ext/blob/b4e2fc4b7596cae051ee233417f39e3e33b5e6c5/.github/workflows/build.yaml#L32)
selects `sldService,printing,monitor,control-flow,wps,kmlppio,wps-download,xlsxppio,excel,oracle,querylayer,gdal,authkey,css,ysld,wmts-multi-dimensional,backup-restore,oauth2-geonode,oauth2-openid-connect,geofence-server,geofence-server-postgres,geofence-wps`.
It selects donor source by mutable workflow ref, uses `-DskipTests -U`, and uploads
to a version-named artifact directory without a source manifest. The recipe omits
`importer` despite GeoNode's importer client code. It enables WPS, as does
`data/wps.xml`, while GeoNode's application setting defaults false. These are
concrete profile-selection questions, not proof that every inherited profile is
required by AmbisGIS.

The [artifact script](https://github.com/GeoNode/geoserver-geonode-ext/blob/b4e2fc4b7596cae051ee233417f39e3e33b5e6c5/.github/workflows/artifacts.sh#L19)
overlays `libs/*` and `data/` into the WAR and separately archives `data/`; at this
commit `libs/` and `plugins/` contain placeholders only. The
[Docker recipe](https://github.com/GeoNode/geonode-docker/blob/0fef6e4ea794d2bb225e1e7d392b580ebf885a1c/docker/geoserver/Dockerfile#L25)
and data download script consume the version-path WAR/ZIP without content hashes.
Docker also replaces `WEB-INF/classes/applicationContext.xml`, configures
authentication and renders the PostgreSQL GeoFence datasource template. Audit
`data/security/config.xml`, OAuth filter/REST role-service configuration,
`data/geofence/`, `data/printing/` and Docker entrypoint/templates before adoption.
Do not copy inherited operational settings into a product deployment.

The Docker source includes a GPLv2 notice. No LICENSE/NOTICE/COPYING/COPYRIGHT
filename was found in the extension tree; exact license provenance for its
configuration/assets remains unresolved. Preserve originals and obtain the
required file/license review before adopting or redistributing them. These local
archives neither create a new public fork nor authorize a source-portfolio change.

## Inventory diagnostics and custody

The deterministic auditor enumerates all 519 tracked POMs plus 6 Maven-related
configuration files. Independent runs produced the same 6,369,140-byte JSON with
SHA256 `e94d6d50282bd3222a49839f3fd1aa583e9a205c94a710242f873ed2ef019f80`.
The actual command exits **1**, because GeoServer's
`src/maven/archetype/pom.xml` uses an undeclared `txsi` namespace prefix. Its raw
bytes/hash and XML diagnostic remain in the inventory. File enumeration is
complete; XML interpretation is incomplete. This archetype tooling POM has not
been proven part of the selected reactor and is not declared a runtime failure.
No silent patch, exclusion or successful-build claim was made.

The final audit manifest records **70 files / 902,064,509 bytes** under
`/home/revelberry/Projects/AmbisGIS/source-archives/java-audit`. It includes the
owned archives, selected Class B source archives, research responses/receipts and
raw declaration inventory. Hash verification and local-only recovery are
separate from dependency resolution. The source archives preserve their notices;
full-history bundles remain in the earlier custody inventory.

## Build and release hazards

All three Java roots bind Spotless `apply` to `validate` and default POM sorting
to `sort`. Even a validation invocation can modify source. Use disposable owned
copies and record the chosen check/skip transformation before invoking Maven.
The audit itself never executes Maven or donor code.

POMs include OSGeo release/snapshot repository definitions and donor deployment
namespaces. Future controlled builds need task-local settings/repositories,
retained fixed artifacts and parent/BOM/plugin/test/native input inventories;
`mvn deploy` is outside this task. Inherited workflows include
`pull_request_target`, write permissions, bot secrets and mutable Action refs.
GeoTools/GWC integration workflows clone donor repositories. None was enabled
or run; source-fork defaults, secrets and production systems are unchanged.

An XML inventory is not an effective dependency graph. Parent/profile/property
resolution, Maven super-POM/plugin defaults, dependency mediation, OS/JDK-activated
profiles, classifiers, test data, native libraries, fonts, CRS resources and
installer/server inputs remain unresolved until explicit acquisition and tests.
No source-to-binary, offline rebuild, independent repair, rendering, publication,
authorization, browser or recovery acceptance is inferred.

[Verification record](../verification/java-dependency-audit.json),
[input manifest](../../build-support/java/inputs.json),
[reproduction/recovery commands](../../build-support/java/README.md), and
[ADR 002](../adrs/002-java-audit-before-build.md) preserve the audit boundary.
