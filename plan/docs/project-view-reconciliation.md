# GOV-02 saved-view reconciliation

GOV-02 remains **Blocked on two specific saved-view checks**: the Review and approvals filter lacks its Review gate restriction, and the roadmap's built-in Status authority is unconfirmed. The owner's other observations are accepted and supported readback confirms most of them. FND-02 continues independently; PR #51 merged only its database development checkpoint.

This reconciliation uses the owner's [2026-09-19 verification comment](https://github.com/aloerch/ambisgis-platform/issues/9#issuecomment-5744517566) and the [supported GraphQL readback](../verification/project-view-readback.json) captured at `2026-09-19T19:05:54.783974+00:00`. The agent did not personally inspect the UI. The comment's unfilled “Remaining exceptions” placeholder is not treated as additional evidence.

## Identity and scope

- Repository: `aloerch/ambisgis-platform`, database ID `1376927351`; authenticated login `aloerch`.
- Project: [AmbisGIS — Product Development #2](https://github.com/users/aloerch/projects/2), node ID `PVT_kwHOAOk9es4Bj_k-`, public and open.
- Worktree: `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-gov02`; branch `gov-02/saved-view-reconciliation`.
- Base: `a3c2e2e696ea11bdc10c2ad202a240fbd0137f45`, the verified merge of [PR #51](https://github.com/aloerch/ambisgis-platform/pull/51) into `ambisgis/main`.
- Project operations: read-only queries. Existing item values, dates, comments and saved settings were preserved. No importer rerun, workflow change, merge or release occurred in this reconciliation.

## Accepted observations and readback

The [query](../verification/project-view-readback.graphql) reads all six saved views and checks every connection for complete pagination. It uses documented `fields`, `configuration.visibleFields`, `groupByFields`, `verticalGroupByFields` and `sortByFields` plus filters. Live introspection confirms these fields. Roadmap date mappings, slicing and individual board-column visibility are not exposed by this query; attributed owner observations are evidence for UI-only configuration.

| View | Accepted evidence | Reconciliation |
|---|---|---|
| [Product backlog, view 2](https://github.com/users/aloerch/projects/2/views/2) | API confirms table, `-delivery:Cancelled`, Phase grouping, Priority ascending then Task ID ascending, visible Risk/Review gate/Delivery and hidden Status. Owner reports useful dependency fields. | Backlog setup accepted; dependency visibility is attributed to the owner. No additional dependency-display format is imposed. |
| [Execution board, view 3](https://github.com/users/aloerch/projects/2/views/3) | API confirms board, **Delivery as column field**, no horizontal grouping, no saved filter, visible Delivery and hidden Status. Owner reports Column group by field = Delivery and Slice by field = Delivery. | The column requirement is satisfied. Horizontal Group by is a separate optional setting. Slice by = Delivery is accepted owner evidence and is not an added requirement. The API does not establish which individual columns are hidden. |
| [Release roadmap, view 4](https://github.com/users/aloerch/projects/2/views/4) | API confirms roadmap and Phase grouping. Owner reports Start date and Target date mappings. | Date mappings accepted as owner evidence; Phase is an explicitly allowed grouping. API `fields` includes Status while `configuration.visibleFields` is empty; this discrepancy does not prove the rendered UI hides or uses Status. Only that authority check remains. |
| [Review and approvals, view 5](https://github.com/users/aloerch/projects/2/views/5) | API confirms table, `delivery:"In review",Blocked`, visible **Linked pull requests and Evidence**, visible Delivery and hidden Status. | PR/Evidence visibility is verified and needs no further owner confirmation. The required Review gate restriction is absent. |
| [Source and security maintenance, view 6](https://github.com/users/aloerch/projects/2/views/6) | API confirms table, `component:Platform,Governance,"Security/Release" -delivery:Cancelled`, Component grouping, visible Task ID/Title/Delivery/Risk/Review gate/Evidence and hidden Status. | Current custody/build/maintenance view accepted. Sensitive reports remain outside the public Project. |
| [Default View 1](https://github.com/users/aloerch/projects/2/views/1) | API agrees with the owner: Delivery visible and Status hidden. | Resolved; default view preserved. |

GitHub's [board instructions](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout) distinguish the column field from horizontal Group by. Accordingly, `project.json` now uses `column_field: Delivery` for the board; `group_by` retains its horizontal meaning. These are local manifest names, not invented GraphQL inputs. The importer still does not change manual view settings or infer acceptance from view creation.

## Exact remaining owner actions

1. **GOV-02 / Review and approvals:** open [view 5](https://github.com/users/aloerch/projects/2/views/5), retain the existing Delivery filter, and add a Review gate filter selecting **Human approval, Security, Data migration and License/Brand** using the field/value picker. Save the view. Examine chapter 12's required review view and this readback; it currently includes Standard PR tasks because no gate filter is present. Resolution is a saved filter containing both restrictions, confirmed by supported readback or an explicit owner observation in [issue #9](https://github.com/aloerch/ambisgis-platform/issues/9). This blocks GOV-02 acceptance only, not unblocked FND-02 engineering.
2. **GOV-02 / roadmap Delivery authority:** inspect [view 4](https://github.com/users/aloerch/projects/2/views/4) and confirm built-in Status is hidden, or explicitly document its derived mapping from Delivery and that it is not independently maintained. Preserve the accepted Phase grouping and Start date/Target date mappings. Examine the contradictory `fields`/`configuration.visibleFields` readback above; no existing Status values need resetting. Resolution is the exact owner observation in [issue #9](https://github.com/aloerch/ambisgis-platform/issues/9), with supported readback where available. This also blocks GOV-02 acceptance only.

The owner need not repeat already accepted settings or recreate views. If a UI setting cannot be changed, record that precise limitation and resolve it against the existing authority policy; do not silently weaken the policy.

## Acceptance and Delivery evidence

- **Dependency-based readiness:** GOV-01's [owner-approved merge](https://github.com/aloerch/ambisgis-platform/issues/8#issuecomment-5740802894) establishes the prerequisite. Its live Delivery is Merged. GOV-02's remaining blocker is the two checks above.
- **Distinct transitions:** the GOV-01 record documents In review, Verified after tests/owner approval, and Merged after actual merge readback. Current readback retains FND-01/GOV-01 Merged, FND-02 In progress and GOV-02 Blocked. A merged database PR does not complete all FND-02 acceptance, and none of these is Released. Cancelled remains a separate Delivery option.
- **Evidence-preserving updates:** the historical [GOV-01 no-op apply](project-live-evidence.md) demonstrated zero mutations and preserved item/issue state. This is historical evidence, not a fresh importer run. The reconciliation itself performs no Project writes.
- **Verified required views:** named layouts and the accepted settings above are evidenced; the two remaining checks prevent whole-task acceptance. After their resolution, reconcile the fresh owner/API evidence and move GOV-02 through In review for this separate correction PR, then Verified/Merged only after the applicable review and actual merge. Do not close or mark the task complete from the current partial result.

The retained query is read-only. To refresh it, use the verified local GitHub CLI from `plan/`:

```sh
gh api graphql -F query=@verification/project-view-readback.graphql
```

Check for GraphQL errors, verify the owner/repository/Project identities, and require every `pageInfo.hasNextPage` to be false (otherwise continue pagination). Do not overwrite the dated evidence or treat HTTP success alone as complete readback. The [GraphQL Projects reference](https://docs.github.com/en/graphql/reference/projects) documents these read fields; roadmap UI observations remain attributed to the owner.

## Validation

From `plan/`, the verified validation environment passed **175 package/governance tests with no skips** and strict schema validation (15 repositories, 66 tasks, 24 requirements, 65 source references; four schemas/examples). [Exact commands and outcomes](../verification/project-view-validation.txt) and [test output](../verification/project-view-tests.txt) are retained. An initial test invocation from the repository root failed before discovery; rerunning from the required `plan/` directory passed. No GIS product acceptance or fresh database/native-build result is claimed.
