# AmbisGIS — independent GIS product design and Codex handoff

**Revision 2.0 · 19 September 2026 · Supersedes the original integration-led plan**

AmbisGIS is an independently maintained, self-hosted GIS product built by forking, modifying and combining existing source. Upstream projects supply starting code, not continuing release or architecture authority. A branded integration stack alone is insufficient. Source custody, owned builds, independent repair and one canonical product model are required.

**AmbisGIS is a working name, not trademark-cleared.** No live GitHub repository, Project, issue, credential or workflow was created or modified in preparing this revision. The previously verified target login is `aloerch`; Codex must verify it again before writes. This is a design package, not implemented GIS software.

## Start here

Read `REVISION_2_CHANGES.md`, `docs/00-architecture.md`, `docs/11-independent-product-and-source-ownership.md` and `docs/12-github-projects-and-delivery.md`. Then open this directory in VS Code and use `CODEX_START_PROMPT.md`. `MASTER_DESIGN.md` assembles the complete design; `AmbisGIS_Design_Book.html` is the self-contained readable edition. Do not run the superseded repository bootstrap from the earlier package.

## Included artifacts and implementation status

The package has 13 design chapters, 66 tasks, 24 requirements, a 15-repository manifest, a GitHub Project schema, source/release templates, the original feature comparison and proposed API schemas. Existing domain requirements—branch editing, service administration, portal/apps, notebooks and QGIS publishing—remain intact.

Implemented tooling: safe repository creation bootstrap; plan/schema validators; a small illustrative three-way-merge model; an offline Project issue-seed exporter; and the receipt-backed Project importer in `tools/bootstrap_github_project.py`. The bootstrap and importer use Python's standard library plus a locally authenticated GitHub CLI. The importer defaults to read-only and preserves human progress; see [the runbook](docs/project-importer.md) for authorization, receipts, recovery and remaining view gates. Live execution and acceptance are recorded separately from mocked safety tests in `STATUS.md`. No GIS engine, product image or acceptance deployment is implemented by these tools.

```bash
# Local checks, no GitHub access:
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
python3 tools/export_project_seed.py --out /tmp/ambisgis-project-seed.json

# Read-only GitHub repository preflight (requires authenticated gh):
python3 tools/bootstrap_repositories.py --owner aloerch

# Explicit creation of missing approved public repositories only:
python3 tools/bootstrap_repositories.py --owner aloerch --apply

# Complete read-only Project preflight, requiring the actual bootstrap receipt:
python3 tools/bootstrap_github_project.py --repository-receipt .bootstrap-receipt.json

# Apply only after reviewing the dry run and local Project authorization:
python3 tools/bootstrap_github_project.py --repository-receipt .bootstrap-receipt.json --apply
```

Full schema checks use `requirements-validation.txt` in an isolated virtual environment. No command installs global packages, changes production systems or purchases infrastructure.

## Repository and Project model

Four new first-party repositories and eleven source forks are defined in `repositories.json`. They form one product and one controlled release graph. PostgreSQL/PostGIS and QGIS are no longer excluded from source custody. Preserving their mature internals initially is allowed; being unable to build or patch them independently is not.

One public user-owned GitHub Project, **AmbisGIS — Product Development**, spans all approved repositories. `project.json` specifies fields and views. `project-seed.json` is a generated local issue seed; it contains no actual remote issue or Project IDs. The live Project tracks progress while version-controlled tasks/requirements/contracts define engineering acceptance. Its actual identity comes from the creation receipt, never from the seed.

## Navigation

| Path | Purpose |
|---|---|
| `docs/00-architecture.md` | Product scope, source-owned architecture and state authorities. |
| `docs/01-landscape-and-parity.md` | Existing open-source capabilities and ArcGIS workflow comparisons. |
| `docs/02-server-and-rest.md` | Server operations, metadata, REST/OGC contracts and compatibility tiers. |
| `docs/03-geodatabase-and-versioning.md` | Branch lifecycle, reconciliation, posting, concurrency and recovery. |
| `docs/04-portal-and-applications.md` | Catalog, modern UI, maps, dashboards and application composer. |
| `docs/05-notebooks.md` | Owned Jupyter foundations, spatial environments, SDK and isolation. |
| `docs/06-qgis-and-publishing.md` | Owned desktop/server distribution and bundled publishing plugin. |
| `docs/07-security-and-operations.md` | Installer, authorization, upgrades, recovery and maintenance. |
| `docs/08-repositories-and-licensing.md` | Exact repository allow-list, source history, licensing and branding. |
| `docs/09-roadmap-and-acceptance.md` | Phases, tests, performance/UX targets and release criteria. |
| `docs/10-codex-engineering-workflow.md` | Agent task/PR protocol and implementation handoffs. |
| `docs/11-independent-product-and-source-ownership.md` | Binding independence, consolidation and source/build/patch requirements. |
| `docs/12-github-projects-and-delivery.md` | Project fields/views, safe provisioning, tasks, evidence and automation. |
| `release-lock.template.json` | Deliberately unresolved source/build/release manifest. |
| `SOURCES.md`, `DECISIONS.md`, `STATUS.md`, `VALIDATION.md` | Evidence, decisions, actual work status and local checks. |

## Boundaries

Do not touch `weaveatlas`, `osgs-neu`, old proposed repository names or unrelated existing repositories. Do not upload private work data, proprietary code, internal URLs, secrets, provisioning files or tokens. The default bootstrap is read-only; apply creates only the new allow-listed targets. Fork setup/default-branch changes and Project writes occur later under the narrowly scoped Codex instructions.

The scope is the specified enterprise GIS workflows, not all ArcGIS products or universal Esri binary/protocol compatibility. Independent maintenance is not original copyright ownership or an exemption from license obligations. Public product branding remains subject to a proper clearance review.
