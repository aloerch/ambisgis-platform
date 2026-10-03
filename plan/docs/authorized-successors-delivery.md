# FND-07 authorized source delivery

The owner-supplied [standing delegation](../authorizations/2026-10-02-standing-delegation.md), section 4, authorized the two exact successors prepared in PR #71 and delegated acceptance against the original criteria. This record supersedes the old handoff's pending publication decision; the old receipts and their original meaning are unchanged.

All four absent destinations were created using the reviewed helper at platform commit `0de2945ee1d29f00af19229720c43e3071b9571b`, based on PR #72 merge `8c3612dd3e4ee992d930f1417798b66f467784e9`. The helper defaults to read-only, rejects collisions, journals attempts before writes and rechecks all refs and settings. Its upload uses a server-enforced absent-ref lease; it cannot update an existing ref. Thirteen regression tests include an actual local Git ancestor-race refusal and preservation of newly created refs between operations.

| Owned repository | Exact published source | Created refs |
|---|---|---|
| `aloerch/ambisgis-geotools` (1376927869) | `3363c3d4ae8adfe3ed2024c27f92ec63855093be` | `ambisgis/review/fnd-07-notices-v1`, `ambisgis/main` |
| `aloerch/ambisgis-qgis` (1376927721) | `86af40542b219b0da6df1a43914413443330c0c0` | `ambisgis/review/fnd-07-publication-snapshot-v1`, `ambisgis/main` |

[Publication evidence](../verification/authorized-successors/publication.json) records four source mutation attempts, no settings mutation and successful final readback. The [unchanged replay](../verification/authorized-successors/successor-replay-verification.json) found four already-exact destinations and made **zero source/settings mutation attempts**. Original refs, defaults and disabled Actions were preserved throughout.

A separate-context reviewer independently fetched each review ref through its owned public HTTPS remote into a fresh isolated object store. [Recovery evidence](../verification/authorized-successors/successor-recovery-summary.json) verifies complete trees, identities and notices. GeoTools retains all 10,404 expected history commits and its direct accepted-base parent. QGIS has exactly one parentless commit and 32,995 stored/reachable objects, with no forbidden objects; all 1,130 exclusions, 265 ColorBrewer palettes and 4,371 selected resource entries pass. This certifies the delivered snapshot boundary only; it neither purges nor certifies other fork refs or GitHub network content.

The [other nine canonical refs](../verification/authorized-successors/prior-nine-current.json) were freshly checked against the selected owned repository IDs and exact commits/trees. Their unchanged full-history, asset, notice and submodule evidence is explicitly reused from PRs #69–71, with hashes checked. Those builds were not repeated for this source-delivery task.

## Unchanged task criteria

| Original FND-07 criterion | Actual evidence and limits |
|---|---|
| Every selected core component resolves to an owned source revision and retained baseline. | All eleven owned canonical refs resolve; retained original bundles/assets and exact successor bundles remain available. Fresh recovery of the two changed roots and hash-bound reuse of unchanged eleven-root custody plus prior nine deliveries satisfy T-OWN-01 source custody. |
| No source transfer implies a copyright reassignment or blanket relicensing. | Existing licenses/notices remain; GeoTools adds the exact dated modification notices. QGIS follows the owner's exact exclusion/snapshot decision. No blanket rights waiver, trademark clearance or production distribution is asserted. |
| All required additional assets are enumerated; nulls are explicit blockers, not fabricated hashes. | Accepted source/resource/vendor/gitlink/LFS inventory remains unchanged. The sole MapStore submodule has its selected owned child; selected core LFS pointers are absent. Successor sidecars enumerate their exact additional source/resource changes and retained bundle identities. No unresolved value was replaced with an invented identity. Full compiler/OS/build-input closure remains FND-08 and complete disconnected repair remains OWN-02. |

The implementation/source evidence now satisfies these source-custody criteria, subject to final separate-context evidence review and normal protected merge. Delivery remains In review until those checks finish; the integrator will record Verified → Merged and close issue #6 only with the exact resulting PR/merge evidence. FND-02 stays accepted/Merged. FND-08 then becomes ready without another owner authorization.

## Validation and next implementation

At the executed helper head, 457 package tests passed without failures, errors or skips and all four schemas validated. The earlier prepublication record is retained as historical evidence. Final PR-head tests, required CI and the independently reviewed gate from the live base must pass before merge. Package checks are not GIS tests.

No GeoTools or QGIS binary was relabeled or rebuilt in this increment. FND-08 must build repaired sources under their new identities, retain complete selected build inputs and demonstrate moving-upstream immunity. FND-03 identity/policy and FND-04 branch prototypes are independently dependency-ready and running real component tests in separate worktrees. The release, Windows/Linux desktop, security, installation, recovery and human-only acceptance gates remain open in the [requirements matrix](delivery-requirements-matrix.md).

The [workflow execution record](../verification/standing-delegation/workflow-execution.json) records PR #72's normal protected merge, required checks, narrowly scoped settings and smoke results. A tracking command completed its writes but its final preservation assertion detected GitHub's existing automatic Status change after GOV-02 closure. Fresh read-only reconciliation confirmed every intended mutation and the sole automatic Todo → Done change; no mutation was retried. The integration runtime retained that failed checkpoint and requires its exact run ID to acknowledge reconciliation before another write. Cross-turn native-goal continuation remains unobserved at this checkpoint.
