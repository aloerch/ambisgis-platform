# FND-08 initial owned product builds

The PostgreSQL/PostGIS, catalog, rendering/cache and UI components have actual
owned-source builds and retained inputs. Separate-context review has checked the
native, Java, QGIS and host-input evidence. Fresh catalog/UI pairs now select the reviewed client lint successor and pass
independent review. Final aggregate review and acceptance remain open.
This is the initial build foundation; no installer or completed GIS is claimed.

## Original acceptance and evidence

| Unchanged FND-08 criterion | Current evidence and remaining work |
| --- | --- |
| Initial vertical-slice components build without resolving upstream branch tips or fetching unrecorded packages. | Exact owned commits, original Git blob/mode inventories, retained dependency manifests, fresh output/cache directories and command-bound network denial are recorded in the component receipts below. The client formatting successor merged through PR #1; four fresh catalog/UI builds explicitly select that merged commit and pass. |
| A simulated upstream API/branch change does not change selected inputs or outputs. | Each qualifying pair creates its synthetic donor fixture before build one, changes only that fixture after completion and builds again. A deliberately floating resolver changes, while exact owned selections stay fixed. Comparisons retain raw hashes and attribute only recorded path/date/build-ID/webpack references; changed code or unexplained membership/content fails. Fresh client pairs pass with the same explicit attribution boundaries. |
| The source inventory includes libraries, plugins, styles, fonts, CRS resources, toolchains and base image dependencies. | Complete component source/input manifests include native/spatial libraries and notices, Java dependencies and plugin resources, Python/npm inputs, QGIS fonts/styles/resources and selected host RPM/source closure. The additional browser-isolation tools have a separately reviewed custody supplement. No compiler bootstrap or recreated OS image is inferred. |

[Chapter 11 T-OWN-02](11-independent-product-and-source-ownership.md) tests whether
simulated donor movement causes different selections or outputs. The comparisons
retain every raw difference and diagnose recorded build-location/time variation;
this is causal donor-independence evidence, not a claim of byte-for-byte
reproducibility. Unexplained content differences remain failures.

## Component results

- [Native/catalog/UI receipts](../verification/fnd08-remaining-slices/README.md)
  preserve the original pairs. Native builds each pass 217 PostgreSQL tests, one
  contrib test, 413 PostGIS CUnit cases and 13 actual spatial SQL assertions.
  Their 2,153 outputs have 2,055 identical hashes and 98 attributed differences.
  Original catalog outputs are byte-identical. The original UI pair and its
  five inherited lint errors remain historical evidence, not a passing native
  runner. [Client PR #1](https://github.com/aloerch/ambisgis-mapstore-client/pull/1)
  merged the two formatting repairs at
  `c1f6ad9df52f08ac3bfd7211db9e3ee744b21407`. Whole-client lint and 510 actual
  sandboxed browser assertions pass at its reviewed source. [Fresh merged-client
  pairs](../verification/fnd08-client-successor/README.md) produce three identical
  catalog outputs and 1,038 UI assets with zero unexplained differences. The
  actual fresh-build native runner passes lint and all 510 browser assertions.
  Catalog custody includes
  209 wheels and 199 sdists. Ten no-sdist packages retain inspectable embedded
  Python source and identity leads; complete standalone build inputs and source
  bootstrap for those packages remain unproven, as recorded in the linked
  catalog evidence.
- [Java evidence](../verification/fnd08-java-successor/evidence.json) records
  qualifying runs 004/005 from exact owned GeoTools, GeoServer and GeoWebCache.
  Each passes 359 native tests and explicitly retains six named inherited skips.
  All 361 JAR/WAR files are accounted for: 160 raw-identical, 201 with only
  diagnosed generated-date/ZIP metadata differences, zero unexplained content.
  Four build/test-only dependency source gaps remain recorded and are absent
  from the resulting WAR; complete toolchain/dependency source bootstrap remains
  separate work.
- [QGIS evidence](fnd-08-qgis-successor.md) records actual qualifying builds
  003/004, final stage-002 and fresh native/runtime checks. All 8,105 installed
  entries are accounted for: 8,056 identical, 49 exact path/build-ID variants.
  The final build passes 66 C++ and 16 Python cases without skips, desktop
  vector/raster/PostGIS/save-reopen, six WMS requests across restart, the exact
  palette exclusions and source-bound font checks. The original nonqualifying
  pair is preserved. Physical-display and Windows acceptance remain open.
- [Selected host inputs](../verification/fnd08-host-inputs/README.md) retain 276
  signed binary RPMs and 175 exact source groups. All 244 selected system paths
  are covered; 24,889 payload files match. Final replay-008 uses the repaired
  path-containment helper and performs zero network calls. Original collection
  dates, eight unavailable-SRPM metadata diagnostics, complete OBS alternatives,
  generated-cache limits and source forms remain explicit. The separate reviewed
  browser-isolation supplement verifies 42 packages and 33 source groups for
  11 observed tool/library paths; 38 packages reuse existing custody and exactly
  four are additional. It does not alter the original 276-package lock.

## Custody, review and limits

Large original inputs and outputs remain in the controlled local artifact store
under `/home/revelberry/Projects/AmbisGIS/source-archives` and
`/home/revelberry/Projects/AmbisGIS/build-worktrees`. Committed manifests bind
actual paths, digests, source identities and reproduction recipes. These paths
are local custody locations, not public download URLs or a release repository.
No production container or floating donor image is substituted. The selected
host development profile is openSUSE Tumbleweed x86_64; installed host payload
correspondence does not establish a clean supported product installation.

Independent reviewers reproduced material fail-open comparison and redirected
path defects. Forward fixes, adversarial regressions and fresh retained replay
are preserved with the original failures. Changes to review helpers are bound
separately from older producer snapshots; old executions are never relabeled.
The aggregate review has freshly passed 146 helper tests. The final client
pair increment has separate review; final aggregate documentation/head binding
and protected PR integration remain pending.

Raw reproducibility is explicitly false where path, timestamp or build-ID
variation is recorded. Diagnostic comparison does not rewrite distributed bytes.
OWN-01 consolidation, full OWN-02 disconnected rebuild/repair, source-rebuilt
bootstrap tools, generated-cache reproduction, distribution/security/license
qualification, installers, supported platform journeys and human evaluations
remain governed by the [complete requirements matrix](delivery-requirements-matrix.md).
