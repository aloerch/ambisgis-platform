# F02-06 Java codec and headless-renderer remediation

These are proposed, locally source-built components for the coordinated Java/GMT
candidate. They do not grant adoption or distribution. The current user prompt
explicitly authorizes codec replacement and a headless Temurin-17 renderer profile;
PR #66 did not authorize their adoption. The parent candidate and every original
archive, failed run and predecessor variant remain preserved.

The [content mappings](../verification/java-gmt-remediation/imaging-replacements.json)
replace original Maven resolution paths locally; neither output is an upstream
release or published in a donor namespace. The
[predecessor mapping](../verification/java-gmt-remediation/imaging-replacements-predecessor-1.json)
is retained. Full source/class/notice records reuse `source_closure.py` and are
indexed by [the evidence summary](../verification/java-gmt-remediation/imaging-evidence.json).

| Component | Exact proposed source-built identity | SHA-256 |
|---|---|---|
| Marlin | `ambisgis-marlin-0.9.4.8-headless-temurin17-2` | `14633f73fed7e30553927201309bcaf407a9f5462fce87692f196859f33d074a` |
| ImageIO | `ambisgis-jai-imageio-1.1-java-temurin17-1` | `51dc61ca6724ba307f7d8407aa276e2c56c11d6ad6093d62820abef0ab0880f2` |

## Marlin source/profile and remaining obligations

The retained release source is revision
`5b1cbb57c39082cc444807daec401dd033754af7`, archive
`60fc2008c33f01281ce75dbbfe04c1771ddb9544746ed32c3dbef551ee60270a`.
Original binary coverage remains **85/87**: the release source omits two
OpenGL classes, and the preceding deleted source demonstrably does not reproduce
those publisher classes. That rejected correspondence is unchanged.

Variant 2 compiles complete retained sources for its selected **83 classes**.
It does not compile the unused `TestArrayCacheInt.java` benchmark helper: its two
classes had no other production-class references; the sole source consumer is the
unselected JMH benchmark. Its TODO-only file header cannot establish the explicit
Classpath exception required by the accompanying license wording. Variant 1,
which inadvertently retained it, remains a rejected predecessor. The final 42
source files supplying deployed classes each retain an explicit original
GPL-2.0-only/Classpath header. No permission is inferred for the omitted helper.
Original sources, including that helper, stay in custody.

[Exact source patch](../../build-support/java/remediation-imaging/marlin-source.patch)
and [profile exclusions](../../build-support/java/remediation-imaging/marlin-profile-exclusions.json)
record the changes. The engine constructor enforces headless operation with
OpenGL disabled; the version identifies the owned variant. Dated modification
comments preserve original notices and exception statements. No rendering
algorithm, line join, antialiasing or JDK baseline is redesigned.

Required production JVM flags are:

```text
--patch-module java.desktop=/absolute/path/to/the-exact-selected-marlin.jar
-Djava.awt.headless=true
-Dsun.java2d.opengl=false
-Dsun.java2d.renderer=sun.java2d.marlin.DMarlinRenderingEngine
```

A classpath entry alone is insufficient. The probe verifies the active
`RenderingEngine`, exact class resource origin, implementation version and JAR
hash before drawing. Public exports to `sun.java2d.pipe` and
`sun.java2d.marlin` serve the witness; no reflective `--add-opens` is required.
It draws known transparent shapes with miter joins/antialiasing, then checks
128 tasks over eight threads for identical pixels. The unpatched JDK and an
OpenGL-enabled launch fail negative controls rather than supplying a silent pass.

The retained upstream `JoinMiterRedundantLineSegmentsTest` also ran. **46/48
cases pass; two fail** for a degenerate `moveTo/close/lineTo` path under the two
stroke-normalization modes. The exact original publisher JAR fails the same two
cases with byte-identical diagnostic PNGs. This is an inherited rendering
limitation, not a passing native suite, and its assertions are unchanged. No
unexplained tolerance or substituted golden image is used. Full upstream long
renderer/benchmark suites were not run. Rights/security review and maintenance
binding remain ungranted.

## JAI ImageIO source recovery and codec profile

