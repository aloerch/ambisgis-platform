# PR #55 — retained Java toolchain and dependency resolution review

**Review only [PR #55](https://github.com/aloerch/ambisgis-platform/pull/55)** in
`aloerch/ambisgis-platform` (repository ID `1376927351`, node `R_kgDOUhI-dw`).
Feature branch: `fnd-02/java-toolchain-resolution`. Target: `ambisgis/main`.
The current exact reviewed head and full tested tree are recorded in the PR's
review summary and final verification receipt. No PR was merged and auto-merge
was not enabled. FND-02 remains **In progress**.

## Prerequisite, ancestry and remaining diff

Live authenticated owner is `aloerch`, ID `15285626`. PR #54 was merged by that
owner on `2026-09-20T20:09:12Z`, merge commit
`8393fc46b9b979b05faa416f5998e0159ecd1e33`, which is verified current main.
Its parents are `fc77ab978e567ce5d55e3428d1249a3b332da09d` and reviewed audit
head `b15a785f350d347c0c2c4ff07ac6e5681c1d9746`. The merge tree equals the
audited head's tree, `58847849100864168a602e70c1aa33dc4c3cc7d0`.
Actual database PR #51, Jupyter PR #53 and GOV-02 PR #52 merge commits are all
ancestors of main. Their evidence and governance corrections are retained.

Normal feature-branch merge `00eb480490942c0a83ce220cfa9fe0a656f9aa54`
has parents `9e1b2e1bca26d00b200a39f58a4a0890d43fca98` and actual main
`8393fc46b9b979b05faa416f5998e0159ecd1e33`. It had no conflicts. Its complete
tree remained exactly `a0f44cb1d9526de25d934a9123ab5a62007189a4`, identical
to #55's previous head. Before review corrections, the diff against new main
was byte-identical to the old diff against #54: 46 files, 21,288 insertions and
10 deletions. The patch SHA256 is
`b3468f6b87cde5566d690597b1905673f7d22cc43f0c4aa2d00a4442bad7548f`.
That proves the base transition neither replayed the audit nor omitted the
remaining resolution checkpoint. Cited commits were preserved without reset,
rebase or force-push. #55 is explicitly retargeted only after the actual #54 merge.

The intended implementation is confined to Java toolchain acquisition/verification,
retained-origin Maven input resolution, file-mirror replay, schema-resource
validation and source/notice inventory. ADR 003, receipts, retained failures and
status/handoff documents explain that scope. This session adds one narrow POM
parser correction and review/Project evidence. It does not pull #57's source
recovery/native-probe implementation or #56's governance changes into #55.

The user-selected review order is **#54 → #55 → #57 → #56**. #56 is technically
independent but last in that order. Live preflight found #54 merged and #55/#57/#56
open; neither #54 nor #55 had review requests, submitted reviews, comments or
unresolved review threads. Comments, reviews, threads and requests were enumerated
to their terminal pages, with the current FND-02 issue discussion also retained.
Later #56 currently reports `CONFLICTING / DIRTY` against main; it remains
unprepared for its later turn. This does not block the selected #55 review.
This engineering assessment is not human approval.

## Material review finding and correction

Independent review found that `resolution_inventory.pom_licenses` rejected
ASCII DTD/entity markers before calling an encoding-aware XML parser. UTF-16
representations of the same document bypassed that refusal and expanded a benign
internal entity. The original UTF-8 regression did not cover this encoding case.
The correction rejects actual declarations with encoding-aware parsing before
ElementTree interprets the POM. The 31 focused tests pass, including three new regressions covering actual
DTD declarations across six encodings, ordinary non-ASCII license metadata, and
explicit inventory-gap propagation. The original failing run is retained. No dependency/version/profile selection
or retained input was changed.

A read-only impact scan found no UTF-16 encoding signature in any of the **2,824
retained POM artifact records**. The actual full source/notice inventory is rerun
with the corrected parser and compared with the original retained report, rather
than inferring safety from synthetic fixtures alone. Its actual exit **2** denotes the original **64 missing source classifiers**,
not an integrity failure. All **10,802 records /10,792 blobs** verified. After
normalizing only the report timestamp and fresh notice-output paths, every
semantic field equals the original report, including all 2,824 POM/license rows. Reproducer,
correction, actual checks and comparison results are linked from the verification
receipts. No other material finding was identified in the reviewed toolchain,
proxy, schema validation, custody/replay boundaries or acceptance claims.

## Verification and deliberate omissions

**143 Java tooling tests, 175 package tests and all four strict schema/example
checks passed with no failures/errors/skips.** Actual output is retained in
`plan/verification/pr55-review/`. Raw discussion, Project-operation logs, original
regression failures and the full real inventory are additionally retained under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-resolution/review-pr55-01`. The tested Java implementation subtree is
`5edbdebeedf57771301c5048171cb85fa1f03b83`. The final published review summary
and final-check receipt record the full Git tree/head; ancestry, commands, exits
and hashes are retained alongside the committed check logs. Package checks use the existing verified validation venv from `plan/`.
They are not GIS product tests.

Read-only custody verification again passed for **34,118 files /
1,682,220,066 bytes**, manifest SHA256
`2a9cc548d2d7709e39c6bef547e9befa7176a897fa6859a8bb7bae2ed14c7f07`.
Installed toolchain verification passed for 342 files, 208 symlinks and 103
directories against the retained Temurin 17.0.20.1+1/Maven 3.9.16 archives.
The existing signature-trust and toolchain-bootstrap limitations remain open.

No Java compilation, native/runtime suite, database/Jupyter test or complete
Maven model/dependency replay was rerun for this review. The base merge changed
no files; the only implementation correction affects POM license inventory and
is exercised by focused tests plus a full real inventory rerun. Maven execution,
profile/version inputs, source-resource rules and dependency graphs are unchanged.
Historical successful replays of the 157-module candidate remain their original
receipts, not new test results. Native results from later #57 remain outside this
PR's acceptance scope.

All 19 existing platform worktrees were initially clean, and no workspace Java
build process was running. Only the selected feature branch and a separate local
parser-review worktree were used for repository edits; user files, archives and
failed-run evidence were preserved. The main checkout itself was not advanced.

## Authorized Project correction

[Complete readback](../verification/pr55-review/project/README.md) records only
two additions and two Evidence assignments: existing #56 → parent issue #9 and
existing #57 → parent issue #3. Their content IDs were absent in both archived
and unarchived enumeration before creation. No existing archive decision was
reversed. #54/#55 were not duplicated; no parent Task ID, Delivery or Review gate
was copied. GitHub's preexisting/default built-in Status is not the product
Delivery authority and was not assigned by this operation.

Project #2 now contains **66 planned tasks + four PR items =70 items**, all
unarchived. Saved `is:pr is:open` membership is #55/#56/#57; merged #54 remains
retained and is excluded by the saved open filter. All 68 preexisting item field
values/archive states, seven view configurations, 24 fields and repository links
compare unchanged. FND-02 remains In progress, GOV-02 remains Merged. No full
importer run, workflow, secret, unrelated repository change or later-PR preparation
occurred. Membership is verified by complete content/filter readback, not claimed
browser inspection.

## Owner decision and remaining limits

The requested decision is whether to accept **this bounded custody/resolution
checkpoint**, including its narrow parser correction, for a separate GitHub merge
into `ambisgis/main`. GitHub mergeability alone is not the review conclusion;
ancestry/diff checks, actual tests, real custody/inventory verification and the
independent engineering assessment support the report.

Acceptance does not approve full source-to-binary or transitive source closure,
file-level licensing/brand, security or toolchain trust, MapFish/GeoFence runtime
compatibility, schema repackaging/rights, logging mediation, OAuth/bootstrap
configuration, canonical product baselines, release or FND-02 completion. The
64-classifier gap count is this checkpoint's historical boundary; later source
accounting/native results in #57 require their own review. The package remains a
plan plus bounded implementation evidence, not a completed GIS distribution.

After the owner actually merges #55, the next requested review preparation is
#57. Verify the actual merged base, integrate/retarget normally and test its
remaining diff then. #57 and #56 are not prepared or implicitly approved here.
