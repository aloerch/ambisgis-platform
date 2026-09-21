# FND-02 exact candidate proposal — F02-06

This is an **internal candidate manifest**, not a comprehensive or certified SBOM,
a release lock, legal clearance, or approval of fork defaults. The authoritative
machine record is [fnd-02-candidate.json](../candidates/fnd-02-candidate.json);
the [generated owner-decision register](fnd-02-owner-decisions.md) presents its
findings and concrete alternatives. Inventory integrity, candidate selection and
owner acceptance are deliberately separate results. The selected bytes remain the
tested bytes; all proposed replacements/exclusions are unbuilt variants.

The base is current `ambisgis/main` at
`725d519820293f466b287d7f4cd779c36b9b7977`. Live verification confirms owner-merged
[#64](https://github.com/aloerch/ambisgis-platform/pull/64), reviewed head
`ee5be14d9d0d14f361dbd235dedc64b3fdb84db0`, at that merge. This accepts bounded
F02-05 only. [The four criteria and eight pass conditions](fnd-02-completion.md)
remain unchanged. FND-02 stays **In progress**.

## What the proposal selects

Eleven source roots come from the approved repository manifest. Exact commits,
annotated tag objects, the MapStore gitlink, original provenance and retained
acquisition history are distinguished. Acquisition snapshots are not approved
product baselines. Ordered guarded changes and hashed recipes connect sources to
specific builds; later documentation commits are not substituted for tested
implementation trees.

The [combination matrix](fnd-02-combination-smoke.md) supplies seven scoped
combinations. Database/native, Java servlet, GeoNode Python, frontend/browser,
QGIS spatial/XML/Qt/Python and notebook Python profiles retain their own versions
and processes. Distinct versions across these processes are not automatically an
ABI conflict. The successor #61 WAR is selected only for combinations that used
it; older native Java probes retain their original scope. This proposal does not
claim simultaneous execution of one global environment.

The index binds component input locks, selected source/patch/recipe records,
producing receipts, output identities, smoke evidence and complete frontend/QGIS
staged inventories. Coverage is explicit per record. Linked dependency locks are
not a claim that all transitive source/generated contents or host tool bootstrap
have been proved. Source-bearing wheels, classifier archives, embedded classes,
WASM, fonts and palettes each require their actual evidence. Original failed
attempts remain retained and are not counted as successful selections.

## Read-only validation and retention mapping

Run from this worktree's actual `plan/` directory with Python and the existing
`requirements-validation.txt` environment (JSON Schema support is required):

```sh
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --eligibility
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --report
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

`platform` maps to this checkout (or explicit `--platform-root`); `workspace` maps
to the supplied AmbisGIS retained-evidence directory. Manifest paths are confined
relative paths, not arbitrary host paths. A missing mapping/file is an unsuccessful
validation, not an invented hash. Retained files under `source-archives/` and
`build-worktrees/` stay outside Git. Historical absolute paths inside original
receipts are evidence; the resolver does not follow them as instructions.

The validator checks schema, duplicate JSON keys/identities, approved roots,
source commits/tags/gitlink against owned repositories, record hashes, references,
ordered recipes, JSON evidence assertions, named archive members and the named
complete output trees. It uses the existing QGIS inventory comparison after
checking path confinement and symlink identity/target confinement; frontend trees
also require the integrated map entry. It never downloads, extracts archives,
executes build hooks, starts services, modifies repositories, invokes an importer,
or writes a report by default. `--report` prints deterministic Markdown to stdout;
explicit shell redirection can update the checked-in register.

Exit **0** means inventory integrity validation succeeded, even when documented
selection blockers remain. Exit **1** means syntax/schema, references, identity,
bytes, membership or availability failed. `--eligibility` exits **2** while owner
acceptance/distribution permission remains ungranted; the tool cannot confer legal
eligibility. Its JSON always names selection blockers and separates acceptance.
Hash verification is not a new native test, reproducible build, source audit of
every transitive byte, or legal opinion.

## Selection and maintenance boundaries

All known source/license findings are addressed in one generated register. It
separates resolved evidence, implementable notice/source obligations, actual
selection blockers, investigation records and justified later gates. Missing
package metadata alone does not establish missing rights; a permissive root
license does not cover unrelated bundled contents. GPL/LGPL and exceptions are
preserved, without arbitrarily choosing an alternative. Qualified review is
requested only for the exact applicability questions stated in the register.

The smallest remediation batch is a **separate candidate variant**, after the
specific owner choices in that register. Recover exact usable source and missing
notice applicability first; where necessary, propose capability-preserving owned
replacements or explicit exclusion of optional restricted material. Any changed
WAR, wheel, resource tree or bundle requires new identities and affected builds /
tests. Existing successful tests must not be attached to different bytes. Neither
merging #64 nor accepting this accurate investigation record adopts the candidate
or waives third-party rights.

This proposal binds F02-07 to [chapter 11 §§6–7](11-independent-product-and-source-ownership.md)
and [chapter 08](08-repositories-and-licensing.md): selected owned revisions and
retained exact inputs are authoritative; donor releases and security disclosures
are advisory inputs reviewed by AmbisGIS. Imports, backports and independent
repairs require provenance, affected tests and a new manifest revision. There is
no automatic synchronization or unsupported indefinite freeze. This documentary
binding records no new owner decision and does not satisfy F02-08.

FND-03 policy, FND-05 publishing, FND-07 canonical baselines/custody, FND-08 full
initial-spine source/bootstrap closure, OWN-02 repair/recovery and release signing /
deployment remain their existing gates. Required unusable source or invalid rights
cannot be deferred to these gates merely to approve a selection. No simulated
repair or unchanged runtime suite was started for this consolidation.

## Validation and engineering handoff

Manifest format version **1**, candidate ID is recorded in the manifest. The
[current validation receipt](../verification/candidate-selection/validation.json)
pins its SHA256 and tool identities. Actual validation covers **243 records**,
**11 owned repository/source bindings**, **10 profiles**, **seven combinations**,
**81 JSON assertions**, **80 ZIP members**, and **11,729 staged entries** (QGIS,
original/served frontend, and notebook static assets). It hashes about 5.9 GB of
listed retained files, independently of tree verification; this is not the size
of a product distribution. **239 package tests**, four existing schema/examples,
the candidate schema/report drift check, and **25 independent guard cases** pass.
No test was skipped. Original reviewed native/smoke results retain their dates.

The 58 dispositions yield **12 adoption blockers**. The smallest coherent
remediation proposal has three component batches, followed by targeted tests:

- **Java:** recover exact json-lib 2.4.2-geoserver/xmlpull 1.1.3.1 source and terms;
  propose complete source builds for AspectJ 1.5.4 and Marlin 0.9.4.8, a source-owned
  MapFish codec alternative for JAI ImageIO 1.1, and explicit exclusion of optional
  `gt-jdbc-oracle`/`ojdbc17` support (including both native driver libraries) if
  the owner selects that baseline. Preserve printing, PostGIS, raster/mosaic,
  rendering and authorization behavior; rebuild and retest affected exact WARs.
- **Frontend:** select retain-with-source-evidence for web-ifc 0.0.50, or an explicit
  optional-IFC exclusion variant preserving 2D capabilities. Resolve the original
  build-01 executed-recipe identity gap from additional contemporaneous evidence;
  if unavailable, select a separately identified build/replay with its own affected
  native/browser/restart evidence. The current payload is unchanged.
- **QGIS:** choose one optional-palette replacement/exclusion variant for the
  **1,129** resources across four distinct notice scopes, or obtain applicable
  permissions. Preserve styling/color-ramp capabilities and rerun affected resource,
  desktop/render/server tests for new bytes. The **265** ColorBrewer palettes are a
  separate notice obligation, not part of that restricted/unclear removal proposal.

The register gives each alternative's exact paths, evidence, consumer impact,
owner action, tests and closing evidence. Distribution-only notice/source and
later delivery obligations also need their stated dispositions; adoption does not
clear them. Newly recovered originals are retained under the explicit workspace
mapping, including exact web-ifc/emitter/jsonp publisher records and historical
source, uap-core revision and gsimporter revision. No maintainer was contacted or
new legal terms accepted.

A new chat should verify current main/PR state, this manifest hash and retained
mapping first, read the decision register, and continue only the selected coherent
remediation course. The final criterion package must distinguish acceptance of
this accurate C2 investigation from adoption of a component and distribution.
No fixed prompt count or additional smoke milestone is promised.

Review [PR #65](https://github.com/aloerch/ambisgis-platform/pull/65), frozen
implementation/evidence head `82b69845fd8550da612e026fed0755a5e9e00f50`.
[Project readback](../verification/candidate-selection/project.json) confirms two
writes, 77 → 78 items, all prior represented planning/view/archive data preserved,
parent FND-02 In progress, and #65 in `is:pr is:open`. This is API verification,
not a new UI acceptance. Later documentation commits preserve the manifest and
code. The final pushed review head is recorded in issue #3.
