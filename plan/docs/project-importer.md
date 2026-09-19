# Project importer operations

`tools/bootstrap_github_project.py` implements the GOV-01 importer. It creates only the approved personal Project and task resources after complete read-only discovery. A successful import establishes work tracking; it does not complete GIS tasks or their review gates.

## Run

Use Python 3.10+ and a locally installed/authenticated GitHub CLI. Authenticate as `aloerch`. The supported authorization path is GitHub CLI OAuth: dry-run needs `read:project` or `project`, while apply needs `project`. Missing/unknown scope evidence stops enumeration instead of treating a public-only listing as complete. Alternative token permission models are not yet verified. Credentials remain with `gh`; never pass or print a token.

From the plan directory, after repository bootstrap has produced a ready receipt for all fifteen IDs:

```sh
python3 tools/export_project_seed.py --out /tmp/ambisgis-seed.json
python3 tools/bootstrap_github_project.py \
  --repository-receipt /path/to/.bootstrap-receipt.json \
  --seed /tmp/ambisgis-seed.json
python3 tools/bootstrap_github_project.py \
  --repository-receipt /path/to/.bootstrap-receipt.json \
  --seed /tmp/ambisgis-seed.json --apply
```

The seed path must contain a freshly generated, exact match to the validated plan. Without `--seed`, the importer generates the same content in memory. Dry-run writes no creation receipt and issues no mutations. `--receipt` selects the local operational journal; its default is `.project-receipt.json`. Keep that file, its repository receipt and backups out of Git. The apply lock is `.project-receipt.json.lock` and contains no credentials.

## Recovery and progress preservation

The importer verifies owner IDs, all fifteen repository IDs/parents and the dependency graph before writes. It enumerates open and closed Projects, issue candidates, fields/options, archived and unarchived items, values, links, labels, views and native dependency edges with complete pagination. GraphQL partial errors stop the run.

Creates are never blindly retried. An interrupted issue, field, item, view or dependency operation is re-read and reconciled against its identity and pending journal. An unreceipted Project matching the title or marker remains a collision, including a lost initial create response: inspect it and recover the receipt through an owner-verified process. Do not delete resources or manufacture IDs to restart.

Issue specification changes replace only the bounded managed block after comparing its recorded hash and a fresh read. Text outside it, comments, assignments, closed state, manual Delivery, Priority and dates are preserved. Checking acceptance boxes inside the managed block is a human edit and causes a safe conflict if an automatic replacement would erase it. Inspect and reconcile such edits; do not reset checkboxes merely to satisfy the importer. GitHub's issue API does not provide a verified atomic body compare-and-swap here, so fresh reads/readback detect conflicts but cannot eliminate every remote edit race.

Initial fields apply only to newly added items with a recorded pending initialization. Resumption fills only still-absent values and reads them back. Archived items and changed identities stop for inspection rather than being restored automatically. The importer does not close/reopen tasks, set Ready from the seed, assign dates or infer completion.

## Views and remaining UI verification

The current documented API can create named table/board/roadmap views and choose visible fields for tables and boards. Roadmap creation rejects visible-field configuration, so that input is omitted for roadmaps. Built-in Status is excluded from the created table/board columns. Creation alone does not verify Delivery authority in the roadmap or GitHub's automatically created default view; that verification is recorded separately. The default view is preserved. Full configuration must be verified before GOV-02 is complete; this importer does not guess undocumented inputs or overwrite subsequent manual view configuration. Supported readback exposes filters, visible fields, grouping, board column fields and sorting. Accept attributed owner observations for UI-only settings such as roadmap date mappings; do not reset completed verification. See [the current GOV-02 reconciliation](project-view-reconciliation.md) for accepted evidence and precise remaining checks.

Open the created Project and configure each saved view using its view menu, then save changes:

- Product backlog: table; exclude Delivery Cancelled; group by Phase; sort by Priority then Task ID; show dependencies, Risk and Review gate.
- Execution board: set View → Column field to Delivery (the UI may label this Column group by field); horizontal Group by and Slice by are separate optional settings; show Ready, In progress, In review, Verified and Blocked, with other states available.
- Release roadmap: group by Target release (or Phase); select Start date and Target date. Leave dates unset until planning evidence supports them.
- Review and approvals: table; filter to In review/Blocked with human, security, migration or license review gates; show linked PRs and Evidence.
- Source and security maintenance: table; include custody/build/maintenance tasks and public vulnerability work. Sensitive reports stay off this public Project.

Record actual saved view IDs, supported configuration readback and attributed owner verification in GOV-02. GitHub distinguishes [board columns from horizontal grouping](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout). The manifest uses `column_field` for the former and `group_by` for the latter; these are local desired settings, not GraphQL input names. Merely creating a view name/layout does not satisfy its acceptance.

## Tests and limits

Run `python3 -m unittest discover -s tests -v` and `python3 tools/validate_package.py --require-schemas` in the validation environment. Stateful fake API tests cover collisions, pagination, scope errors, partial GraphQL failures, response loss, interruption, body conflicts, human progress and unchanged reruns. Live receipt/readback evidence is separate. These are governance/package tests, not database, rendering, browser, notebook, security-release or GIS acceptance tests.

API references: [Projects GraphQL](https://docs.github.com/en/graphql/reference/projects), [native issue dependencies](https://docs.github.com/en/rest/issues/issue-dependencies), [GitHub CLI API](https://cli.github.com/manual/gh_api).
