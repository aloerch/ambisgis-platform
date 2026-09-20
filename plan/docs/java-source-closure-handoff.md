# FND-02 Java source and compatibility — continuation handoff

Repository: `aloerch/ambisgis-platform`, database ID `1376927351`, node
`R_kgDOUhI-dw`; authenticated owner `aloerch` (ID `15285626`).
Worktree: `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-closure`.
Branch: `fnd-02/java-source-compatibility`; target: `ambisgis/main`.
FND-02 remains **In progress**. This session prepares **PR #57 only** for owner
review; it does not merge a PR or start the next engineering slice.

## Current owner action and actual ancestry

The chosen review order is **#54 → #55 → #57 → #56**. Actual live merges:

- #54: owner `aloerch`, 2026-09-20T20:09:12Z, merge
  `8393fc46b9b979b05faa416f5998e0159ecd1e33`.
- #55: the same owner, 2026-09-20T20:50:29Z, reviewed head
  `8eeb408f296b7c6152fae2ef5edef65161f674ac`, merge/current main
  `bb3680802d7f7d5c500180ec12e66d32d81d0aa0`. Main's tree equals the exact
  reviewed #55 tree `c7353aa55c9cd874ec8b98ad38e70839f5e50a3b`.

Normal merge `dc250cd854ae87bfb80657148efe937a69c381dc` combines previous
#57 head `7d3063f89c20b5e028b0151a6648a79e4ef14a83` and actual main.
Only root/plan STATUS conflicted. Both were reconciled deliberately, preserving
native/database/Jupyter evidence and the newer governance/parser records.
Before scoped review repairs, the remaining Java implementation diff was byte
identical to #57's old diff against #55. The 96 changed paths also matched.
The inherited encoding-aware POM parser and its three regression tests equal
merged main. No reset, rebase, force-push or cited history rewrite occurred.

These were ordinary dependent branches. #57 was explicitly retargeted only
after #55's actual merge; no automatic managed-stack behavior was assumed.
Read [the selected review report](pr-57-review.md) for scoped repairs, current
checks, exact tested source identity, unresolved findings and acceptance limits.
The PR summary and final verification receipt identify the exact published head
and full tested Git tree. Independent engineering review is not human approval.

The owner decision is whether to accept this bounded source-recovery and
compatibility-evidence checkpoint for a separate GitHub merge. #56 remains open,
technically independent, and **not prepared in this run**; it follows #57 in the
chosen order. No acceptance of final source/license/security/product gates,
release, or the future HTTP/XML/printing/logging/OAuth slice is implied.

## Project readback

Complete archived/unarchived enumeration confirms **66 planned tasks + four PR
items =70 items**, all unarchived. Saved `is:pr is:open` matches #57 and #56;
merged #54/#55 remain retained items. Parent Evidence, task identities, seven
views, 24 fields and 15 repository links are preserved. FND-02 remains In progress;
GOV-02 remains Merged. Since the prior #55 receipt, only #55's coarse built-in
Status changed Todo → Done; this is distinct from product Delivery.

[Actual readback](../verification/pr57-review/project/README.md) records zero
remote mutations. No duplicate item, task issue, importer run, progress reset,
archive change or UI setup is needed. Historical 68-item observations remain in
the earlier receipts and commits; they are not the current membership.

Current preparation checks: **218 Java tooling tests, 175 package tests, all four
strict schemas and 12 selected native XML resolver tests passed without failures/
skips**. Both scoped review repairs are documented in the selected report. Other
native results below remain historical; full suites were not rerun.

## ENGINEERING STATUS

The retained engineering slice added actual controlled source compilation/native tests to the earlier
resolution-only checkpoint. [ADR 004](../adrs/004-java-source-and-compatibility-probes.md)
records the guarded EMF build-plugin repair, Unix-only PostgreSQL test fixture,
logging witness and source-recovery boundaries. Read the component evidence:

- [64-gap source supplement](java-source-provenance.md): exact GAVs, hashes, source revisions, structural mappings, observed use, original rights evidence and attempted remedies.
- [Compatibility builds/native results](java-compatibility-evidence.md) and [recipe](../../build-support/java/compatibility.md).
- [JavaCSV recovery](javacsv-source-recovery.md), [Huldra/Marlin probes](java-recovered-source-probes.md) and [profile/bootstrap decisions](java-profile-decisions.md).

The original 64 gaps now have **39 retained-source structural candidates,
4 embedded-source cases, 3 generated-input cases and 2 metadata-only packages**.
These 48 are accounted for structurally, not declared reproducibly source-built.
**12 unresolved +4 partial cases remain.** All source/binary correspondence and
final legal approval gates stay explicit. In particular:

- Unresolved: `classworlds:classworlds:1.1-alpha-2`, `dom4j:dom4j:1.1`, `geronimo-spec:geronimo-spec-jta:1.0.1B-rc4`, `org.netbeans.lib:cvsclient:20060125`, `org.sonatype.sisu:sisu-inject-plexus:2.1.1`, `plexus:plexus-utils:1.0.3`, `xmlpull:xmlpull:1.1.3.1`, `com.oracle:ojdbc14:10.2.0.3.0`, `javax.media:jai_imageio:1.1`, `net.sf.json-lib:json-lib:2.4.2-geoserver`, `opendap:opendap:2.1`, `com.google.code.typica:typica:1.3`. No unknown path is declared unused.
- Partial: Commons Codec 1.2 includes a class absent from its source tag; AspectJ Weaver 1.5.4 bundles five BEA classes; GroboUtils 5 bundles incompletely recovered third-party classes; Marlin 0.9.4.8 lacks exact OpenGL source. A preceding Marlin source compiled but differs substantively in disassembly and is rejected as exact correspondence.
- The Json-lib patch author's recovered POM says 2.4.1-geoserver, not selected 2.4.2-geoserver. The NetBeans source endpoint returned HTML, and a JAI ImageIO download was a Windows binary installer, never executed. Failed/mismatched candidates remain retained. Oracle source/rights access or a tested capability-preserving implementation change remains necessary; no driver/functionality was silently removed.

