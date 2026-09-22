# F02-06 proposed Java/server NO-JPEG2000 profile

The current owner instruction explicitly supersedes the earlier prohibition on
removing JPEG2000. The selected bounded proposal removes its optional handling
from this Java/server profile. It does not remove ordinary JPEG or the imaging
library, or assert project-wide JPEG2000 removal. Candidate adoption and
license/distribution decisions remain separate owner gates.

| Consideration | Remove affected JPEG2000 handling — selected | Source-owned OpenJPEG integration — not selected |
|---|---|---|
| Workflow impact | JP2/raw J2K input and JPEG2000 output are unsupported; JPEG2000-backed PDF images/backgrounds/map tiles are refused. Preserve ordinary PDF, PNG/JPEG/TIFF/GeoTIFF, ImageN, imageio-ext, vector/mosaic/services/tiles. | Would preserve selected JPEG2000 workflows after independently proving both reader and writer integration. No required preserved workflow was identified that justifies this incremental stack. |
| Concrete inputs | Exclude all `jj2000/` and both `com/sun/media/imageio[impl]/plugins/jpeg2000/` source roots and their SPIs. Keep the other 132 JAI source files, existing ImageN/imageio-ext and headless renderer. Add narrow source-owned MapFish guards. | Add exact native OpenJPEG source/build, ABI/compiler locks, Java reader/writer wrapper, loading/disposal/error handling and native package membership. The current Java WAR has none of these native codecs. |
| Terms | All 132 selected Java source headers retain Sun BSD terms and the nuclear disclaimer. Historical JJ2000 sources/notices stay intact in custody; exclusion grants no new rights to them. | Reviewed OpenJPEG 2.5.4 BSD-2-Clause terms are positive evidence for that source; wrapper and build dependency terms require separate verification. A permissive root license is not an integrated rights conclusion. |
| Security and maintenance | Remove the disputed decoder/encoder attack surface; maintain the retained formats plus small explicit policy guards. Test content, MIME/extension mismatch, output aliases, indirect PDF use and failed-request cleanup. | AmbisGIS would own native codec triage, fuzz/regressions, allocation/concurrency/malformed-input tests, backports, Java wrapper disposal, ABI/compiler and platform support. No dependency on upstream maintenance resuming is acceptable. |
| Portability | No new native library or loader. Existing Linux/Temurin17 and headless limitations remain. | The authorized experiment could establish Linux/Temurin17 only; it would not establish Windows/macOS support. |
| Regression burden | Preserve existing non-JPEG2000 assertions; replace only candidate-specific JPEG2000-positive selection with refusal tests. Full exact-WAR service/mosaic/cache/frontend proofs remain necessary. | Requires JP2/raw codestream read/write, lossless/lossy precision, metadata/region/subsampling, reference decoding and native security/resource tests in addition to the same non-JPEG2000 regressions. |

The owner's prioritization of JPEG2000 as optional is the scope decision. It is
not an industry usage claim. Removal avoids substantial incremental maintenance
for the optional workflow while retaining the required workflows, subject to the
final exact-WAR runtime evidence.

## Dated OpenJPEG review

