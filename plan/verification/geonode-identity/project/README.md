# PR #60 Project publication

[PR #60](https://github.com/aloerch/ambisgis-platform/pull/60) was opened against
`ambisgis/main` from `fnd-02/geonode-identity-integration`, initially at
`103a7544188c9f74f8241fd2b762bea6453e1bc0`. The tested implementation is
`08d1d910552f47d1ab8893c4a7fcd42c0cbacb44`; later changes are documentation
and publication receipts only. The live PR and its final evidence comment identify
the current review head.

The bounded publication helper is the reviewed #59 helper with only the worktree,
branch, base and retained-root constants changed. It uses the pinned existing
read-only snapshot adapter and supported GraphQL operations; it does not rerun the
importer or Project-view setup.

The dry run discovered 72 items. Apply performed exactly two authorized mutations:
add actual PR content `PR_kwDOUhI-d88AAAABEXbEsw` and set only that new item's
Evidence to PR #60 plus FND-02 issue #3. Both mutations were acknowledged, but the
first item-list readback still returned 72 items, so the helper correctly failed
its preservation assertion. That failed receipt is retained. No writes were
replayed. A fresh read-only readback returned **73 items: 66 tasks + seven PRs**;
only #60 matches the saved `is:pr is:open` queue.

[Reconciliation](reconciliation.json) compares the original pre-mutation snapshot
with the fresh readback: all 72 prior item values and archive decisions, all Project
fields/repository links, and every view configuration/order are identical. The
one new item has its correct Evidence link and no copied Task ID, Delivery or
Review gate. FND-02 remains **In progress**. This is supported API evidence, not a
claim of manual UI review. The inherited adapter does not expand assignee/label
values; these fields were not written.

Full paginated exports and mutation/readback journals remain under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-identity/` in
`project-dry-run-01`, `project-apply-01` and `project-readback-02`.
The reconciliation file indexes their exact hashes instead of recopying them.
Additional exact-head readback is recorded with the PR's final evidence comment.
No merge, auto-merge, release, deployment, branch deletion or workflow/secret change
was performed.
