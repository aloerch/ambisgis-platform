# FND-07 QGIS local publication snapshot

The authorized local repair is complete. **No QGIS source ref, archive, repository
setting or visibility was published or changed.** Existing public fork branches,
tags and GitHub's fork network are not purged or certified clean by this snapshot.
The finite next decision is acceptance/publication of this exact isolated root
under that explicit hosting boundary; it is not a new permission search.

Owner `aloerch` (ID `15285626`) authorized local preparation in
[issue #6 comment 5863464446](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863464446),
created `2026-09-28T04:35:51Z`; body SHA-256
`87d79df2d4458d9570c269ff9d20310c4117f7d82c2dc23d4588ca505900da1f`.
This authorizes local preparation, not publication of either old or changed QGIS.

## Exact source and recovery

- Repository: `aloerch/ambisgis-qgis`, numeric ID `1376927721`.
- Accepted original commit/tree: `1a4cda5f2620e7374e5926fc955a7d2d06493e15` /
  `c8542e82e3c3810950f32ce8d58a16bfed12e6c8`.
- New local parentless commit/tree: `86af40542b219b0da6df1a43914413443330c0c0` /
  `84ea1b18fdf5721819fee34fe06cdef7ea82afdc`.
- Proposed review destination: `refs/heads/ambisgis/review/fnd-07-publication-snapshot-v1`.
  Proposed canonical destination: `refs/heads/ambisgis/main`.
- Private bundle SHA-256: `3f822df157c4c15dd8ebe5b877b2555102f586d8be8e6be307b8899fd8cf8f2f`,
  209,753,585 bytes. It is self-contained and has no predecessor prerequisite.
- Final preparation receipt SHA-256:
  `f9828bf21e349a596c3ed16c58287c4f26dce1a271aab5f4cf15ab336f20d4eb`.

Retained run directory:
`/home/revelberry/Projects/AmbisGIS/build-worktrees/canonical-and-publication-repairs/run-002/qgis/attempt-003`.
It contains `source.git`, the bundle, independently restored `restored.git`,
full `source-provenance.json`, `expected-tree.json`, `forbidden-object-ids.json`,
resource stages, actual preparation/verification/test receipts and logs.
The platform checkpoint includes compact evidence and hashes only; it does not
include the full source, bundle, omitted palette payloads or old source history.

Both new and restored repositories have exactly 32,995 stored/reachable objects:
one parentless commit, 4,015 trees and 28,979 blobs. All 32,451 source entries are
verified against the complete original-file mapping. Full strict Git fsck passes.
No excluded blob, extra stored object, backup ref, parent, alternate/shared or
hardlinked object, replacement/graft, hook, filter, promisor or shallow dependency
is present. Restoration reads only the self-contained local bundle; it uses no
original object store or donor/network fallback. Separate verification compares
the result against immutable accepted inputs without reconstructing missing data.

## Exact change and attribution

The [omission report](../verification/canonical-and-publication-repairs/qgis-exclusions.json)
is bound to the accepted map SHA-256
`a1b259c8e422d52f63aba093d49af915301c6b4b7c11bb134d0a600d31f6e43c`.
It contains exactly 1,130 SVG paths representing 1,129 distinct original blobs;
`gmt/GMT_dem1.svg` is the recorded duplicate of `td/DEM_print.svg`. No excluded
blob appears under another retained source path. The retained source scan also
checks 39 detected ZIP/tar/gzip containers and 135 expanded members for those
payload identities; all 13 Qt resource definitions have no cpt-city embedding.
This establishes the named-payload boundary, not arbitrary transformed-content
or blanket licensing clearance.

The [19 catalogue changes](../verification/canonical-and-publication-repairs/qgis-catalogue-changes.json)
remove 107 references. Each changed file adds a prominent modification comment
dated `2026-09-28`; the source commit uses the actual preparation timestamp and
configured operator identity. Original authorship is retained through source
headers, `doc/AUTHORS`, unchanged notices and the complete original/new file-blob
mapping. All 84 omitted-collection metadata/notice files remain in source and
are relocated unchanged outside the active palette archive during packaging.
No entire resource collection is deleted by pathname prefix.

All 265 ColorBrewer palettes and their exact original notice remain. This product
includes color specifications and designs developed by Cynthia Brewer
(http://colorbrewer.org/). Its acknowledgment/naming conditions, the original GMT,
font/icon, third-party dependency, copyright, license and branding obligations
continue. Removing the identified optional palettes resolves this specific source
payload hold; it grants no blanket redistribution permission. [Attribution hashes](../verification/canonical-and-publication-repairs/qgis-attribution.json)
identify preserved original notices without rewriting their text.

## Functional comparison and tests

All executable C++/Python/provider code, compiler inputs and editable build scripts
retain their exact paths, Git blob identities and modes. The complete source delta
is limited to 1,130 omissions, 19 catalogues and two new provenance/notice files.
No QGIS compilation, database/browser stack or native runtime suite was started.
Previously executed native/runtime evidence remains historical evidence for the
unchanged functional composition, not a new build from this root.

The original `resource_selection.py` is byte-identical to its accepted SHA-256
`03a0562feeca2201c1882c9f4b45b72885a814c1ff89fb2d6019f21278079954`.
The new `publication_selection.py` adapter is explicit and variant-bound; it never
reads old source archives or tolerates arbitrary missing files. Its palette/notice
projection has 4,371 entries: 4,351 exactly match the accepted stage, 19 differ only
by the precise new XML comments, and one added publication notice is identified.
The full selected projection has the same resource paths and effective XML;
all 265 ColorBrewer payloads remain exact. Two fresh stages match. Unchanged
reapplication reports `already-exact` with zero mutations.

Fresh checks include 21 publication guard tests and all 75 existing QGIS harness
tests. Real copied-stage negative checks reject a missing complete stage, a missing
retained palette, changed palette bytes and an extra file, with no reconstruction.
Trusted receipt verification rejects tampering and recomputes complete source and
catalogue comparisons. A successful Git subprocess never overrides final integrity
or publication failures. These are source/recovery/packaging tests, not new GIS
native acceptance, FND-08 build/drift tests or OWN-02 full repair evidence.

The first source attempt failed on Git fast-import Unicode path quoting; the
failure and crash log remain in the parent run directory. Attempt-002 passed but
used a temporary adapter placement in the old selector; independent integration
review found this would invalidate accepted recovery pins. It remains retained,
then attempt-003 was freshly executed with a separate adapter and untouched original
selector. Independent review also found that verification could recreate a missing
stage; `verify_only` now refuses that condition and a regression exercises it.
No failed receipt or original source history was overwritten.

## Resume and next decision

From the platform worktree, verify the exact successful run into a **new** receipt:

```sh
python3 -B build-support/source_publication/qgis_snapshot.py verify --help
python3 -B build-support/source_publication/qgis_snapshot.py verify \
  --workspace-root /home/revelberry/Projects/AmbisGIS \
  --receipt /home/revelberry/Projects/AmbisGIS/build-worktrees/canonical-and-publication-repairs/run-002/qgis/attempt-003/result.json \
  --receipt-sha256 f9828bf21e349a596c3ed16c58287c4f26dce1a271aab5f4cf15ab336f20d4eb \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/canonical-and-publication-repairs/run-002/qgis/attempt-003/verify-NEXT.json
python3 -B -m unittest discover -s plan/tests -p test_qgis_publication.py -v
python3 -B -m unittest discover -s build-support/qgis -p 'test_*.py' -v
```

The [exact proposal](../verification/canonical-and-publication-repairs/qgis-publication-plan.json)
requests creation-only review/canonical refs at the new commit/tree, preserving
`master`, all existing refs/history and Actions disabled. Expected-old observations
are dated evidence and must be re-read; they do not grant publication authority.
Any conflicting ref or changed setting holds the operation. The accepted FND-02
manifest remains immutable. New source review/publication and final three-criterion
FND-07 acceptance remain pending; FND-08 has not started. [ADR 010](../adrs/010-qgis-publication-source-boundary.md)
records the deliberate public-history boundary and its limits.
