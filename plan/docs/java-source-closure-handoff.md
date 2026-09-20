# FND-02 Java source and compatibility — continuation handoff

Repository: `aloerch/ambisgis-platform`, database ID `1376927351`, node
`R_kgDOUhI-dw`; authenticated owner `aloerch` (ID `15285626`). Engineering
worktree: `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-closure`.
Branch: `fnd-02/java-source-compatibility`, based on corrected PR #55 head
`9e1b2e1bca26d00b200a39f58a4a0890d43fca98`. FND-02 remains **In progress**.
No PR was merged by this session. The published engineering PR and its exact
final tested head are recorded in its review summary and the session handoff;
verify the live head before any owner-approved merge.

## OWNER ACTIONS

| PR | Exact tested head | Order and bounded decision |
|---|---|---|
| [#54](https://github.com/aloerch/ambisgis-platform/pull/54) | `b15a785f350d347c0c2c4ff07ac6e5681c1d9746` | First Java checkpoint: review audit and normal integration of owner-merged main, then separately authorize merge to `ambisgis/main`. Accepts audit evidence, not Java compilation, source closure or product baseline. |
| [#55](https://github.com/aloerch/ambisgis-platform/pull/55) | `9e1b2e1bca26d00b200a39f58a4a0890d43fca98` | After #54 merges, verify actual main, integrate normally, retarget to main and recheck remaining diff/tests/current head. Accepts retained toolchain/dependency resolution, not runtime or source/legal acceptance. Never merge into an obsolete audit branch. |
| [#56](https://github.com/aloerch/ambisgis-platform/pull/56) | `28c9d79757b98bdedd44b5d7486835f9e4b71e63` | Independent governance review/merge to main. Accepts narrow Project visibility correction and preservation regression, not Java/product progress. |
| Engineering branch above | Exact final tested head in published PR summary | Review new source recovery/compile/native evidence as a separate checkpoint. Merge only after #55 is owner-merged, actual base is verified/retargeted and current diff/tests are reviewed. No acceptance of unresolved source, license/security, full tuple or release gates. |

At reconciliation #54 and #55 both read `stack: null`, `stackEntry: null`:
these are ordinary dependent branch PRs, not a GitHub-managed stack. The original
#54 conflict was limited to GOV-02 paragraphs in both STATUS files; the normal
merge preserved database/Jupyter evidence and owner-merged governance corrections.
No force-push, reset or history rewrite occurred. #54's integration passed 28
Java tooling /175 package tests; #55's passed 140/175. Both passed strict plan
validation and four schemas. Their bodies carry their exact current tested heads,
bases and mergeability; acceptance/retargeting decisions stay separate.

**No owner decision is currently required to continue engineering.** The pending
PR decisions gate merging only. No repeat GOV-02 setup or owner UI action is
pending. Security, license/brand, migration, signing and deployment approvals
remain future task-specific gates; this handoff does not request those approvals.

[PR review queue](https://github.com/users/aloerch/projects/2/views/7) was fully
read back with saved filter `is:pr is:open`, without parent-task Delivery/Review
gate restriction. Existing #54/#55 are separate unarchived PR items; neither
inherits Task ID or progress fields. Project count is **66 planned tasks +2 PR
items =68 items**, not 68 tasks. Existing views were preserved. Supported columns
include Repository/Evidence; parent issue links use Evidence because the actual
schema offers no Linked issues column. GOV-02 Delivery was reconciled to Merged
from the actual owner merge of #52, retaining its other fields. FND-02 fields
remain unchanged. PR #56 and the engineering PR were not added: this session's
Project authorization specifically names #54/#55. The separate #56 retains all
tracking code/docs/receipts; it is not folded into this Java branch. The live
importer was not rerun, and its new local preservation regression passed.

## ENGINEERING STATUS

This slice adds actual controlled source compilation/native tests to the earlier
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

Real results include GeoTools referencing **667 passed/8 skips**, XML schema
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

**212 Java tooling tests, 175 package tests and all four strict schema/example
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

Next ready FND-02 action: supply a controlled loopback-capable fixture environment
for XML/MapFish HTTP tests, while independently resolving the exact 16 remaining
source dispositions and testing the combined GeoServer/GeoFence logging and OAuth
paths. Recovered sources still need controlled rebuild/source-binary evidence;
19 schema archives need owned repackaging/file-level rights. Canonical source
baselines, full host/native/toolchain closure, full Java tuple, security/licenses,
FND-07/FND-08, P1/P6 and release acceptance remain open. No inherited workflow,
source-fork default, secret, deployment or release changed. All task-owned build
and database processes were stopped before publication.

Final review hardened GDAL staging against changed bytes during copy, directory
symlinks, unrecorded installed files and relative-path ambiguity. Seven targeted
guards passed, followed by the full 212-test suite. A fresh actual staging check
verified all 2,914 retained files and the same three tool hashes. It ran no Java
tests; importer-07 remains the native evidence. The initial normalization
regression failure and its correction are preserved separately.
