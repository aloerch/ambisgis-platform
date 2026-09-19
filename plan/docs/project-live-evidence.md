# GOV-01 live verification

The public [AmbisGIS Project](https://github.com/users/aloerch/projects/2) was provisioned under the owner's locally authorized GitHub CLI identity. Repository bootstrap receipts verified all fifteen newly created target IDs. The first complete dry-run made no mutations and wrote no Project creation receipt.

Live apply created eleven custom fields and seeded 66 issues/items with stable Task IDs, actual specification/dependency links and 130 native blocked-by relations. All five requested view names/layouts now exist. GitHub also created a default `View 1`; it was preserved. Grouping, sorting, filters, roadmap date mappings and Delivery authority remain GOV-02 UI gates. Current saved filters were read back as unset; no completed filter setup is claimed.

An initial apply stopped at roadmap creation because GitHub rejects visible-field configuration for that layout. The receipt preserved the existing resources. After a regression-tested layout-specific fix, resumption created only the missing views, updated importer-owned specification links and completed full issue/dependency readback. No resource was deleted or blindly recreated. GraphQL errors returned with HTTP 200 are now reported as sanitized application errors rather than misleading generic HTTP failures.

At `2026-09-19T09:23:30.263248+00:00`, a fresh unchanged apply completed with **480 transport read calls and zero mutation calls**. All 66 item values/archive states compared equal before/after. Representative FND-01/FND-02/GOV-01/GOV-02 issue bodies, closed/open states, assignees and comment counts compared equal, including FND-01's existing Merged progress and closed issue. Later deliberate evidence/state updates are separate from this snapshot.

[The public evidence export](../verification/project-live.json) records actual Project/repository/issue/item/field/option/view IDs, URLs, dependency edges, tested source hashes and observed preservation checks. Local operational receipts, authenticated CLI state, source archives and raw local build paths are retained outside Git. No token or private issue content is published.

All 143 package/governance tests pass without skips, and strict validation passes. Independent agent review found no blocker; it does not substitute for the owner's required human review of GOV-01. Issue-body concurrency protection remains optimistic, without verified atomic compare-and-swap support. The importer is not GIS product or release acceptance evidence.
