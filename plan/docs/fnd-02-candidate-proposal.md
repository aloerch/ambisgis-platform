# FND-02 candidate proposal — independent JSON / NO-JPEG2000 revision 4

**The two remaining variant adoption blockers are remediated; FND-02 remains In progress pending explicit owner acceptance.**
The [active manifest](../candidates/fnd-02-candidate.json) selects
`fnd-02-json-nojpeg2000-proposal-4`, candidate revision 4/schema 1.
All eleven owned roots, 58 finding IDs, 56 unaffected findings and the original
[four criteria/eight general pass conditions](fnd-02-completion.md) are preserved.
Inventory validity, owner adoption and distribution remain separate gates.

The [unchanged parent revision 3](../candidates/fnd-02-candidate-parent-3.json),
SHA256 `8083a10deee529363e15925941c28e5a1e1f3030716f0cac7154c39466efbb90`,
comes from reviewed/merged #67, main `8f66b1e2a421d93e0c8d9714df76ad2dd62269a3`.
Its source, WAR and failed receipts remain preserved. The
[owner instruction](../verification/json-jpeg2000-remediation/owner-instruction.txt)
separately authorizes this implementation and supersedes only mandatory JPEG2000
preservation. It does not adopt or authorize distribution of the successor.

## Exact selected change

Final WAR SHA256: `90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1`.
An independently authored, bounded net.sf.json API replaces the entire old
json-lib production layer. It uses unchanged retained Jackson core 2.21.0;
exact shaded FastDoubleParser 2.0.1 correspondence and supplemental MIT/BSL/BSD
notices are retained. This is engineering provenance, not a formal legal
clean-room claim or a grant for excluded originals.

The Java/server profile is **NO-ORACLE / NO-JPEG2000 / headless Temurin17**.
Source/SPI exclusion removes the disputed JJ2000 implementation and dependent
JPEG2000 providers while preserving 132 ordinary ImageIO source files and 323
classes byte-for-byte against the preceding source-built core. Native OpenJPEG
and a Java wrapper are not introduced. [The dated choice and scope](jpeg2000-exclusion-handoff.md)
compare optional capability loss with native codec security, wrapper, ABI and
maintenance costs, including the official maintenance warning.

Affected routes explicitly reject JP2/raw J2K, JPEG2000 output and JPX-compressed
PDF input. Ordinary JPEG/PNG/TIFF/GeoTIFF, actual PDF/image printing, PostGIS
vector/mosaic, WMS/WFS, identity, cache and browser restart checks pass.
Seven service profiles remain selected: importer, oauth2-geonode,
geofence-server, geofence-server-postgres, printing, postgis and authkey.
Malformed importer JSON returns a controlled 400; six actual converters preserve
valid recovery, including their existing transform-chain reader contract.

QGIS/GDAL/notebook inputs are unchanged. QGIS uses its separate spatial-04 GDAL
prefix and retains Exiv2 JP2 metadata support; this is not project-wide JPEG2000
removal. Frontend replay-02 and the QGIS palette selection are unchanged.

## Findings, evidence and review

The [generated register](fnd-02-owner-decisions.md) records zero variant adoption
blockers and retains distribution/source/notice obligations. JSON's closing
condition is unchanged. JAI's condition records the owner-authorized tested
removal alternative and preserves the earlier mandatory-JPEG2000 condition in
history. No rights to original JSON-derived/JJ2000 code are inferred.

[The compact evidence index](../verification/json-jpeg2000-remediation/evidence.json)
and [seven-combination matrix](fnd-02-combination-smoke.md) distinguish fresh
exact-WAR execution from integrity-only reuse. Packaging skips test execution;
fresh native/contracts, real database/authorization/printing/cache/browser checks
supply affected acceptance. Unchanged database, notebook, QGIS and frontend
compilation/native/IFC results remain historical execution.

Historical JSON 357/359 BeanUtils expectations, Marlin 46/48, Java7-target LTW,
six native MapFish skips and five frontend lint failures remain visible. No
unsafe class introspection, -noverify or rendering-tolerance change is used.
Transient ZIP preflight limits are 1 GiB compressed/10,000 entries; inherited
multipart buffering is not comprehensively hardened. New MapFish loaders and
byte-array validation apply 64 MiB limits; this is not a blanket bound on
inherited HTTP buffering. Native remote mosaic harvesting and TIFF-JPEG2000
variants retain their documented pre-existing limitations.

## Final decision

The [criterion report and maintenance binding](fnd-02-json-nojpeg2000-acceptance.md)
complete F02-06's decision-ready summary, bind F02-07 to the existing chapter 11/08
rule, and present F02-08's four original criteria in this same PR. Owner review
must expressly cover the exact candidate, capability limits and maintenance rule.
Merging a checkpoint alone does not accept the whole task. FND-03/05/07/08,
OWN-02, License/Brand, security, signing and deployment retain their later scope;
full product implementation is not a new FND-02 acceptance condition.

[The engineering handoff](json-jpeg2000-remediation-handoff.md) gives exact inputs,
commands, failures, cleanup and review limits. No merge, adoption, distribution,
release or production change is performed.
