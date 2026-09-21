# PR #61 Project publication

[PR #61](https://github.com/aloerch/ambisgis-platform/pull/61) was published from
`fnd-02/geonode-role-propagation` at head
`7ebc480fae0dedc70271ed17756387f5fefedd07`, with frozen implementation
`d935fb48a7e0721b1e25f67eccfe3ed836c890fc`. Subsequent publication documentation
does not change the executed source trees or artifacts. The final review head is
also pinned in the FND-02 issue evidence comment after the documentation push.

The reviewed bounded helper first passed a read-only dry run, then made exactly
two authorized mutations: add actual PR content `PR_kwDOUhI-d88AAAABEXx1fA`, and
set that new item's Evidence to the PR and FND-02 issue URLs. The item is
`PVTI_lAHOAOk9es4Bj_k-zg75IZU` in Project `PVT_kwHOAOk9es4Bj_k-`.
No importer, task transition or Project/view setup was run. An initial invocation
with an abbreviated head was rejected by the exact-head guard before snapshots
or mutations; the successful invocation used the complete hash.

Complete paginated readback passed all preservation checks in [outcome.json](outcome.json):
**73 → 74 items**, comprising **66 task issues + eight PRs**, all unarchived.
All 73 previous items, represented values and archive decisions, 24 fields,
15 repository links, seven views and their configurations/order stayed unchanged.
FND-02 remains **In progress**. The new PR carries no Task ID, Delivery or Review gate.
Only #61 is OPEN; #54–#60 are MERGED. Saved filter `is:pr is:open` is unchanged.
This is API evidence, not a claim of browser/UI verification. The inherited adapter
does not expand assignee/label values; no such fields were written.

The [retained manifest](retained-manifest.json) binds the full before/after
snapshots, pagination, mutation journal, helper provenance and summaries under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation`.
The compact public outcome contains identities, links and verification results;
raw runtime configuration and credentials are not part of this publication.

Final verification uses the same helper **without `--apply`**, the exact pushed
head and a fresh `project-final-readback-01` output. Its retained result and the
issue comment record that final head without replaying mutations. The owner must
review this new security-sensitive PR before merging; this checkpoint performs
no merge, auto-merge, deployment or release.