The [official repository](https://github.com/uclouvain/openjpeg) explicitly marks
itself unmaintained; the maintainer's [issue 1655](https://github.com/uclouvain/openjpeg/issues/1655)
was opened July 7, 2026. The latest reviewed release is
[2.5.4](https://github.com/uclouvain/openjpeg/releases/tag/v2.5.4), published
September 20, 2025, commit `6c4a29b00211eb0430fa0e5e890f1ce5c80f409f`.
The [security page](https://github.com/uclouvain/openjpeg/security) reported no
policy or published advisories; this does not establish absence of vulnerabilities.

Relevant open reports include [1652](https://github.com/uclouvain/openjpeg/issues/1652)
(core decoder, July 1, 2026), [1648](https://github.com/uclouvain/openjpeg/issues/1648)
(core encoder, June 29, 2026), and
[1643](https://github.com/uclouvain/openjpeg/issues/1643)
(tile geometry, June 4, 2026). These are reported defects requiring independent
triage, not reproduced vulnerability determinations in this batch. Release age
alone is not the reason for rejection. Occasional commits and a source fork do
not remove AmbisGIS's maintenance obligation. Exact HTTP bytes, timestamps,
tag object and hashes are in the
[primary-source review index](../verification/json-jpeg2000-remediation/imaging-openjpeg-review.json).

The [cross-profile inventory](../verification/json-jpeg2000-remediation/imaging-cross-profile-inventory.json)
records that the selected GDAL 3.10.3 build explicitly sets
`GDAL_USE_OPENJPEG=OFF` and its retained executed format listing has no JP2
reader. CMake discovered host OpenJPEG 2.5.4 but did not select it. QGIS uses this
source-owned GDAL prefix; selected QGIS support and notebook dependency/native
inventories identify no OpenJPEG/Pillow/rasterio input. No unrelated profile was
purged, and this is not a promise about future or user-installed notebook codecs.

## Source/build boundary and indirect consumers

The [new build recipe](../../build-support/java/remediation-nojpeg2000/build_imageio.py)
reads the retained original source archive
`f7dac9b2350337503a7fb56636b927700247c6111f3a254ac223f510e1bffb68`,
revision `c3c86a17fecc8a2d9b83bd0e6f686542c55d294b`.
Its output is `ambisgis-jai-imageio-1.1-nojpeg2000-temurin17-1.jar`, SHA-256
`a7084cfbb419bd158464638454939d25e1fef1a990ee00bf6145b28956218007`.
It contains 323 source-mapped classes from 132 Java files. Every preserved class
is byte-identical to the corresponding class in the parent's selected JAI
variant. Native codecLib and inactive `javax.media.jai` exclusions remain.
All 147 JJ2000 Java files and their dependent provider source roots are excluded;
no disputed implementation is copied or relocated. The complete per-file header,
source exclusion and archive-binary accounting is retained in
[the selected-source terms index](../verification/json-jpeg2000-remediation/imaging-selected-source-terms.json).

The exact parent WAR scan found no other JJ2000/OpenJPEG/Kakadu/GDAL codec.
GeoServer startup already unregisters the legacy Sun JPEG2000 SPIs. GeoTools
coverage and mosaic classes only name the optional Kakadu provider; these are not
hard imports. Selected ImageN/imageio-ext classes have no dependency on the
excluded JJ2000 implementation. TIFF compression tags 34712, 33003 and 33005 are
already unsupported by both retained legacy and imageio-ext TIFF readers; fresh
baseline and successor tests use real J2K strip bytes to preserve that distinction.
This exclusion does not cause their pre-existing unsupported status.

OpenPDF can embed JP2 without ImageIO and PDFBox can attempt dynamic JPEG2000
lookup. Therefore hiding the SPI alone would be insufficient. The
[source policy patches](../../build-support/java/remediation-nojpeg2000/profile.py)
check actual JP2/raw J2K content before OpenPDF image parsing; inspect parsed PDF
`/Filter /JPXDecode` entries (including arrays/indirect objects) for background
and remote PDF tile imports; and explicitly reject JPEG2000 output aliases.
Asynchronous tile errors retain a fatal format refusal instead of yielding a
blank or annotated successful print. Final-page header/footer errors are checked
after PDF finalization, with failure-safe resource cleanup. File/data/remote
image paths share the same refusal, regardless of filename or supplied MIME.
The inherited data-URI null-path error in SVG dispatch is repaired narrowly.

MapFish maps these intentional failures to HTTP 415 with a fixed message and
removes failed private print files. JPEG2000 aliases disappear from the dynamic
ImageIO-derived output list. New URL buffering is bounded to 64 MiB, with
30-second URL connection/read limits and an elapsed read deadline; oversized
input returns HTTP 413 without a placeholder. This explicit security-related
limit is a candidate behavior difference, not an unchanged historical guarantee.
The ordinary format and print fixtures remain within these bounds.

## Evidence and integration

[The compact evidence index](../verification/json-jpeg2000-remediation/imaging-evidence.json)
links source build and component probe receipts, predecessor failures and exact
fixture/source identities. Component substitution tests are labeled as such;
they are not acceptance of a packaged successor WAR. They cover exact raster
pixels/georeferencing, JPEG error bounds, three TIFF fax modes, actual MapFish
PDF/PNG/TIFF output and decoded raster content; JP2/J2K provider/class absence;
genuine inputs with misleading filenames/MIME; output alias refusal; PDF JPX
inputs/backgrounds; final-page headers/footers; 413/415 redacted servlet responses;
malformed input and subsequent valid operations. A negative control rejects the
parent WAR containing the original selected JJ2000 implementation.

The original JPEG2000-positive fixtures and results remain historical evidence.
They are intentionally deselected for this profile, not counted as passes.
The Marlin 46/48 and Java7-target LTW limitations remain unchanged. Source and
engineering review are not license clearance or owner adoption.

The integrator calls `profile.prepare(work / 'source')` before source inventory
and compilation and `profile.inspect_artifacts(build, jar_entries, class_origins,
libraries)` on the new aggregate. The latter recursively inspects archive bytes,
class identities, original-code fingerprints, SPIs, native payloads and retained
indirect references while requiring ordinary imaging definitions and the guard.
[The replacement mapping](../verification/json-jpeg2000-remediation/imaging-replacement.json)
contains only the new JAI row for integration with unchanged selected components.

After building the new coherent WAR, rerun the same wrapper without
`--component-replacement`:

```sh
python3 build-support/java/remediation-nojpeg2000/probe.py \
  --workspace /home/revelberry/Projects/AmbisGIS \
  --war /absolute/path/to/the/new/geoserver.war \
  --expected-war-sha256 ACTUAL_NEW_WAR_SHA256 \
  --output /fresh/private/probe-directory
```

Use host `/usr/bin/python3` through `flatpak-spawn --host` where the IDE namespace
requires it. The wrapper uses the existing verified socket-denial runner. Fresh
exact-WAR PostGIS/mosaic, service formats/imports, printing HTTP, authorization,
GWC cold/restart and frontend/backend restart results must be linked by the
integrator before the variant-specific closing condition is satisfied.

The affected original MapFish native selection was also rerun from fresh copies
with the existing EMF pin and candidate replacement inputs: 71 passed, six
unchanged skipped, zero failures/errors. The [native receipt](../verification/json-jpeg2000-remediation/imaging-native-mapfish.json)
binds its source changes, verified compile socket denial/runtime loopback control
and stopped fixture servers. The failed pre-test run without the historical EMF
pin remains retained. Component probe 11 adds actual defining-JAR and class-byte
hash checks for every changed MapFish guard class and retained JAI providers;
its compiled witnesses cannot shadow a packaged production class. Final exact-WAR
mode applies those checks to unchanged extracted WAR libraries without any
production source overlay.
