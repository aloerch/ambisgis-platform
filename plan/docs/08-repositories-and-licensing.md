# 08 — Owned repositories, licenses and branding

## 1. Repository plan

The authenticated GitHub login was verified as **aloerch**. New projects must be created there unless the user deliberately changes the manifest and owner. Existing repositories, including `osgs-neu` and `weaveatlas`, are outside this task. An accessible-repository listing is not proof that a proposed name is free, so bootstrap checks GitHub directly at execution.

| Repository | Kind / source donor | Responsibility |
|---|---|---|
| `aloerch/ambisgis-platform` | New | Umbrella product, control plane, gateway, portal, publishing, SDK, deployment and integration tests |
| `aloerch/ambisgis-geodb` | New | Typed geodatabase semantics, migrations, branch engine and correctness tests |
| `aloerch/ambisgis-qgis-plugin` | New | QGIS publishing and controlled branch-edit plugin |
| `aloerch/ambisgis-notebooks` | New | JupyterHub integration, spatial environments and isolation tests |
| `aloerch/ambisgis-postgresql` | Fork of `postgres/postgres` | Owned PostgreSQL source and tested database-engine builds; semantic changes only when justified |
| `aloerch/ambisgis-postgis` | Fork of `postgis/postgis` | Owned PostGIS source, spatial extension builds and regression tests |
| `aloerch/ambisgis-qgis` | Fork of `qgis/QGIS` | Owned QGIS desktop/server source and product distribution; publishing plugin developed separately |
| `aloerch/ambisgis-jupyterhub` | Fork of `jupyterhub/jupyterhub` | Owned multi-user notebook service source and security maintenance |
| `aloerch/ambisgis-jupyterlab` | Fork of `jupyterlab/jupyterlab` | Owned notebook workbench source and product UX |
| `aloerch/ambisgis-geotools` | Fork of `geotools/geotools` | Owned server geospatial library source and builds |
| `aloerch/ambisgis-geowebcache` | Fork of `GeoWebCache/geowebcache` | Owned tile-cache engine source and builds |
| `aloerch/ambisgis-geoserver` | Fork of `geoserver/geoserver` | Independently maintained rendering and service-engine source derived from GeoServer |
| `aloerch/ambisgis-geonode` | Fork of `GeoNode/geonode` | Independently maintained catalog/control-plane source derived from GeoNode |
| `aloerch/ambisgis-mapstore-client` | Fork of `GeoNode/geonode-mapstore-client` | GeoNode and MapStore integration bridge |
| `aloerch/ambisgis-mapstore` | Fork of `geosolutions-it/MapStore2` | Independently maintained map/dashboard/application components derived from MapStore |

These are fifteen repositories under one product, not fifteen independently configured applications. All are linked to the umbrella GitHub Project in chapter 12. Additional dependencies are retained as verified source/build inputs; promote one to a named fork only through a reviewed manifest and allow-list change. [S56–S62]

## 2. Monorepo boundaries

Suggested umbrella tree after Codex seeds it:

```text
ambisgis-platform/
  AGENTS.md  README.md  STATUS.md  DECISIONS.md
  docs/  adrs/  contracts/  plan/
  apps/portal/                 # product shell and supported MapStore adapter
  services/control-plane/     # GeoNode Django extension, catalog/jobs/policy
  services/gateway/           # native feature/API + rendering/compat adapters
  workers/publishing/          # durable state-machine executors
  packages/python-sdk/
  packages/typescript-sdk/
  packages/policy-contracts/
  deploy/compose/  deploy/profiles/
  tests/contract/  tests/e2e/  tests/security/  tests/performance/
  tools/  release/  .github/workflows/
```

Shared schemas live in the umbrella repository and are released/versioned for dependent repositories. `ambisgis-geodb` is a library package consumed by the gateway, not automatically a separate network service. Do not scatter tiny shared functions into additional public repositories. Each owned source module has its own tests and source revisions; only the AmbisGIS release manifest determines the supported product combination. Component tags are provenance, not independent customer upgrade instructions.

## 3. Fork and branch discipline

Create real public GitHub forks to preserve provenance; a GitHub fork is a separate repository and does not require synchronization with the donor. The visible fork relationship is not runtime coupling. Preserve original copyright, license files, source ancestry and the selected baseline tag/commit. [S35, S55]

Create `ambisgis/main` from the selected baseline as the canonical product branch, and `ambisgis/release/<series>` for maintained releases. Imported donor branches/tags remain reference-only and are not production tracking branches. Rebase/force-push of shared product history is forbidden. After workflow audit and a reviewed setup PR, setting `ambisgis/main` as the fork default is authorized for these new targets; the repository bootstrap itself does not perform that change. Do not rename or overwrite upstream reference branches.

`origin` is the owned fork. `upstream` is an optional read-only reference remote used only for deliberate research/import work. Release builds resolve owned source commits or retained content-addressed source archives, never `upstream/main`, mutable external tags, or automatic fork synchronization. Git bundles and required LFS/submodule assets are backed up independently of the GitHub fork network.

Record permanent product changes in `CHANGES_FROM_DONOR.md`: rationale, files, source provenance, tests, security/compatibility implications and responsible module. No removal condition or upstream PR is mandatory for a deliberate product divergence. Helpful external fixes may be offered upstream, but acceptance is not a dependency and no agent is authorized to contact maintainers without user approval.

