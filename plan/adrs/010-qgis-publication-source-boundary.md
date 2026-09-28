# ADR 010 — A bounded parentless QGIS publication source variant

Status: local implementation prepared under the [separate owner decision](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863464446); changed-source publication and final FND-07 acceptance remain pending.

QGIS's accepted source commit `1a4cda5f2620e7374e5926fc955a7d2d06493e15`
contains 1,130 optional palettes already omitted from the accepted application.
The owner authorized an isolated local source snapshot that excludes those exact
payloads, preserving all retained source, attribution and original history in
controlled custody. A child deletion commit would retain the disputed payloads
through its ancestors and does not satisfy this publication boundary.

Prepare one parentless root with exact file/blob provenance to the accepted tree.
Remove only the 1,130 named SVGs; change 19 catalogues to remove their 107 references
and carry accurate AmbisGIS modification notices. Preserve all 265 ColorBrewer
palettes, the remaining GMT assets, original license/copyright texts, executable
code and editable build inputs. Add a source-provenance ledger and a publication
notice. Original full histories and removed assets remain in their existing
controlled custody under their actual rights restrictions; they are not included
in the proposed publication repository or its self-contained local bundle.

This is a narrow exception to continuous **public** Git ancestry, authorized by
the owner for this optional-resource boundary. Source ownership, repair capability,
original history custody and chapter 11 maintenance responsibilities continue.
The accepted FND-02 manifest and its executed artifact identities remain immutable.
The ledger maps the new source-only variant to that accepted functional composition;
it does not claim that previous binaries were built from this new root. A new
binary build acquires its own identities under FND-08.

The snapshot and its fresh bundle restore must contain exactly one root commit,
its complete expected trees/blobs and no forbidden or unreachable objects,
shared object stores, hardlinks, alternate objects, replacement/graft refs,
shallow/promisor dependencies, hooks, filters or network downloads. Resource
selection uses a separate variant adapter so the accepted selector's original
byte pins remain intact. The recovered source independently produces the accepted
palette/notice projection with only identified comment and provenance additions.

**This does not purge or certify the existing public fork, its other branches/tags,
or GitHub's fork network.** No existing history/ref, visibility or repository is
changed. The next owner review must explicitly accept publication of the exact
new root into the existing fork with that boundary, or retain it locally while
making a separate hosting decision. A new public repository or history rewrite
is not an authorized workaround.

See the [exact local handoff](../docs/qgis-publication-snapshot.md) and
[creation-only proposal](../verification/canonical-and-publication-repairs/qgis-publication-plan.json).
