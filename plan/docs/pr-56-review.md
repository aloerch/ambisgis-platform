# PR #56 preparation and continuation handoff

**Phase A only.** Review [PR #56](https://github.com/aloerch/ambisgis-platform/pull/56)
on `gov-02/pr-review-visibility` for the tracking correction, its preservation
regression and normal integration with main. The owner decides whether to accept
this bounded change and merge it separately. No repeated view setup is needed.
This run ends after preparation; Phase B requires the owner's actual #56 merge
and a rerun of the continuation request. This is a request-specific sequencing
gate, not a claim that governance code technically blocks Java development.

## Verified base and integration

Repository `aloerch/ambisgis-platform`, ID `1376927351`, node `R_kgDOUhI-dw`;
authenticated owner `aloerch`, ID `15285626`. Existing worktree:
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-pr-review`.

Live owner merges, all verified in actual integration ancestry:

| PR | Merge commit |
|---|---|
| #54 | `8393fc46b9b979b05faa416f5998e0159ecd1e33` |
| #55 | `bb3680802d7f7d5c500180ec12e66d32d81d0aa0` |
| #57 | `8bf1217c8c078c26558da4b3318feda07a9c4ce1` |

#57 was merged by `aloerch` on 2026-09-20T21:32:22Z from reviewed head
`bfcec2dfc1470b5a159cb46a2bc42140c742203a`. Its merge tree exactly equals the
reviewed `7bb7ce83f8bfc900a707de8524b2efafb4a74f16`. Current base is that #57
merge. No unexpected head or closed-but-unmerged prerequisite was adopted.

Normal merge `7b9b334fcac40e19291c96a4e009584c1b00b944` preserves two parents:
original #56 head `28c9d79757b98bdedd44b5d7486835f9e4b71e63` and actual main
`8bf1217c8c078c26558da4b3318feda07a9c4ce1`. Only root/plan STATUS conflicted;
paragraph reconciliation retains the governance correction and newer Java,
database and Jupyter evidence. No reset, rebase, force-push or whole-side conflict
acceptance occurred. Local `ambisgis/main` was stale; the verified fetched remote
integration ref was used without altering the main worktree.

Java, database and Jupyter implementation trees and all inherited historical
receipts are unchanged from main. Java subtree remains
`d6ca199d12cb0e963748b5a6a58a8cca0e3c72dd`: both encoding-aware POM guards/tests,
source-verification failure receipt fix, GDAL staging and compatibility recipes
are retained. The original #56 extra-PR preservation test is byte-identical to
its pre-integration version. The only change to existing implementation/test paths against main is that
25-line regression; importer production behavior is unchanged. The fresh
read-only Project audit script is retained verification machinery. Historical
68-item snapshots and unsuccessful commands remain dated evidence.

[Identity/ancestry/preservation records](../verification/pr56-review/README.md)
retain exact observations. The published PR summary and persistent
`final-checks.json` identify the final head and full Git tree after the evidence
commit, avoiding a self-referential commit hash inside its own tree.

## Current Project state

Complete supported readback at 2026-09-20T21:39:28Z found **66 planned tasks +
four PR items = 70**, all unarchived. The saved `is:pr is:open` queue matches
**#56 only**; #54/#55/#57 remain retained merged items. All represented task
values, item identities/archive decisions, parent Evidence, seven view
configurations, 24 field definitions and fifteen repository links match the
immutable #57 snapshot. The only observed item-value difference is #57's
built-in Status Todo → Done following its owner merge. Product Delivery remains
**FND-02 In progress / GOV-02 Merged**.

Nine read requests completed 110 connections/pages, including both archive
states and nested field/view configuration connections; all terminal
`hasNextPage` values were false. Membership follows complete PR content/state
and the saved filter; no browser inspection is claimed. The existing adapter
represents assignee/label field types without their full values, so this baseline
comparison does not prove equality of expanded assignment/label metadata.
Nothing in this run writes those fields or human discussion content.

[Compact independent audit](../verification/pr56-review/project/README.md)
references the old immutable snapshot and hashes fresh raw captures retained
outside Git. Zero Project mutations, no importer run, no duplicate items or
Task IDs, no archive restoration, and no view/UI setup replay were needed.

## Validation and limits

Fresh integrated checks: **218 Java tooling tests and 176 package tests passed**,
zero failures/errors/skips. The package suite includes the active/archived PR
and manual-view preservation regression. Strict schema results and exact-final
package verification are recorded with commands, working directories and hashes
in the linked receipts. Use the existing verified validation environment;
`requirements-validation.txt` names the schema dependency.

No Java compilation/native test, database native/harness suite, Jupyter
native/runtime probe or HTTP/OAuth experiment ran for this governance preparation.
The native numbers in earlier reports remain historical. Whole incoming-history
whitespace checking reports unchanged raw failed-test/CRLF log lines; its output
is preserved in the persistent evidence directory. Checking the actual scoped
#56 diff against main passes; original log bytes were not normalized.

The default shell sandbox failed before execution because it could not create
its namespace. Approved escalated commands were used for local tooling and
GitHub access; this does not establish runtime network isolation. No new host
isolation experiment, service, privileged installation or security-setting change
was needed in Phase A.

The independent engineering review and its final document check are retained
with the receipts. That review is distinct from owner acceptance. Preflight
review requests, threads, reviews and PR conversations all reached terminal
pages with none outstanding. GitHub check/mergeability state is read back after
push; local tests do not imply hosted CI.

## Resume and remaining acceptance

Inspect the final PR head/tree, normal merge, new preservation regression,
current-vs-historical tracking notes, and verification receipts. Accept or request
specific changes to #56. No agent merge, auto-merge, branch deletion, source-fork
default change, workflow, secret, deployment or release is authorized.

After the owner merges #56, rerun the continuation request. Recover current
state; verify #54/#55/#57/#56 in actual main ancestry, then create a separate
Phase B branch/worktree from updated main. Do not reuse a merged checkpoint
branch. The next bounded engineering action is controlled HTTP/XML/MapFish
fixtures, combined logging/OAuth behavior, and relevant source dispositions.

Unchanged gaps: 48 structural dispositions are not reproducible source builds;
12 unresolved/four partial cases remain. Broader XML retains one error/four skips;
MapFish retains 17 errored identities/six skips. JavaCSV Linux-default failures,
proprietary fixture skips, schema rights/repackaging, combined logging/OAuth,
host/toolchain/source closure and final license/security gates remain explicit.
FND-02, FND-07/FND-08, P1/P6 and release acceptance are separate.

To recheck this prepared branch using the verified validation environment:

```sh
cd /home/revelberry/Projects/AmbisGIS/ambisgis-platform-pr-review
/tmp/ambisgis-validation-venv/bin/python3 -m unittest discover -s build-support/java -p 'test_*.py' -v
cd plan
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 -m unittest discover -s tests -v
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 tools/validate_package.py --require-schemas
```

Verify tool availability before reuse. Fresh raw records and final head receipt:
`/home/revelberry/Projects/AmbisGIS/source-archives/pr-review-visibility/preparation-20260920-01/`.
No task-owned process remains running after these checks.
