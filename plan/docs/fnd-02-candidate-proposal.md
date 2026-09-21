# FND-02 exact candidate proposal — frontend/QGIS revision 2

**Inventory evidence is validated separately from candidate adoption and distribution.**
The active [manifest](../candidates/fnd-02-candidate.json) is
`fnd-02-frontend-qgis-proposal-2`, candidate revision 2, unchanged manifest schema 1.
The [generated decision register](fnd-02-owner-decisions.md) presents all 58
dispositions from the authoritative manifest. FND-02 remains **In progress**; the [eight-row checklist](fnd-02-completion.md)
retains every original criterion and pass condition.

Owner-merged [#65](https://github.com/aloerch/ambisgis-platform/pull/65), reviewed
head `bc60bbcbfccb840853c858a29ca9ec3ae4292656`, merge
`b31e81ad7bfe328d5a8b3ea579eff09e6a0086e7`, accepted the consolidation checkpoint.
Its exact [baseline manifest](../candidates/fnd-02-candidate-baseline-1.json),
`fnd-02-tested-proposal-1`, remains byte-for-byte SHA-256
`18d80d6e7520e3a16db023bbff87cd2dc20a33ba921bd4f26e49a67d71a0aace`.
The [current prompt authorization](../verification/frontend-qgis-remediation/authorization.json)
authorizes implementation of this separate variant; adoption and distribution
remain unaccepted. It is not retrospective permission attributed to #65.

## Selected changes and remaining decisions

Only frontend-build and qgis-desktop-server profiles and their two combinations
change. All eleven owned roots, eight other profiles, five other combinations,
original records/archives/stages and non-targeted findings remain unchanged.
The selected #61 WAR, GeoNode/client wheels, database and notebook artifacts are
integrity-checked reuse, with their original native/runtime scope preserved.

- **Frontend recipe:** contemporaneous evidence did not establish the original
  build-01 executed recipe. Authorized replay-02 physically executes a frozen
  tooling snapshot into fresh trees. Its new native tests and browser-02 real
  backend/load/zoom/reload/restart evidence bind the actual served bytes. Five
  inherited lint errors still fail; five webpack warnings remain. Output differs
  in six entry files and 506 renamed chunks; no byte-identical build claim.
- **IFC retained:** exact web-ifc 0.0.50 C++/TypeScript source and eight pinned
  dependency archives, nested notices, historical build/binding/toolchain inputs
  and source availability index are retained. Offline native compilation/six
  upstream tests and an unchanged Node-WASM synthetic box geometry/save/reopen
  probe demonstrate bounded usability. All 13 frontend IFC assets remain unchanged;
  browser/Node identical WASM bytes preserve origin ambiguity. No independent
  Emscripten bootstrap or broader 3D/generated-runtime acceptance is claimed.
- **QGIS resources:** deterministic selection-03 excludes the exact 1,129 named
  optional palettes, corrects 19 catalogues, relocates 84 metadata files without
  changing their bytes, adds notices and retains 265 ColorBrewer palettes. All
  8,003 unrelated files and binary/mode identities remain unchanged; zero compile
  steps were needed. Fresh runtime-07 verifies chooser, actual retained colors,
  serialized vector/raster styles, desktop interaction, PostGIS/server GetMap and
  restart from the selected prefix. Existing explicit renderer colors survive the
  tested omitted-ramp project; absent named ramps cannot support reclassification.

Five targeted adoption blockers close for this variant. **Seven remain:** AspectJ,
xmlpull, JAI ImageIO, json-lib, Marlin, shipped ojdbc17 source and QGIS SRC-02.
The latter's removed `td/DEM_print.svg` is byte-identical to retained
`gmt/GMT_dem1.svg`, SHA-256
`0ba1cad3e42202036ab6a86663a09d377eb84eb22584df0e4dbc9fdee54cf602`.
Different notices do not establish origin or broader permission. No 1,130th
palette was silently removed. The smallest next choice is exact authoritative
provenance recovery or a separately authorized one-file exclusion and affected
staging/tests. This gates adoption/distribution, not independent engineering.

The IFC finding becomes a distribution/source/notice obligation, not blanket
approval. ColorBrewer acknowledgement/naming, other retained resource/font/icon
terms, original archives and all other distribution/later gates remain unchanged.
Six Java blockers require one coordinated source/codec/rendering batch with one
deliberate Oracle-support decision and one affected aggregate rebuild/test plan.
No Java replacement, driver exclusion or WAR mutation is part of this checkpoint.

## Validation and retained evidence

Use the actual `plan/` directory and the retained JSON-Schema validation environment:

```sh
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --eligibility
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --report
python3 tools/validate_candidate.py candidates/fnd-02-candidate-baseline-1.json --workspace-root /home/revelberry/Projects/AmbisGIS
python3 tools/validate_candidate.py candidates/fnd-02-candidate-baseline-1.json --workspace-root /home/revelberry/Projects/AmbisGIS --eligibility
python3 tools/validate_candidate.py candidates/fnd-02-candidate-baseline-1.json --workspace-root /home/revelberry/Projects/AmbisGIS --report
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

The supported positional manifest argument selects the baseline; default selects
the variant. `--report` validates first and writes deterministic Markdown to stdout;
only an explicit redirect changes the register. Report identity/link now reflects
the selected manifest. Schema, path confinement, source identity, hashes, JSON
assertions, archive membership, complete tree and eligibility checks are unchanged.
Exit 0 is inventory validity; exit 1 is unsuccessful validation; eligibility
remains exit 2 with ungranted owner/distribution acceptance. A nonzero eligibility
result is not a failed integrity check. Hash verification is not native execution.

[Validation](../verification/frontend-qgis-remediation/validation.json) records
actual counts, timings, manifest and tool hashes. [The engineering handoff](frontend-qgis-resource-selection-handoff.md)
indexes exact identities, commands, failures, independent reviews and containment.
Component details: [frontend](frontend-remediation-handoff.md),
[IFC](webifc-remediation-handoff.md), [QGIS](qgis-resource-selection-handoff.md).
Retained source/build/runtime data stays under the supplied workspace mapping;
missing files fail validation. Neither the index nor linked inventories claim
complete transitive source rights or toolchain closure.

## Maintenance and acceptance boundaries

This proposal binds F02-07 to [chapter 11 §§6–7](11-independent-product-and-source-ownership.md)
and [chapter 08](08-repositories-and-licensing.md): selected owned revisions and
retained inputs are authoritative. Donor releases/disclosures are advisory inputs;
imports, backports and independent repairs require AmbisGIS review, affected tests
and a new manifest revision. There is no automatic synchronization or unsupported
indefinite freeze. Documentary binding records no new owner policy acceptance.
F02-08 and whole FND-02 acceptance remain pending.

FND-03 policy, FND-05 publishing, FND-07 canonical baselines, FND-08 full initial
source/bootstrap closure, OWN-02 repair/recovery and signing/deployment retain
their gates. Required unusable source or invalid rights cannot be deferred merely
to approve this selection. Review of this checkpoint accepts only its exact
bounded remediation and accurate remaining-blocker record; merge is separate
from component adoption, final criterion acceptance and distribution permission.