Audit imported workflows, package coordinates, download scripts and update checks before enabling builds. Redirect product artifacts into owned namespaces; preserve internal package names when gratuitous renaming would break compatibility. Do not publish into upstream namespaces. CI uses reviewed permissions and dependency inputs; release credentials are unavailable to untrusted pull requests.

## 4. Licensing baseline and review gates

This section is an engineering compliance plan, not a legal opinion. A public fork preserves the upstream license; changing a logo does not relicense copied code or remove notice/source obligations.

| Component | Planning evidence | Action |
|---|---|---|
| PostgreSQL | PostgreSQL permissive license [S28] | Preserve license and copyright in the mandatory owned fork; retain tested storage semantics initially. |
| PostGIS | GPL licensing [S29] | Preserve actual selected-source terms and provide corresponding source for distributed builds as required. |
| GeoServer | GPL terms [S30] | Retain licenses/notices/source/build instructions; match extensions and audit their licenses too. |
| GeoNode | Docs describe GPL3+; reviewed repository header says GPL2+ and includes GPL3 text [S06, S31] | **Do not guess away this discrepancy.** Preserve the file verbatim; resolve exact release/file-level scope in the inventory and escalate ambiguous derived-work combinations. |
| MapStore | Reviewed two-condition BSD-style license [S32] | Retain actual license/disclaimer in source and binary notices; inspect dependencies/assets separately. |
| geonode-mapstore-client | Requires exact selected-commit license inspection | Bootstrap verifies the upstream repository, but that is not license approval for copied code. |
| QGIS/plugin/server | GPL terms [S33] | Verify plugin distribution obligations and separate trademarks/assets. |
| Jupyter/identity/dependencies | Exact release/license inventory required | Do not infer the license of the entire image from one top-level project. |

Proposed default for **new first-party product code** is `GPL-3.0-or-later`, supporting an openly maintained integrated distribution and compatible use where upstream terms permit. Independent schemas/SDKs may later adopt a permissive license only through an explicit ADR; don't casually copy GPL implementation into a supposedly permissive SDK. Upstream files always retain their actual terms. Process/network separation helps architecture but is not an automatic legal exemption from all combined-work obligations.

Before distributing binaries/images, produce a component/file-level license inventory, source availability bundle or durable corresponding-source links, build scripts, modifications log, notices, asset/font/driver rights and SBOM. Check whether a particular bundled component introduces AGPL, noncommercial, source-available, or restricted redistribution terms. Do not label source-available software open source without checking its actual license.

## 5. Branding policy

Use original product name, logo, icons and design tokens after trademark/domain review. Keep an About/Third-party notices page and clear upstream attribution. Do not remove legally required notices, pretend upstream work was authored by the project, imply endorsement by Esri/QGIS/OSGeo/GeoServer, or redistribute proprietary Esri logos/fonts/widgets.

AmbisGIS Desktop is a maintained QGIS-derived distribution, not a claim to have originally authored the desktop engine. Branded upstream distributions must comply with each project's trademark policy as well as copyright license. Accessibility and localization apply to new branding and all replacement UI elements.

## 6. Bootstrap tool: precise behavior

`tools/bootstrap_repositories.py` uses Python's standard library and an already installed/authenticated `gh`. The manifest `repositories.json` is allow-listed and rejects unexpected repository names/upstreams. Default mode performs **GET-only** checks and prints planned actions. `--apply` explicitly authorizes creation of missing public repositories/forks in the authenticated personal account.

The tool checks exact owner identity, manifest structure, repository visibility, upstream existence and fork parent. It distinguishes a confirmed HTTP 404 from authentication/permission/rate/network failures. It never treats arbitrary errors as permission to create. Fork creation is asynchronous, so it polls a bounded number of times and verifies the resulting parent/default branch. [S35–S36]

Existing matching forks are reported and left unchanged. Existing new-project repositories are reusable only if their GitHub numeric ID matches this tool's local creation receipt; otherwise it stops on collision. A receipt is local operational state, not proof against a malicious administrator; review it and never obtain it from untrusted code. A lost receipt can be recovered through an explicit human-verified process, not by guessing ownership from the description.

The tool creates remote repositories only. It does **not** clone, push files, enable Actions, configure secrets, modify existing repositories, delete anything, purchase services or change production systems. New repositories use an initial README. A local receipt records created repository IDs, upstream parent information and completed/partial status without tokens. Partial failure reports exactly which repositories may have been created; rerun safely after inspection.

If the initial POST response is lost, the next GET may discover a new repository without a receipt. The safe result is a collision requiring inspection, not automatic adoption. API authentication must be scoped to create the desired repositories; failure does not trigger automatic permission escalation.

## 7. Seeding and release flow

After successful bootstrap, Codex clones only the fifteen manifest repositories into a new workspace. Verify remotes and paths before writing. Seed the umbrella plan/contracts/tools on a feature branch. For each new component repo create README, chosen LICENSE/NOTICE, AGENTS, skeleton package/tests, security policy and CI; the skeleton must clearly state unfinished capabilities. Seed owned build and source-provenance metadata in every fork. Product consolidation may deliberately change inherited internals; do not retain a thin-patch-only rule.

Use human-reviewed PRs for database migrations, authorization, licensing, external publication, destructive operations and release signing. An agent may prepare code and tests; it does not self-certify security or legal compliance. Public releases reference exact commits across all repos, build from reproducible sources, publish provenance/SBOM and include a tested support matrix.
