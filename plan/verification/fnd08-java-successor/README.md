# FND-08: exact owned Java successor builds

Two fresh, Internet-socket-denied builds produced a coherent GeoServer/GeoWebCache
aggregate from GeoTools `3363c3d4ae8adfe3ed2024c27f92ec63855093be`, GeoServer
`fd2fe1dfcc78fa974bdb81673872879336312077` and GeoWebCache
`b4e9a30c8e2be00b9aa87fb17324efa8e489ac22`. Each export verifies the exact Git tree,
every blob and executable mode. Git attributes, default branches and donor API
responses cannot select the input. The retained prepatched GeoFence, MapFish and
reactor sources are verified against the recovered 39,622-file historical inventory.
Historical recipes, manifests and FND-02 acceptance evidence remain unchanged.

`build-support/java/owned_successor.py` is a separate producer. It does not call
the historical archive-extraction/patching producer. Each attempt has a fresh
source directory, Maven repository, user home and settings. The selected Maven
mirror contains only verified retained bytes and the six explicit controlled
variants. The build uses the retained JDK/Maven archives and checks the complete
extracted toolchain. An initial attempt failed closed because the older Maven
custody lacked Spring LDAP 2.3.2.RELEASE. Both successful attempts use the already
retained `java-http-auth/maven` custody; no dependency acquisition occurred.

Each successful attempt produced 361 JAR/WAR artifacts. All 100 embedded owned
core JARs match the fresh reactor outputs. A wider origin inventory identifies
all 367 WAR libraries as new source builds or retained selected dependencies.
Native GeoTools referencing tests executed from the new source: 359 passed,
6 inherited skips, zero failures/errors. Online and stress tests were excluded
explicitly. These tests do not establish service, authorization, rendering or
other product acceptance. The new WAR and a separately hash-bound runtime profile
are available for those affected tests.

`donor_drift.py` creates an isolated synthetic donor Git repository and API
response. Between successful builds its default branch, commit, tree and API
contract changed. A deliberately floating positive-control resolver observed
the incompatible sentinel. No real owned/donor ref changed. Both actual builds
selected identical source and Maven manifests and executed identical producer,
helper and toolchain bytes, including identical complete tooling snapshots.
The final pair is run-004/run-005, with the fixture present before the first build
started. Earlier run-002/run-003 builds remain useful build and comparison
evidence, but their fixture was prepared after the first completed build, so
they are explicitly insufficient for the final drift experiment. The comparator
now rejects that chronology and records the original receipt timestamps.

Raw output comparison is **160 of 361 artifacts byte-identical**. The remaining
201 differ through ZIP metadata and generated time values in manifests,
GeoServer/GeoTools properties and Maven `pom.properties` comments. Recursive
inspection includes all nested WAR JARs and records every changed line and raw
hash. There are zero unexplained content changes and no changed class bytes.
No artifact was rewritten or normalized. This establishes unchanged selected
inputs and attributes the observed output differences; it does not claim full
byte-for-byte reproducibility. Fixed `project.build.outputTimestamp` and
`SOURCE_DATE_EPOCH` do not control every inherited build plugin's time field.

The actual fresh Maven repositories consumed 1,007 JARs, all matched to retained
input hashes. Source inventory dispositions are 952 coordinate source archives,
23 supplemental source archives, 19 schema resources, 6 controlled source variants,
2 embedded-source candidates, 1 resource/metadata-only artifact and 4 explicit
legacy source gaps. The four gaps are classworlds 1.1-alpha-2, dom4j 1.1, opendap
2.1 and sisu-inject-plexus 2.1.1. Their exact bytes appear only in build/test
resolution, not in the resulting WAR. The inventory binds their class paths,
frozen dispositions and retained recovery leads. Source-candidate presence is
not source/binary correspondence. These source obligations remain open before
distribution/independent rebuild qualification.

The complete source inventory contains 39,622 files, including an 8,620-file
convenience subset for styles, fonts, CRS/schema and other resources. Toolchain
archives/source inputs are retained and verified; full JDK/Maven source bootstrap
is a later qualification obligation. Selected host executables and shared
libraries belong to the aggregate FND-08 host inventory. This Java evidence alone
does not mark FND-08 accepted or claim a release.

Reproduction uses a new output directory each time:

```sh
python3 build-support/java/owned_successor.py \
  --recovered /home/revelberry/Projects/AmbisGIS/build-worktrees/source-baseline-restore/run-002 \
  --geotools-repo /home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/remote-recovery-001/geotools.git \
  --custody /home/revelberry/Projects/AmbisGIS/source-archives/java-http-auth/maven \
  --toolchain-custody /home/revelberry/Projects/AmbisGIS/source-archives/java-resolution/toolchain \
  --tools /home/revelberry/Projects/AmbisGIS/build-worktrees/java-resolution/toolchain \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/fnd08-java/NEW-ATTEMPT
```

Run `donor_drift.py prepare`, the first build, `donor_drift.py drift`, the second
build, then `donor_drift.py compare` with the two output paths and fixture.
`successor_inventory.py` verifies the consumed Maven and WAR origins and retained
source candidates. Exact commands, hashes, failed and successful attempts,
network receipts, test counts and validation logs are bound by [evidence.json](evidence.json).
