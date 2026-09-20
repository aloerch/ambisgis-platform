# GOV-02 saved-view reconciliation

**Current-state correction (2026-09-20):** Owner `aloerch` merged PR #52 at
`fc77ab978e567ce5d55e3428d1249a3b332da09d` on 2026-09-19T21:54:27Z.
Live GOV-02 Delivery has now been reconciled to **Merged**, with its Evidence
link retained. The earlier In review/Blocked statements below describe the
historical review sequence; their requested owner review has occurred.
Previously accepted settings and the explicit roadmap limitation require no
repeat verification. See [the separate PR queue correction](pr-review-visibility.md)
for the new incremental-review visibility evidence. No Released or product
acceptance claim follows from this governance merge.

GOV-02 is now **In review** in [PR #52](https://github.com/aloerch/ambisgis-platform/pull/52). The owner resolved the review filter and reported that the roadmap has no visible-fields picker. The unsupported instruction to hide Status through that picker is withdrawn; the exact layout limitation is retained for review below. At the initial follow-up readback, live Delivery still read **Blocked**; the later verified review transition is recorded below. No approval, merge or whole-task completion is claimed. FND-02 continues independently.

This reconciliation uses the owner's [initial 2026-09-19 verification](https://github.com/aloerch/ambisgis-platform/issues/9#issuecomment-5744517566), [follow-up at 21:19:59 UTC](https://github.com/aloerch/ambisgis-platform/issues/9#issuecomment-5745381847), and [fresh supported GraphQL readback](../verification/project-view-followup-readback.json) captured at `2026-09-19T21:25:32.834870+00:00`. The [earlier 19:05:54 UTC capture](../verification/project-view-readback.json) is preserved as historical evidence. The agent did not personally inspect the UI. The initial comment's unfilled “Remaining exceptions” placeholder is not additional evidence.

## Identity and scope

- Repository: `aloerch/ambisgis-platform`, database ID `1376927351`; authenticated login `aloerch`.
- Project: [AmbisGIS — Product Development #2](https://github.com/users/aloerch/projects/2), node ID `PVT_kwHOAOk9es4Bj_k-`, public and open.
- Worktree: `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-gov02`; branch `gov-02/saved-view-reconciliation`; separate review [PR #52](https://github.com/aloerch/ambisgis-platform/pull/52).
- Initial base: `a3c2e2e696ea11bdc10c2ad202a240fbd0137f45`, the verified merge of [PR #51](https://github.com/aloerch/ambisgis-platform/pull/51). The review branch subsequently integrates verified `ambisgis/main` commit `12bd2c5c88ab8573add1b483f1d53b4024649b39`, preserving the current Jupyter/FND-02 records; this local branch integration does not merge PR #52 into main.
- Initial reconciliation: read-only queries preserved item values, dates, comments and saved settings. The later deliberate GOV-02 Delivery/Evidence update is recorded separately below. No importer rerun, workflow change, remote merge or release occurred.

## Accepted observations and readback

The [query](../verification/project-view-readback.graphql) reads all six saved views and checks every connection for complete pagination. It uses documented `fields`, `configuration.visibleFields`, `groupByFields`, `verticalGroupByFields` and `sortByFields` plus filters. Live introspection confirms these fields. Roadmap date mappings, slicing and individual board-column visibility are not exposed by this query; attributed owner observations are evidence for UI-only configuration.

| View | Accepted evidence | Reconciliation |
|---|---|---|
| [Product backlog, view 2](https://github.com/users/aloerch/projects/2/views/2) | API confirms table, `-delivery:Cancelled`, Phase grouping, Priority ascending then Task ID ascending, visible Risk/Review gate/Delivery and hidden Status. Owner reports useful dependency fields. | Backlog setup accepted; dependency visibility is attributed to the owner. No additional dependency-display format is imposed. |
| [Execution board, view 3](https://github.com/users/aloerch/projects/2/views/3) | API confirms board, **Delivery as column field**, no horizontal grouping, no saved filter, visible Delivery and hidden Status. Owner reports Column group by field = Delivery and Slice by field = Delivery. | The column requirement is satisfied. Horizontal Group by is a separate optional setting. Slice by = Delivery is accepted owner evidence and is not an added requirement. The API does not establish which individual columns are hidden. |
| [Release roadmap, view 4](https://github.com/users/aloerch/projects/2/views/4) | API confirms roadmap and Phase grouping, with no saved filter, sort or column grouping. The owner reports Start date and Target date mappings and a calendar layout with no fields-selection option. | Date mappings and the UI limitation are attributed owner evidence. API `fields` includes Status while `configuration.visibleFields` is empty; neither proves rendered Status visibility or a derived mapping. No picker operation remains requested. See the authority limitation below. |
| [Review and approvals, view 5](https://github.com/users/aloerch/projects/2/views/5) | Owner and fresh API agree on `delivery:"In review",Blocked review-gate:"Human approval",Security,"Data migration","License/Brand",Release`. API confirms table, visible **Linked pull requests and Evidence**, visible Delivery and hidden Status. | The required gate restriction is resolved. All four required gates are selected; the owner also included Release, an existing review-gate value. Preserve that deliberate additional selection. No filter or visibility reconfiguration is required. |
| [Source and security maintenance, view 6](https://github.com/users/aloerch/projects/2/views/6) | API confirms table, `component:Platform,Governance,"Security/Release" -delivery:Cancelled`, Component grouping, visible Task ID/Title/Delivery/Risk/Review gate/Evidence and hidden Status. | Current custody/build/maintenance view accepted. Sensitive reports remain outside the public Project. |
| [Default View 1](https://github.com/users/aloerch/projects/2/views/1) | API agrees with the owner: Delivery visible and Status hidden. | Resolved; default view preserved. |

GitHub's [board instructions](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout) distinguish the column field from horizontal Group by. Accordingly, `project.json` now uses `column_field: Delivery` for the board; `group_by` retains its horizontal meaning. These are local manifest names, not invented GraphQL inputs. The importer still does not change manual view settings or infer acceptance from view creation.

## Roadmap limitation and remaining review

The owner's follow-up reports: “the view settings do not contain a fields selection option, unlike tables and boards.” This corrects the earlier instruction to pick visible fields and hide Status. GitHub's [current roadmap documentation](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-roadmap-layout) describes date/iteration positioning, grouping, sorting and slicing; it does not document the table/board field-visibility picker. This agrees with the reported UI limitation, but is not an independent inspection of this saved view.

The roadmap remains a Phase/date planning view. Supported readback shows Phase grouping, no filter, no sort and no column grouping; it establishes no Status-driven setting among those fields. It cannot prove every rendered or UI-only setting: saved slicing is not returned, and the `fields`/`configuration.visibleFields` discrepancy does not prove that Status is hidden. This follow-up configures no derived Delivery-to-Status mapping, and the evidence establishes none. Delivery remains the sole delivery authority under chapter 12; no independent Status-maintenance workflow is authorized by this record.

The proposed disposition is **In review with this explicit platform limitation**, under GOV-02's acceptance requirement that UI-only steps be reported rather than claimed completed. The earlier field-picker action is unavailable and is no longer an engineering blocker. PR #52 review must assess the attributed limitation against the authority policy before Verified. This does not silently alter that policy, assert an unperformed hide/mapping action, or infer owner PR approval from a UI observation. If review identifies actual independent use of Status, record that specific use and a supported correction; do not repeat the unavailable picker instruction or reset existing Status values.

No owner needs to repeat the already accepted view settings. The remaining action is to review PR #52's correction, fresh readback and this documented limitation. Verified requires the applicable checks and review; Merged requires an actual approved merge readback. Neither transition has occurred in this follow-up.

## Acceptance and Delivery evidence

- **Dependency-based readiness:** GOV-01's [owner-approved merge](https://github.com/aloerch/ambisgis-platform/issues/8#issuecomment-5740802894) establishes the prerequisite. Its live Delivery is Merged. GOV-02 has a reviewable correction PR and recorded tests; the filter correction and reported roadmap limitation support a deliberate transition to In review.
- **Distinct transitions:** the GOV-01 record documents In review, Verified after tests/owner approval, and Merged after actual merge readback. Fresh readback retains FND-01/GOV-01 Merged, FND-02 In progress and GOV-02 Blocked; the proposed GOV-02 transition is not a claim that it was applied. A bounded merged FND-02 PR does not complete all FND-02 acceptance, and none of these is Released. Cancelled remains a separate Delivery option.
- **Evidence-preserving updates:** the historical [GOV-01 no-op apply](project-live-evidence.md) demonstrated zero mutations and preserved item/issue state. This is historical evidence, not a fresh importer run. The reconciliation itself performs no Project writes.
- **Required views and limitations:** all six named layouts and the supported settings above are evidenced. The remaining roadmap rendering/slicing limits are reported, with owner attribution, rather than represented as completed API checks. In review is the proposed next state for the separate correction PR. Applicable review of this record still precedes Verified, and actual merge precedes Merged. Do not close or mark the task complete from this read-only follow-up.

The retained query is read-only. To refresh it, use the verified local GitHub CLI from `plan/`:

```sh
gh api graphql -F query=@verification/project-view-readback.graphql
```

Check for GraphQL errors, verify the owner/repository/Project identities, and require every `pageInfo.hasNextPage` to be false (otherwise continue pagination). Do not overwrite the dated evidence or treat HTTP success alone as complete readback. The [GraphQL Projects reference](https://docs.github.com/en/graphql/reference/projects) documents these read fields; roadmap UI observations remain attributed to the owner.

## Validation

The fresh follow-up passed **175 package/governance tests with no failures, errors or skips**, plus strict plan/schema validation (15 repositories, 66 tasks, 24 requirements, 65 source references; four schemas/examples) from `plan/`. [Exact commands and outcomes](../verification/project-view-followup-validation.txt), [test output](../verification/project-view-followup-tests.txt) and [schema output](../verification/project-view-followup-schemas.txt) are retained. The [original validation record](../verification/project-view-validation.txt) and [original test output](../verification/project-view-tests.txt) remain unchanged; their corrected initial wrong-directory invocation is historical. No GIS product acceptance or fresh database/native-build result is claimed.

The earlier independent integrator-agent review accepted the original reconciliation with its then-outstanding checks. That historical review is not approval of this follow-up or whole-task acceptance. Fresh package/schema outcomes are retained separately in [the follow-up validation record](../verification/project-view-followup-validation.txt) and [test output](../verification/project-view-followup-tests.txt).

The review branch also integrates current main `12bd2c5c88ab8573add1b483f1d53b4024649b39` in local merge `453eacb9724a477a75642e708b0c20082d612b38`. Post-integration **175 tests and all four schema/example checks passed**; [integration validation](../verification/project-view-integration-validation.txt), [test output](../verification/project-view-integration-tests.txt) and [schema output](../verification/project-view-integration-schemas.txt) are retained. Current-main Jupyter/FND-02 records are preserved; only the GOV-02 paragraphs differ in the two STATUS files. This branch integration is not a remote merge of PR #52.

## Recorded review transition

After the follow-up and current-main integration were tested and pushed, the
integrator verified PR #52 open at `7ace33af6e9b92cc05374de28c996957f584f549`,
existing local Project write authorization, owner/repository/Project/item/field
identities, and the live Blocked value. A deliberate update moved only GOV-02
Delivery to **In review** and its Evidence link to PR #52.
[Mutation receipts and supported readback](../verification/project-view-review-transition.json)
confirm both values. The earlier Blocked captures remain historical evidence.
No saved-view setting, other task state, workflow or importer was changed.

Independent integrator review found no blocker to reviewing this bounded
correction: observations are attributed, unsupported UI behavior is not claimed,
and current-main engineering evidence is preserved. This is engineering review;
the owner's review of the precise limitation still precedes Verified. No PR
merge, issue closure or whole-task acceptance was performed.
