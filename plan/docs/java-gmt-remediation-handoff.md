# FND-02/F02-06 Java/GMT remediation handoff

This is proposed candidate revision 3/schema 1, `fnd-02-java-gmt-proposal-3`, on
`fnd-02/java-gmt-selection-remediation`, based on owner-merged #66/main
`6b2e2fd7edc91746748d916d34af01f0a681e342`. The current owner prompt separately
[authorizes implementation](../verification/java-gmt-remediation/authorization.json).
FND-02 stays **In progress**. No merge, adoption, distribution, release or later-task
acceptance is granted. The four criteria and eight pass conditions are unchanged.

## Selected artifacts and history

| Artifact | SHA-256 |
|---|---|
| Parent revision 2 manifest, preserved byte-for-byte | `3c59d99834b53f8778143db70f754272bce9920ca05071586d4f3629cdd625a0` |
| Final aggregate-02 WAR | `e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044` |
| Source-built AspectJ runtime | `5bf41bf5474d618423d2a6d8042468cf4e7e57db8895604f205d75fe61d5090b` |
| Source-built AspectJ weaver | `e35095ad483cc38a2cf17777f74f9a59abafed1fcabc7cf951b1fbf8153370d6` |
| Source-built XMLPull API | `fb4f2393e1cdf1c078a7800312eac6d1392ebd27c3015d06c25401d3bd705573` |
| Source-built json-lib compatibility variant | `92c744bdb2ed2a6ff255af473f271bf3954e00ab037ed5649a39056eeab2fbf2` |
| Java-only JAI ImageIO variant | `51dc61ca6724ba307f7d8407aa276e2c56c11d6ad6093d62820abef0ab0880f2` |
| Headless Temurin17 Marlin variant 2 | `14633f73fed7e30553927201309bcaf407a9f5462fce87692f196859f33d074a` |
| QGIS selected stage membership manifest | `a2152edc50a7fdb34401e148c1eec238dfdf5dad6600faf73e92a063a4c47baa` |
| Omitted GMT alias original bytes | `0ba1cad3e42202036ab6a86663a09d377eb84eb22584df0e4dbc9fdee54cf602` |

The eleven owned root revisions are unchanged. Source archives, original publisher
binaries, source mismatches, previous branches/stages and unsuccessful attempts
remain retained. Source/recipe/input trees were frozen before aggregate execution.
Maven filenames are local resolution keys; embedded variant identities and locked
replacement mappings explicitly disallow treating modified binaries as publisher
releases. Nothing was published to donor package namespaces.

## Profile and source changes

The **NO-ORACLE/headless-Temurin17** profile removes Oracle dependencies and the
exposed importer option through five exact source/compiler guards. It retains
shared image-mosaic abstractions used by PostGIS/SQLServer, importer, printing,
PostGIS, GeoFence/PostgreSQL, authkey, strict GeoNode verification, stateless bearer
handling, diagnostic redaction and finite role/cache controls. It does not substitute
an old driver or an empty class. Whole-WAR provider/class/native/fingerprint checks
and active datasource discovery inspect actual selected definitions. Oracle-backed
stores/imports/mosaic indexes are unsupported; future support needs usable source,
compatible terms, an explicit profile and actual affected tests.

AspectJ builds coherent runtime/weaver from complete release/BCEL source without
the unused BEA/JRockit adapter. XMLPull uses retained publisher API sources and its
public-domain dedication. json-lib uses a distinct compatibility build from
`1ff8dc03730cb00afb4628350f3106f35c122d34`, not invented 2.4.2 provenance.
JAI ImageIO uses recovered FCS source at
`c3c86a17fecc8a2d9b83bd0e6f686542c55d294b`; proprietary codecLib paths and inactive
javax.media.jai bridge are omitted, while ImageN/imageio-ext stay selected.
A narrow signedness fix preserves packed-RGB JPEG2000 values.
Marlin uses actual 0.9.4.8 source at
`5b1cbb57c39082cc444807daec401dd033754af7` with explicit headless/no-OpenGL
requirements and exact module loading. Two unused benchmark helper classes whose
file lacks a designated Classpath exception were excluded from variant 2; original
source/notices remain. All selected 42 production Java files carry the explicit
GPL2+Classpath notice. No unpatched renderer fallback can satisfy the witness.