Historical native results include GeoTools referencing **667 passed/8 skips**, XML schema
resolver **12 passed**, GeoFence **62 passed** (8 model/27 H2/27 PostgreSQL),
Huldra **19 passed**, and JavaCSV **105 passed** with explicit historical CRLF.
JavaCSV's unchanged Linux-default suite produces the same **16 failures** against
both rebuilt source and original binary. JGridShift's four source files compile
and its public API equals the retained JAR; the retained core tree has no native
tests. These are distinct evidence levels, not interchangeable acceptance.

Broader XML reports **293 passed/4 skips/1 error**. MapFish source compilation
passes after the guarded EMF pin; **54 distinct cases passed/6 skipped/17 error
identities** remain (84 Surefire XML records include 24 repeated setup/teardown
error records). HTTP/WMS/WMTS fixtures cannot run with all Internet sockets denied;
the host refused user/network namespace creation. No failed test was waived or
renamed a skip. Source archives are unchanged; the patch/fixture affects fresh
source copies only. The SLF4J witness reproduces the legacy-binding failure and
passes with a matching SLF4J2 provider; the combined application graph still needs
explicit mediation and actual packaged-classpath tests.

Importer compiled/packaged all **89 selected reactor modules** and passed
**112 native tests with six skips and no failures/errors**. Four real GDAL raster
transformation tests passed after staging three exact tools from the verified
owned database/GDAL archive; 2,914 installed files matched retained bytes. The six
remaining skips are three Oracle and three SQL Server fixture cases. Earlier
missing test-provider inputs, ten-skip run and hardlink-preflight failure remain
retained. Prerequisite native suites excluded by target selection are not
claimed passed.
OAuth is retained in the selected profile but has no native authorization/runtime
acceptance here. WPS remains outside this bounded profile with documented owned
GeoNode-default rationale. Schema resolver success does not close offline
repackaging, external resource/rights or broad XML behavior. Bootstrap assets
have hash/provenance improvements, not permission to deploy inherited credentials.

Historical publication checks: **212 Java tooling tests, 175 package tests and all four strict schema/example
checks passed with no failures or skips.** Actual output is retained in
`plan/verification/java-closure-integration-*.txt`. The checks run from the
correct root/plan directories using the verified validation environment. They
are separate from GIS component tests. Historical PostgreSQL/PostGIS native and
Jupyter suites were not rerun. The new GeoFence tests use verified prior owned
database artifacts with a fresh, stopped private cluster.

## Retained evidence and next ready action

All custody is under `/home/revelberry/Projects/AmbisGIS/source-archives`:
`java-source-closure` (complete detailed supplement), `java-source-closure-parent`
(Huldra/Marlin/Apache recovery), `java-source-closure-research` (JavaCSV/Json-lib),
`java-compatibility` (actual lifecycle input additions), and `java-profile-evidence`
(bootstrap asset rights bytes). Each frozen snapshot has its own hashes; none
replaces the original `java-resolution` custody. Its **34,118 files /
1,682,220,066 bytes** were reverified unchanged against manifest SHA256
`2a9cc548d2d7709e39c6bef547e9befa7176a897fa6859a8bb7bae2ed14c7f07`.

Raw fresh source trees, repositories, logs, output artifacts, recipe snapshots,
network-denial reports and failures are under `build-worktrees/java-compatibility`.
Never reuse an existing run path. Run `--help` on the retained helpers and replay
an exact recorded command into a new directory. GitHub CLI's verified SHA256 is
`ea857a3f0f7d4276cf5848b236542c5048e2eaa7bdd1b6ddec238f8793e74bff`;
locate/verify it before reuse instead of assuming a `/tmp` path survives.

Future FND-02 engineering scope (not started or authorized by this review): supply a controlled loopback-capable fixture environment
for XML/MapFish HTTP tests, while independently resolving the exact 16 remaining
source dispositions and testing the combined GeoServer/GeoFence logging and OAuth
paths. Recovered sources still need controlled rebuild/source-binary evidence;
19 schema archives need owned repackaging/file-level rights. Canonical source
baselines, full host/native/toolchain closure, full Java tuple, security/licenses,
FND-07/FND-08, P1/P6 and release acceptance remain open. No inherited workflow,
source-fork default, secret, deployment or release changed. All task-owned build
and database processes were stopped before publication.

Historical publication review hardened GDAL staging against changed bytes during copy, directory
symlinks, unrecorded installed files and relative-path ambiguity. Seven targeted
guards passed, followed by the full 212-test suite. A fresh actual staging check
verified all 2,914 retained files and the same three tool hashes. It ran no Java
tests; importer-07 remains the native evidence. The initial normalization
regression failure and its correction are preserved separately.
