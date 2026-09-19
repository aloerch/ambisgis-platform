# FND-02 — Java toolchain and selected dependency resolution

This checkpoint retains the selected JDK/Maven distributions and sources and
resolves an explicit Java/GeoNode extension candidate. It does not accept a Java
build, full transitive source closure, native/runtime compatibility or a product
release. FND-02 remains **In progress**. [PR #55](https://github.com/aloerch/ambisgis-platform/pull/55) is open and unmerged, stacked on the audit branch.
The preceding audit remains reviewable
in [PR #54](https://github.com/aloerch/ambisgis-platform/pull/54).

The authoritative numeric results, exact command receipts and retained artifact
hashes are in [machine evidence](../verification/java-resolution.json). Read
[ADR 003](../adrs/003-java-resolution-candidate.md) for the candidate selection,
[commands](../../build-support/java/README.md) for reproduction, and
[the handoff](java-resolution-handoff.md) for the next action.

## Toolchain custody

Eclipse Temurin JDK **17.0.20.1+1** and Apache Maven **3.9.16** are retained as
44 files / 316,260,577 bytes. The toolchain manifest SHA256 is
`48b0521866a69a7570f140acc45db2f40bdcb77dfc9a6bc8936d911bd4b8e43c`.
All four publisher binary/source archive checksums matched. Installed tree
verification checks 342 files, 208 symlinks and 103 directories against those
archives before Maven execution. Version commands succeeded. The tools remain
local to this task. Original archives preserve all notices; a separate inventory
accounts for 324 notice/legal entries.

Signatures are retained but trusted-key verification was not performed. The boot
JDK, native compiler/build dependencies, publisher image layers and host shared
library source closure remain incomplete. Publisher source/SBOM metadata is not
an independent source-to-binary rebuild. See [toolchain evidence](../../build-support/java/toolchain.md).

## Selected graph and custody boundaries

The disposable reactor combines the exact owned GeoTools 34.5, GeoWebCache
1.28.5 and GeoServer 2.28.5 archives with retained Class B MapFish 2.4.1 and
GeoFence 3.8.3 evaluation sources. It selects the GeoServer web application and
GeoFence PostgreSQL test module, with importer, GeoNode OAuth, both GeoFence
server profiles, printing and PostGIS enabled. Distinct GeoTools property
spelling in MapFish and GeoFence requires both overrides to 34.5. No retained
source POM is patched. Fixed MapFish source replaces the unresolved snapshot
only for this experiment; adoption still requires compilation and affected tests.

The effective model contains 157 projects, 2,177 direct dependency declarations
and 2,574 build-plugin declarations. All 502 direct `org.geotools` declarations
use 34.5. These declarations are not a full transitive lock. WPS remains outside
this bounded graph, consistent with GeoNode's application default; the donor
recipe discrepancy and other capability/profile choices remain open.

Each invocation uses a fresh Maven repository, reviewed source copies, empty
global settings, task-local user settings and a sanitized environment. A loopback
mirror permits only Maven Central and the OSGeo release repository. It retains
successful bytes, original/final URL, SHA256 and size before serving them, and
freezes the first selected origin. Moving snapshot/version aliases and donor
core binaries are refused. Early invocations checked POM hashes; later invocations check all POM/`.mvn`
configuration hashes before and after execution and prevent ancestor `.mvn`
inheritance. This is not full source-tree hashing. Inherited workflow/deploy/download scripts and
lifecycle goals were not run. Model construction does load reviewed Maven build
extensions, including inherited `wagon-webdav`.

Nineteen exact schema archives required a narrowly scoped source-resource rule.
Their 177 required resources and source/destination mappings match owned
packaging recipes. Actual ZIP members passed safe-path, exact-Maven-identity,
XML/XSD and executable/native/script/nested-archive checks; the two recipe-declared
GML ReadMe text files remain intact. Member hashes and annotations are retained.
All 19 POMs lack license declarations. The [first comparison](../verification/java-schema-recipes.json)
and [additional comparison](../verification/java-additional-schema-recipes.json)
record that source evidence; file-level rights remain open.

XML 1.0 was initially quarantined for a documentation stylesheet instruction.
Independent inspection found XSD data and no DTD/entities/imports/includes.
A GAV/member/hash/exact-instruction exception now retains that original data;
its stylesheet is never requested or executed. All 18 prior validation manifests
are unchanged, and the original rejection/quarantine remains retained. ADR 003
records the exact hashes and instruction. This is not browser/XSLT/runtime
acceptance and does not activate the recipes' live Ant downloads.

## Resolution result

The fourth dependency pass exited **0**: all **157 selected reactor modules**
completed the pinned `go-offline` goal, with no failures or skipped modules.
The actual duration was 265.948 seconds. POM/`.mvn` configuration remained
unchanged. This includes GeoNode OAuth, importer, printing, GeoFence PostgreSQL
inputs and the GeoServer web application; it proves input resolution only.

Both final network-denied replays exited **0**. Each copied the same **9,142**
verified selected files into an independent file mirror and used a fresh local
Maven repository. All 157 dependency modules succeeded; the normalized effective
model matches the original. Both actual kernel probes denied IPv4/IPv6 socket
creation with `EPERM`. Maven POM/`.mvn` configuration remained unchanged. Host
files/tools and Unix-domain services are not isolated by this wrapper.

The frozen snapshot contains **34,118 files / 1,682,220,066 bytes**. Its manifest
SHA256 is `2a9cc548d2d7709e39c6bef547e9befa7176a897fa6859a8bb7bae2ed14c7f07`.
It includes 10,802 verified Maven records / 10,792 distinct blobs, toolchain
custody, original failed observations, schemas, notices and replay evidence.
The final inventory has 1,746 JAR input records, 1,660 retained source-classifier
records and **64 missing source classifiers** (actual inventory exit **2**).
Notice inspection covered 3,406 archive records and retained 3,463 notice-member
entries; these are not counts of unique licenses. [Exact gaps](../verification/java-resolution-source-gaps.json)
and [final triage](../verification/java-resolution-source-gap-triage.json) identify
16 missing-source GAVs directly declared at 33 sites, including one provided
Oracle driver. Sources/rights remain required even where a classifier is absent.

## Source coverage and preserved failures

Exact base-GAV source classifiers and POMs are acquired from each binary's
recorded origin. Missing classifiers remain explicit gaps; source classifiers
may omit test/native sources and do not establish binary correspondence. Notices
are retained as original bytes. License declarations and XML annotations are
inventory evidence, not redistribution approval.

The first dependency pass failed on an overly broad moving-version check in our
proxy that incorrectly rejected the fixed `org.apache.maven.release` group.
That check was narrowed to the version directory. The second pass completed 71
resolution modules, failed `gt-xml` on the nine schema archives, and skipped 85
projects. Both original logs and actual exit 1 receipts are retained. The third pass
completed 112 modules, failed the app-schema resolver on ten additional
transitive schema archives, and skipped 44 projects. The first
source pass verified 9,241 records and inspected 2,927 archive records for notices while
reporting 54 missing source classifiers. Later results supersede these counts
without deleting the failed observations. [First-pass source-gap triage](../verification/java-resolution-source-gap-triage-initial.json)
finds nine missing-source GAVs directly declared at 24 sites in the effective
model; absence of direct overlap does not make the remaining gaps unused.
An attempted schema-custody merge
precheck used the wrong verifier result key and failed before copying any file;
the next Maven pass acquired validated schema bytes through its normal proxy.

The initial model replay passed with 157 projects and an unchanged normalized
model under kernel IPv4/IPv6 socket denial. Its receipt predates the additional
Maven ancestor-configuration guard; actual process arguments already identified
the intended source root. The first expanded model/dependency replay attempts then exited 1 during
file-mirror preparation because `org/glassfish/javax.json` is a legitimate
Maven group directory and the reader mistakenly treated it as a record file.
Maven never started in those attempts. The traversal correction preserves strict
regular-file/symlink checks, and fresh replay results are separately recorded in
the machine evidence.

The first executed network-denied dependency replay failed on the explicitly
declared SLF4J API 2.0.17 JAR, while online acquisition had selected competing
1.7.36. The four relevant POMs are byte-identical between runs. Retained plugin
source reconstructs dependencies in unordered sets, supporting a mediation-order
explanation as an **inference**, not a version-range or metadata-change finding.
The exact 2.0.17 JAR, source classifier and matching publisher sidecars were then
retained; fresh replay succeeded. [Detailed diagnosis](../verification/java-resolution-slf4j-mediation.json)
records source/log lines and hashes. This goal’s success is not a dependency
conflict lock: reconcile SLF4J 1.x bindings/API 2.x and test the actual build/runtime
path before acceptance. Both the failed replay and repair receipts are retained.

Toolchain acquisition also retains its original Adoptium API HTTP 403, cross-
filesystem hardlink failure and repeated-directory extraction rejection, followed
by the actual corrected successful operations. Prior audit malformed-XML and
host-Python schema-validation observations remain historical evidence.

## Verification

All **140 Java custody/resolver tool tests** and **175 package tests** passed,
with no failures/errors/skips. Strict plan validation and all four schema/example
checks passed in the existing validation venv. These are tooling/package checks,
not native Java or GIS product tests. Actual output and the independent review
record are retained under `plan/verification/java-resolution-*`. Earlier
98-test, 130-test and 135-test tooling logs and earlier package checks remain separately
retained as historical checkpoints.

## Remaining acceptance

Complete missing sources and file-level license review; review toolchain trust
and bootstrap/native inputs; decide/test the fixed MapFish and GeoFence alignment,
WPS/other extension selection and GeoNode bootstrap assets. Then execute owned
compilation, retained-input rebuild/repair and relevant native/runtime tests,
including rendering, importer, OAuth, GeoFence PostgreSQL and printing. Database
and Jupyter results remain historical and were not repeated here. A successful
resolution goal or model replay cannot satisfy these acceptance requirements.

Security, licenses/brand, release signing and deployment review gates remain open.
No source-fork default, inherited workflow, secret, deployment or release changed.
