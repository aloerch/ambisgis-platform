# FND-02 candidate proposal — Java/GMT revision 3

**Inventory validity, component adoption and distribution are separate gates.**
The [active manifest](../candidates/fnd-02-candidate.json) selects
`fnd-02-java-gmt-proposal-3`, candidate revision 3/schema 1. FND-02 remains
**In progress** with the same [four criteria and eight pass conditions](fnd-02-completion.md).
All 58 finding IDs and all eleven source-owned core revisions remain preserved.

The exact [parent revision 2](../candidates/fnd-02-candidate-parent-2.json) retains
SHA256 `3c59d99834b53f8778143db70f754272bce9920ca05071586d4f3629cdd625a0`;
[baseline revision 1](../candidates/fnd-02-candidate-baseline-1.json) retains
`18d80d6e7520e3a16db023bbff87cd2dc20a33ba921bd4f26e49a67d71a0aace`.
Owner-merged #66/main `6b2e2fd7edc91746748d916d34af01f0a681e342` supplies the
parent selection. The [current authorization](../verification/java-gmt-remediation/authorization.json)
explicitly selects these new implementation courses; the merge does not.

## Selected delta

One final aggregate-02 WAR, SHA256
`e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044`, packages
five source-built components (six JARs) and an explicit NO-ORACLE/headless Temurin17
profile. Original archives, mismatched predecessor sources, rejected builds and
old WARs remain custody evidence. Content-pinned local mappings and embedded
variant names distinguish modified outputs from upstream releases. Importer,
printing, PostGIS/mosaics, GeoFence/PostgreSQL, strict GeoNode verification, authkey,
stateless bearer/redaction and finite cache controls remain selected.

QGIS selection-01 derives from verified parent selection-03 and omits only the
additional `gmt/GMT_dem1.svg` alias with necessary catalogue corrections.
Cumulative 1,130omissions,265 unchanged ColorBrewer palettes, unchanged compiled
binaries and new actual desktop/server checks are [recorded](java-gmt-qgis-handoff.md).
Oracle datastores/imports/mosaic indexes and Marlin OpenGL are explicitly unsupported.
No Oracle account/database is needed or authorized.

## Findings and acceptance

Five targeted adoption findings have demonstrated variant-only remediation:
AspectJ, XMLPull, Marlin, selectedOracleplaceholder source, and QGIS SRC-02.
Two remain blocked: **json-lib's missing JSON.org-derived grant chain** and
**JAI ImageIO's separate JJ2000 GPL combination terms**. Complete source and successful
runtime do not resolve invalid or unverified rights. Exact closing conditions,
attempts and capability-preserving alternatives appear in the [generated register](fnd-02-owner-decisions.md)
and [handoff](java-gmt-remediation-handoff.md). The remaining 51 findings are unchanged.

All retained copyright/notices, IFC/ColorBrewer obligations, build-only/later-gate
source gaps and host/bootstrap limits remain. The five inherited frontend lint
errors remain. NativeJSON two BeanUtils expectations and Marlin two of 48 degenerate
path cases fail identically on old/new implementations; Java7-target LTW is likewise
unsupported while legacy Java5-target weaving and real Spring proxy behavior pass.
No full cartographic/provider/API parity is advertised.

## Evidence and verification

Ten profiles and seven combinations remain. Changed Java consumers and selected QGIS
stage receive fresh attributable tests. Database/Jupyter native results and
frontend replay-02/IFC compilation/native results carry forward with integrity
checks. Whole historical Java/QGIS suites are not rerun or assigned to changed bytes.
Full WAR/library/class/native/notice inventories and exact replacement origins
are checked; packaging with skipped tests stays packaging evidence only.

Use the supported commands in the [engineering handoff](java-gmt-remediation-handoff.md).
The unchanged validator verifies source/root identities, schema, paths, hashes,
JSONbindings, archive members and complete selected trees. Integrity/report exit0
means inventoryvalidity; eligibility exit2 records ungranted adoption/distribution.
No separate validator or weakened gate is introduced.

## Maintenance binding and finite next step

F02-07 remains bound to chapter11§§6–7/chapter08: owned revisions and retained
inputs are authoritative; later imports/backports/independent repairs need AmbisGIS
review, affected tests and a manifest change. Donor releases/disclosures are
advisory. No automatic synchronization or unsupported indefinite freeze.
This is documentary preparation, not an approving owner decision.

Review the bounded checkpoint and remaining blockers. The smallest next coherent
action is source/terms repair for JSON-derived code and JPEG2000, preserving current
contracts/formats and repeating affected aggregatechecks. F02-08 criterionreview
and full FND-02 acceptance stay pending. FND-03/05/07/08, OWN-02, License/Brand,
security, signing and deployment retain their own gates. No PR merge, adoption,
distribution, release, deployment or upstream contact is authorized here.
