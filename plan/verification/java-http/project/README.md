# Phase B: postmerge Project and prerequisite readback

Captured **2026-09-20T22:00:42.942476Z** before the new engineering PR exists.
Authenticated owner `aloerch` (`15285626`), repository `aloerch/ambisgis-platform`
(`1376927351` / `R_kgDOUhI-dw`) and Project #2
(`PVT_kwHOAOk9es4Bj_k-`) were verified through supported read-only APIs.
No Project mutation, importer run, archive change or repeated UI setup occurred.

## Phase selection

**Phase B is authorized and its prerequisite merges are verified.** PRs
#54/#55/#57/#56 were merged by `aloerch`; every actual merge is an ancestor of
integration commit `a9ec191658be027b40118fd35e145729202fe55d`.
PR #56 merged the prepared head `35d84b5fe80c246e90636ddf8ee5855b94460452`
with the exact reviewed tree `c792696b68a235dc1d21260858b81fe6e4beb5f6`.
Phase A has no remaining preparation action. This does not establish acceptance
of the new engineering slice or completion of FND-02.

## Preserved state and explicit reconciliation

The complete readback contains **66 unique tasks + four retained merged PR items
= 70 items**, all unarchived. All represented task values, item identities,
archive decisions and PR parent Evidence match the immutable Phase A baseline.
FND-02 remains **In progress** and GOV-02 remains **Merged**. The saved PR queue
filter is `is:pr is:open`; its matching membership is empty at this capture.
All 24 field definitions, 15 repository links and seven views are retained.

The initial strict comparison exited **1**, correctly reporting a changed view:
Product backlog/view 2 now places **Delivery fourth instead of fourteenth** in
its visible fields. Its recorded `updatedAt` changed to `2026-09-20T21:48:59Z`.
Exact comparison confirms that this column reorder and timestamp are the only
view differences. Filters, grouping, sorting, available fields and every other
view value are unchanged. The audit cannot identify who made that change.
The observed configuration is preserved; no corrective write or owner UI action
is needed. This discrepancy does not block engineering.

The sole item-value change is #56's coarse built-in Status **Todo → Done** after
its merge. Product Delivery and all other represented item values are unchanged.
The original unsuccessful strict-comparison receipt remains intact. The separate
[reconciliation](reconciliation.json) records the exact differences and the
successful prerequisite checks; it does not relabel the original exit as success.

## Evidence and limits

Nine read requests covered 110 connections/pages, including both archive states
and nested item/view fields, visible fields, grouping and sorting. All terminal
`hasNextPage` values are false. The adapter follows pagination and rejects partial
GraphQL errors, duplicate identities and nonadvancing cursors.

Raw snapshots, sanitized request/response bodies, pagination, the executed script,
initial outcome and reconciliation are retained outside Git at:

`/home/revelberry/Projects/AmbisGIS/source-archives/java-http-auth/project-before/`

[The manifest](raw-manifest.json) records their exact sizes/hashes. The unchanged
Phase A baseline is referenced by path/hash, not copied. The current readback
SHA256 is `dd75e6b79f60a333230313babaf66fcb3ca4377339ca8b84c4cf7cb79852c9e3`.
This is API readback; no browser inspection is claimed. The inherited adapter
represents assignee/label field types without expanding all values, so their
expanded-value equality is not claimed. No audit write touched those values.
No package, Java or native tests ran as part of this readback.

The retained [audit script](read-only-audit.py) checks exact owner/repository/CLI/
adapter/baseline identities, refuses mutation requests and existing output
paths, and requires the captured integration head/branch. It is a reproducible
capture of this stage, not a live-state reset or general importer. A future
post-publication audit must use the new PR identity/current head and compare
against this capture while preserving the observed view order.

Executed command:

```sh
python3 plan/verification/java-http/project/read-only-audit.py \
  --repository /home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-http \
  --gh /tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh \
  --output /home/revelberry/Projects/AmbisGIS/source-archives/java-http-auth/project-before
```

Verify tool availability and choose a new output directory for any repeat.


## Publication snapshot helper

[`snapshot.py`](snapshot.py) performs the later readback without requiring the
original integration HEAD. It requires the exact Phase B worktree/branch,
approved origin, reviewed CLI hash, adapter identity and integration ancestry.
Its `--output` must be a fresh directory under the Phase B source archive and
outside every Git worktree. No mutation operation is available.

Provide `--repository`, `--gh`, `--ghhash` and `--output`. After publication,
add `--expected-pr-number` with the actual new PR number. The expected PR must
match the current local HEAD, own repository/author, Phase B branch and
`ambisgis/main` base. The fully paginated snapshot must contain exactly the 70
prior items plus that single unarchived PR, whose Evidence links the PR and its
FND-02 parent issue #3. Existing task fields and acceptance states stay intact.

Comparison uses this reconciled `project-before` capture, including the human
Delivery column order. Any other change is reported as a failed check, retained
for review and never reset. Without an expected PR, the comparator expects the
unchanged 70-item baseline. Raw snapshots, pagination, request/response bodies,
comparison and executed script are retained in the new output directory.
Seven offline comparator/transport tests pass; no live call was made while
preparing this helper. Their evidence is in `../reviews/project-snapshot-helper-tests.*`.