The authoritative historical repository retains the exact
[`jai-imageio-1_1-fcs` tag](https://github.com/jai-imageio/jai-imageio-jpeg2000/tree/c3c86a17fecc8a2d9b83bd0e6f686542c55d294b)
at `c3c86a17fecc8a2d9b83bd0e6f686542c55d294b`, although the separate core
repository's published tags begin later. Archive
`f7dac9b2350337503a7fb56636b927700247c6111f3a254ac223f510e1bffb68`
now accounts structurally for **559/559 original binary classes**. This improves
source recovery; it does not claim publisher-byte equivalence or broad rights
clearance.

The new Java-only variant compiles 312 Java files into **515 classes**, each
mapped to source. It preserves legacy `com.sun.media.imageio*`/`jj2000` packages.
[The explicit source exclusions](../../build-support/java/remediation-imaging/imageio-profile-exclusions.json)
remove native codecLib adapters/registrations and dormant `javax.media.jai`
operation bridges. The selected baseline uses `org.eclipse.imagen` and contains
no `javax.media.jai` implementation. ImageN, imageio-ext and their providers are
unchanged. No proprietary native codecLib archive member is extracted, executed
or selected. Original archive bytes are retained intact.

The complete baseline provider order/origins, source consumers, SPI entries,
class inventory and final provider choices are recorded. The only other WAR
references to omitted classes are literal `CLibPNGImageWriter` names used by
GeoServer's PNG-legend special case and GWC's provider preference. Neither is a
hard import/required native path. Native CLib providers were not registered in
the baseline. Java TIFF fallback paths remain and pass exact-pixel CCITT RLE,
T.4 and T.6 tests; JPEG and PNG use the retained JDK codecs. Imageio-ext TIFF
provider registration can deregister the legacy reader, so evidence records
actual automatic selection and separately instantiates the rebuilt legacy SPI
for its direct GeoTIFF test without altering registry order.

[The source patch](../../build-support/java/remediation-imaging/imageio-source.patch)
removes unused native imports/branches and three removed Java finalization calls
confined to compile-time-disabled timing paths. A real baseline JPEG2000 test
exposed packed INT RGB channels incorrectly labeled signed, clipping samples at
127. The narrow repair identifies unsigned packed bit fields. Original and
first replacement failures remain; the repaired variant preserves all tested
lossless RGB samples. TIFF/GeoTIFF tests preserve pixel scale, tiepoint and EPSG
4326 keys. JPEG tolerance is mean absolute channel error ≤3 and maximum ≤12 for
the known smooth input at quality 0.95; observed mean is approximately 0.551 and
maximum 3. PNG alpha and lossless TIFF/JPEG2000 pixels are exact.

**F02-JAVA-jai-imageio11 remains blocked for candidate adoption:** the recovered
147 JJ2000 source headers contain a separate conforming-product restriction.
They are not covered by the Sun BSD grant for the other Java sources. The
[publisher's separate JPEG2000 documentation](https://github.com/jai-imageio/jai-imageio-jpeg2000)
also identifies GPL incompatibility. The selected WAR combines this code with
GPL MapFish; technical success cannot establish compatible permission. Original
Sun notices, the nuclear disclaimer, JJ2000 notices and broader distribution
review remain explicit. No external legal terms were accepted or maintainer
contact made. The smallest safe next action is a bounded, source-owned codec
proposal with compatible JPEG2000 terms and the same real format/printing tests,
or authoritative compatible permission obtained through a separately authorized
process. Removing JPEG2000 support is not an accepted solution.

## Execution and resume

Build outputs and full receipts are under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/imaging`.
`marlin-04` is the selected benchmark-free build; `imageio-03` and independently
rebuilt `imageio-04` have identical selected bytes. `marlin-02`/`marlin-03`
prove deterministic predecessor compilation and remain preserved. All builds and
probes run with retained socket-denial controls, with verified IPv4/IPv6 denial
receipts. Complete retained toolchain-tree verification is recorded in the final
component build receipts. These probes launch no service/listener and use no
credentials. All invoked JVMs have exited.

The current final check is `final-war-probe-02` against aggregate-02 WAR
`e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044`.
Its codec and printing stages pass; its original native line-join stage exits 1
with the two inherited cases, so the wrapper reports
`partial-native-renderer-failure` and exits 1. The compact evidence summary
distinguishes component classpaths, predecessor WAR checks and this final check. A component substitution probe is
not acceptance of a deployed WAR. The final probe extracts the exact packaged
libraries into a fresh private directory, verifies the expected WAR hash before
and after, detects the selected renderer manifest and supplies its exact module
patch. It performs real MapFish PDF/PNG/TIFF printing, PDF text/page assertions
and decoded known raster content. It preserves a partial/nonzero result if the
inherited native renderer cases fail while still running independent printing.

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
TASK_CODE="$TASK_ROOT/ambisgis-platform-java-gmt"
# Fresh output directories are mandatory; previous evidence is never overwritten.
python3 "$TASK_CODE/build-support/java/remediation-imaging/build_marlin.py" \
  --workspace "$TASK_ROOT" --output "$TASK_ROOT/build-worktrees/java-gmt-remediation/imaging/marlin-05"
python3 "$TASK_CODE/build-support/java/remediation-imaging/build_imageio.py" \
  --workspace "$TASK_ROOT" --output "$TASK_ROOT/build-worktrees/java-gmt-remediation/imaging/imageio-05"
python3 "$TASK_CODE/build-support/java/remediation-imaging/probe_imageio.py" \
  --workspace "$TASK_ROOT" \
  --war "$TASK_ROOT/build-worktrees/java-gmt-remediation/aggregate-02/work/source/geoserver/src/web/app/target/geoserver.war" \
  --expected-war-sha256 e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044 \
  --output "$TASK_ROOT/build-worktrees/java-gmt-remediation/imaging/final-war-probe-03" --mapfish
```

From the IDE Flatpak environment, invoke those commands through
`flatpak-spawn --host /usr/bin/python3`; the Python wrappers install and verify
socket denial for their child JVMs. Package/schema/aggregate/service/authorization
and cross-product checks belong to the coordinated parent handoff; they are not
claimed by the focused imaging probes.
