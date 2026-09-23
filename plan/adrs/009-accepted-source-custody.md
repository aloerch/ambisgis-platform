# ADR 009 — Materialize the accepted source composition under platform custody

Status: proposed implementation for owner review; source-fork promotion pending.
Task: [FND-07](https://github.com/aloerch/ambisgis-platform/issues/6).

The owner's [separate FND-02 decision](https://github.com/aloerch/ambisgis-platform/issues/3#issuecomment-5785944488)
accepts candidate revision 4 for subsequent engineering. Its manifest remains
byte-for-byte unchanged. The separately hash-bound governance record establishes
that decision without rewriting historical approval fields or release permissions.

The eleven core repositories retain their original complete Git histories.
Recovery resolves their accepted commits from the existing verified bundles,
then replays the accepted platform recipes into new independent repositories.
Changed sources receive new, honestly dated local product commits; unchanged
implementations retain their accepted donor commits. The modified MapStore source
is materialized independently and the client product gitlink binds its actual
product commit. No original checkout, shared object store, alternates, hardlinks,
external filters, donor hooks or upstream network access supplies recovered objects.

The accepted platform revision is part of the source composition: it owns the
repair code, JSON adapter, generation inputs, packaging rules, dependency
selection and notices. The restoration receipt describes execution of the
existing candidate; it is not a second selection manifest or a release lock.
Generated QGIS data and selected resource views remain identified as generated
outputs with exact inputs/transformations, separate from editable source.
PostgreSQL/PostGIS/Jupyter build generation stays in its existing recipes.

Permanently modified Class B components remain platform-maintained vendor inputs
under chapter 11: AspectJ, XMLPull, independent JSON compatibility code, Marlin,
ImageIO, GeoFence/MapFish changes and the selected frontend helpers. Their original
source archives, source comparisons, patches/recipes and notice paths remain
bound to the existing candidate and replacement map. Jackson/FastDoubleParser and
IFC dependencies retain their own provenance and terms; retained binaries are
not represented as recovered editable source or fresh source-built outputs.
No additional public source repository is established by this decision.

The Java/server profile stays NO-ORACLE, headless-Temurin17 and NO-JPEG2000.
QGIS's exact optional-resource omissions remain packaging choices; original
excluded source and notices are retained only as historical custody material,
with original rights and explicit non-distribution status. Source custody does
not transfer copyright, relicense code or authorize redistribution.

Public fork changes require the exact separate promotion decision in the
[source recovery handoff](../docs/source-baseline-restore-handoff.md). Repository
Actions are enabled even though their workflow API lists are empty; inherited
workflow execution must be prevented or reviewed before a permitted push.
No source defaults, public source refs, workflows, releases or deployment change
in this checkpoint. FND-07 remains incomplete until required delivery and human
review pass. FND-08/OWN-02 retain compiler/OS/build closure, moving-upstream
immunity and full disconnected rebuild/repair; no such acceptance is inferred.
