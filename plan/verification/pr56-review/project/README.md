# PR #56 preparation: independent read-only Project audit

Captured 2026-09-20T21:39:28.543196+00:00. All 13 preservation checks passed.
Authenticated owner aloerch (15285626), repository aloerch/ambisgis-platform
(1376927351 / R_kgDOUhI-dw), Project #2 (PVT_kwHOAOk9es4Bj_k-) verified.
Zero remote mutations; no importer, Project changes, repository modifications,
package tests, native reruns, or browser/UI verification were performed.

The complete readback contains 66 unique tasks and four distinct PR items:
70 total, all unarchived. All represented task field values, item identities/archive states,
PR parent Evidence, 24 field definitions, 15 repository links and seven complete
view configurations match the immutable #57 snapshot. PR items do not duplicate
Task ID, Delivery or Review gate values from their parent tasks.
FND-02 remains In progress; GOV-02 remains Merged.

Saved view 7 retains `is:pr is:open`; its currently matching Project membership
is #56 alone. #54, #55 and #57 are owner-merged and remain retained items.
The only item-value difference from #57's snapshot is PR #57 built-in Status
Todo -> Done, associated with aloerch's merge at 2026-09-20T21:32:22Z and commit
8bf1217c8c078c26558da4b3318feda07a9c4ce1. Built-in Status is not product Delivery.
No discrepancy requires a Project write or repeated owner view setup.
Issue assignee/label content is represented by field type in this existing
adapter, not expanded as full issue metadata; unchanged assignment/label values
are therefore not claimed from the baseline comparison. This audit makes no
remote writes to any human field or discussion.

## Pagination evidence

9 supported requests returned HTTP 200. `pagination.json` records 110
connections/pages, all ending with hasNextPage=false: fields, repositories,
basic views, all 70 items (explicit ARCHIVED and NOT_ARCHIVED), 70 nested item
fieldValues, expanded views, and 35 nested view fields/configuration/grouping/
sorting connections. Every connection fit one page in this readback; the audited
adapter follows endCursor whenever hasNextPage is true and rejects duplicate IDs,
nonadvancing cursors, incomplete responses and partial GraphQL errors.
`readback-requests.jsonl` retains request/response bodies without HTTP headers or
credentials; `readback.json` retains the normalized snapshot.

## Immutable baseline (referenced, not copied)

Repository commit: 8bf1217c8c078c26558da4b3318feda07a9c4ce1
Path: plan/verification/pr57-review/project/readback.json
SHA256: 5893ca7e32130960bea596af73260ee505efc54fcfa0dd035b453a5d1c09231e
Capture: 2026-09-20T20:58:14.041994+00:00

The read-only adapter is plan/tools/github_project_api.py at the same commit,
SHA256 2285d2ba5eb367df7f8e641399011bed237d60febb8dc1393f96d653f197cfd9.
The CLI SHA256 is ea857a3f0f7d4276cf5848b236542c5048e2eaa7bdd1b6ddec238f8793e74bff.
The script refuses overwriting prior results and checks the baseline, adapter
and CLI hashes. It never changes Git refs or prior evidence.
