# Incremental PR review visibility

The existing [PR review queue, view 7](https://github.com/users/aloerch/projects/2/views/7)
now contains the two existing open PRs #54/#55 as separate unarchived Project
items. FND-02 stays **In progress** with all of its fields unchanged. The count
is **66 planned task issues + 2 PR items = 68 Project items**, not 68 tasks.
GOV-02 is **Merged** after the actual owner merge of PR #52; it is not Released.

## Verified identity and exact changes

Readback on 2026-09-20 verified authenticated `aloerch` (ID `15285626`),
`aloerch/ambisgis-platform` (database ID `1376927351`, node `R_kgDOUhI-dw`),
and public/open Project #2 (`PVT_kwHOAOk9es4Bj_k-`). Work is isolated on
`gov-02/pr-review-visibility`, based on verified main commit
`fc77ab978e567ce5d55e3428d1249a3b332da09d`, in
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-pr-review`.
The retained GitHub CLI binary SHA256 is
`ea857a3f0f7d4276cf5848b236542c5048e2eaa7bdd1b6ddec238f8793e74bff`.

Complete preflight found seven views, 24 fields and 66 unarchived task items.
The user-created PR queue already existed before this work; it was verified
by Project/view ID, name, table layout and actual saved filter **`is:pr is:open`**.
The request's literal `is is` is treated as the existing PR/open qualifiers,
not a new free-text filter. GitHub documents both qualifiers in its
[filter reference](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects).
No parent Delivery or Review gate restriction was present or added.

| PR | Actual content ID | Added Project item ID |
|---|---|---|
| [#54](https://github.com/aloerch/ambisgis-platform/pull/54) | `PR_kwDOUhI-d88AAAABEQiDOg` | `PVTI_lAHOAOk9es4Bj_k-zg72Eq8` |
| [#55](https://github.com/aloerch/ambisgis-platform/pull/55) | `PR_kwDOUhI-d88AAAABEQ97wg` | `PVTI_lAHOAOk9es4Bj_k-zg72Erw` |

Each PR was absent by actual content ID before `addProjectV2ItemById`.
Both are now unarchived; neither has Task ID, Delivery or Review gate values.
Their Evidence values link their own PR and the existing parent issue #3.
The task's own Evidence remains PR #55. No task or PR was duplicated.

The queue ID is `PVTV_lAHOAOk9es4Bj_k-zgLu0DU`.
Supported `updateProjectV2View` configuration added **Repository** and
**Evidence** to its existing columns; existing columns were retained:
Title, Assignees, Linked pull requests, Sub-issues progress, Delivery,
Task ID and Review gate. Field selection does not restrict membership.
The live schema/Project provides **Linked pull requests**, not a selectable
**Linked issues** field. No nonexistent field was fabricated; the explicit
parent issue URL in Evidence provides that link. Existing Task ID/Delivery/
Review gate columns remain empty for the PR items. No UI step is pending.

The six earlier views are byte-for-byte identical in configuration readback,
including the accepted `Review and approvals` filter:

```text
delivery:"In review",Blocked review-gate:"Human approval",Security,"Data migration","License/Brand",Release
```

## Readback and membership limits

[Before](../verification/pr-review-before.json),
[mutation receipts](../verification/pr-review-mutations.json), and
[after](../verification/pr-review-after.json) preserve actual IDs and results.
The existing `GitHubProjectAPI.project()` / `items()` readers paginate fields,
views, repository links, items **including ARCHIVED and NOT_ARCHIVED**, and
nested item values to their terminal page. The additional retained saved-view
query checks every nested connection's `hasNextPage` is false; all fit in one
page on this capture. All 68 items are unarchived, and exactly 66 unique Task
IDs remain. All original item values/archive states are unchanged except the
one evidence-based GOV-02 Delivery reconciliation below.

The supported `ProjectV2View` schema has no items connection. Membership is
therefore established from complete Project content enumeration, actual
PullRequest type/open states and the read-back saved `is:pr is:open` filter,
not a claim of browser inspection. The only PR contents at capture are #54
and #55. Subsequent head changes do not change content/item identity.

Read-only introspection initially exceeded GitHub's two-use `inputFields`
limit; splitting that query resolved it. Passing a leading-comment GraphQL
file to the adapter's strict classifier was also rejected; removing the file
comments resolved that local read failure. No mutation followed either failed
read, and no unsupported save operation was assumed.

## GOV-02 reconciliation

The owner [confirmed the saved review filter and roadmap UI limitation](https://github.com/aloerch/ambisgis-platform/issues/9#issuecomment-5745381847)
before merging [PR #52](https://github.com/aloerch/ambisgis-platform/pull/52)
on 2026-09-19T21:54:27Z. Live `mergedBy.login` is `aloerch`, merge commit is
`fc77ab978e567ce5d55e3428d1249a3b332da09d`, base is `ambisgis/main`, and
reviewed branch head was `e19bc4960866d89c749e1d2d68427dd586130d2f`.
The merged correction retained 175 passing package tests/four schema checks
and the exact roadmap limitation. This supplies the previously outstanding
owner decision; it does not require another view setup or PR #52 review.

Live GOV-02 still read In review, so only its Delivery was reconciled to
**Merged**, preserving Evidence = PR #52 and every other field. This records
an already completed approval/merge event rather than manufacturing a new
Verified transition. The issue remains open; its managed body/checklists and
human discussion were preserved. The historical reconciliation document now
has a dated current-state note. No task is marked Released and no full-product,
license, security or FND-02 acceptance is inferred.

## Adding future relevant PRs

Use the existing authorized local CLI/API; no workflow or secret is needed.
First verify owner, approved repository ID, Project ID and the actual PR node
ID. Enumerate Project items with both archive states and complete pagination.
Match by `content.id`, never title or the parent Task ID. If present, preserve
that item and its archive state; an archived review item needs an explicit
inspection/decision before restoration. If absent, use the existing
`GitHubProjectAPI.add_item(project_id, pr_node_id)` operation, or the documented
CLI equivalent with the already verified PR URL:

```sh
gh project item-add 2 --owner aloerch --url "$VERIFIED_PR_URL" --format json
```

After an uncertain response, re-read by content ID before any retry. Read back
the returned item; add an Evidence link with the existing field when useful.
Leave Task ID and parent-task planning/progress fields unset. Confirm that the
saved queue still filters `is:pr is:open` and that the PR is open/unarchived.
Adding relevant future items still requires task/session authorization; this
run added only the explicitly authorized #54/#55.

Do **not** rerun the full importer merely to add a PR. The queue is an extra
manual view outside the seed's five required views; no manifest/receipt
adoption is needed. The existing importer reconciles only its 66 task issues
and preserves extra items/views. A targeted regression now exercises dry-run
and apply with two extra PR items (one archived) and this queue: zero mutations,
66 verified tasks, 68 items, unchanged PR values/archive states/view filter,
and no duplicate task identity. These are local fake-API tests, not a fresh
live importer run.

## Review boundary and validation

This is a separate governance change. It does not modify Java engineering,
merge any PR, enable workflows, install secrets or reset progress. The owner
can review the tracking correction independently of #54/#55; any decision
blocks its merge only, not ongoing engineering. Queue setup itself requires
**no owner UI decision or repeated GOV-02 setting verification**.

Current package and strict schema outcomes are recorded in
[validation](../verification/pr-review-validation.txt). Database/Jupyter native
checks and Java compilation/runtime acceptance are not part of this change.