[QGIS detail](java-gmt-qgis-handoff.md) records exactly one extra palette exclusion,
1,130 cumulative omissions, 265 unchanged ColorBrewer palettes and zero compilation.
Identical palette bytes do not prove identical licensing; exclusion avoids the
uncertain origin without declaring the GMT grant invalid.

## Remaining blockers and finite next action

Two targeted adoption blockers remain, independently of technical success:

- **F02-JAVA-json-lib:** recover the applicable historical grant chain for the
  seven JSON.org-derived files, or implement a compatible source-owned replacement
  under verified terms. Apache headers/POM assertions alone do not establish the
  missing derived rights.
- **F02-JAVA-jai-imageio11:** resolve the separate JJ2000 conforming-product
  restriction for the intended GPL combination, or source-build a compatible-term
  JPEG2000 implementation and retest the required codec/printing/raster behavior.
  The Sun BSD core notice does not clear the add-on; JPEG2000 cannot simply vanish.

The smallest next coherent engineering action is those two source/terms repairs,
followed by one changed-artifact aggregate and affected checks using these retained
fixtures. Neither blocker can be waived by checkpoint review. The other five
findings close only within the tested variant and preserve applicable notice/profile
obligations. All unrelated 51 findings, original source-ledger/build-only gaps,
ColorBrewer/IFC/distribution, security, signing and deployment gates remain.
F02-07 maintenance binding is documentary; F02-08 criterion acceptance remains missing.

## Runtime and evidence scope

The [compact evidence index](../verification/java-gmt-remediation/evidence.json) and
[generated decision register](fnd-02-owner-decisions.md) identify exact final results. Aggregate packaging skips tests and is not runtime acceptance. Historical
XML/MapFish/OAuth native suites and QGIS 66 C++/16 Python suites were not rerun as
whole suites. Database/Jupyter native results and selected frontend replay-02/IFC
compilation/native results are integrity-only reuse. Five inherited frontend lint
errors remain failed. No fresh frontend compilation or full product parity claim.

Preserved failures include the first GeoFence invocation's missing lifecycle
attachment (35 tests passed before Maven failed; package-stage rerun passed all
62), original JAI packed-RGB clipping before the scoped repair, source-probe
iterations, failed mosaic fixture attempts and a replaced preliminary Marlin/WAR.
Two native JSON BeanUtils introspection expectations fail identically on original
and variant (357/359 pass). Java7-target LTW fails identically on original/variant;
Java5-target weaving and actual Spring advice pass. The Marlin upstream line-join
suite retains two identical baseline/variant failures out of 48 for a degenerate
line-after-close path; no golden or tolerance was weakened. These are explicit
runtime limitations, not hidden successful native suites.

Offline/loopback controls, sandboxed Chromium and the existing PostgreSQL-only
supervision exception are retained. All credentials are synthetic and scrubbed or
invalidated, task services stopped and cleanup receipts checked. No new containment
exception, public listener, employer/production system or upstream contact.

## Exact resume commands

Run from `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-gmt/plan` with the
verified JSON-Schema Python environment (IDE `/tmp/ambisgis-validation-venv/bin/python`):

```sh
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --eligibility
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --report
python3 tools/validate_candidate.py candidates/fnd-02-candidate-parent-2.json --workspace-root /home/revelberry/Projects/AmbisGIS --platform-root /home/revelberry/Projects/AmbisGIS/ambisgis-platform-remediation
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

Inventory/report exit 0 verifies evidence; eligibility exit 2 retains ungranted
adoption/distribution gates. Do not overwrite retained runs. Actual aggregate,
component and runtime invocation arrays are in the indexed receipts; choose a fresh
output directory for any rerun. The final review head/PR and live Project receipt are recorded in publication
evidence and issue #3 without promoting Delivery.

## Final checkpoint validation

[Validation receipt](../verification/java-gmt-remediation/validation.json): 251 package
tests and four schemas pass; Java 383, frontend 39, QGIS 75, GWC 59 and containment 15
guards pass. Actual inventory checks 723 records, 50,817 complete-tree entries and
484 archive members across 11 roots, 10 profiles and seven combinations. Integrity/report
exit 0; eligibility exit 2. Exact candidate manifest SHA256:
`8083a10deee529363e15925941c28e5a1e1f3030716f0cac7154c39466efbb90`.

Independent source/imaging, Oracle/mosaic and candidate/acceptance reviews are
linked in validation. Initial stale generated-register package failure is retained;
regeneration via the unchanged validator resolved it. All task-owned services are
stopped; final process audit and fixture credential cleanup are retained.
