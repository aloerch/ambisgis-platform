# 11 — Independent product and source ownership

**Governing revision 2 requirement.** This chapter replaces the earlier thin-fork, upstream-led integration strategy. It is not an optional later optimization. The product is provisionally named **AmbisGIS**.

## 1. What is being built

AmbisGIS is a new, independently maintained GIS product created by adopting, modifying and combining existing open-source code. GeoServer, GeoNode, MapStore, PostgreSQL, PostGIS, QGIS and Jupyter supply initial code and provenance. They do not retain decision-making authority over AmbisGIS architecture, internal APIs, releases or defect correction.

The product must retain useful mature implementation work rather than rewrite rendering, spatial indexing, transactions or notebooks to prove independence. Conversely, it must not preserve a fragmented product structure merely to keep patches small or remain easy to merge upstream. A common login and theme over independently administered applications is insufficient.

“Owned” means custody and engineering control over the fork and distribution under the applicable licenses. It does not mean acquiring the original authors' copyright or a right to ignore license, patent, attribution or trademark restrictions. Apply chapter 08's file-level review before combinations and redistribution.

## 2. Observable independence requirements

| Requirement | Required outcome | Not sufficient |
|---|---|---|
| Source custody | Product source revisions, complete relevant history, licenses, build scripts and required assets are retained in controlled repositories or content-addressed archives. | A bookmark to an upstream repository. |
| Build authority | Product artifacts are built from selected owned source and recorded dependencies, without resolving external moving branches. | Pulling an upstream image with a fixed tag. |
| Change authority | AmbisGIS can change the catalog schema, engine hooks, notebook integration and UI to satisfy its own requirements. | Waiting for an upstream extension point or PR approval. |
| Release authority | One approved product manifest selects compatible module revisions and migration order. | Asking users to select independent GeoNode/GeoServer/PostGIS versions. |
| Operational independence | A supported release installs, runs and recovers using the product's retained assets and documentation. | A working developer machine with hidden package caches. |
| Maintenance independence | A defect can be diagnosed, patched, regression-tested and released without an upstream correction. | Freezing an old version forever. |
| Product cohesion | One authoritative item, metadata, permissions, service lifecycle and configuration model. | The same information writable independently through several inherited admin systems. |

Source control and version pinning prevent *unselected* changes from entering a release; they do not fix vulnerabilities, prove correctness or retain a missing dependency. The architecture therefore requires source retention, tested build inputs and a real maintenance workflow as well as pins.

## 3. Source portfolio and custody classes

**Class A — owned product roots.** Maintain the eleven source forks in `repositories.json`: GeoServer, GeoTools, GeoWebCache, GeoNode, its MapStore client, MapStore, PostgreSQL, PostGIS, QGIS, JupyterHub and JupyterLab. Each has an AmbisGIS product branch, source inventory, build recipe, regression tests and permanent-change ledger. A source fork may initially contain no algorithmic modifications; custody and independent build/repair capability still have to be demonstrated. The PostgreSQL/PostGIS GitHub donor repositories are mirrors; verify selected commits against their documented canonical provenance rather than assuming the GitHub PR workflow is upstream's workflow. [S56–S62]

**Class B — retained dependencies.** Track the complete selected transitive closure, including GDAL, PROJ, GEOS, native drivers, Python/JVM/Node libraries, notebook-server/kernel packages, Keycloak if selected, metadata libraries, frontend packages, font/style assets, CRS grids, compiler tools, base image packages, generated build tools and installer utilities. Retain the licensed source and required build/install artifacts with hashes and retrieval provenance. These do not all need a new public GitHub fork on day one. Any Class B component that needs permanent product-specific changes is promoted to an owned source project or vendored module through a reviewed manifest/ADR change.

**Class C — optional external integrations.** External identity services, basemaps, referenced organization databases and third-party clients may be supported, but the baseline product must work without them. Document what happens when such an integration disappears. External client compatibility is not part of the product's source-custody guarantee.

The existing fifteen-repository allow-list is a safety boundary for initial creation, not a claim that fifteen repositories cover every transitive dependency. Adding a source donor requires an explicit source/license/namespace review and corresponding tool allow-list change.

## 4. Combining code without forcing an artificial monolith

Use `ambisgis-platform` as the principal first-party monorepo: product shell, catalog/service contracts, configuration, publishing, SDK, build orchestration and cross-module tests. Keep imported histories/toolchains in their source forks where that is useful. Build all of them as one product. The release manifest, not independently moving repository defaults, is the source composition.

The catalog, service registry, authorization policy and publishing job model are AmbisGIS modules. They may begin from inherited GeoNode structures, but are allowed to evolve together. Frontend map/dashboard components are adopted from the owned MapStore source and exposed through one product composition model. GeoServer-derived rendering and the database remain specialized engines, not independent competing product authorities.

Do not merge Java rendering, PostgreSQL internals, Python control-plane code and browser code into a single process merely to reduce the number of boxes. Retain isolation for arbitrary notebook execution, parser workers, database privilege boundaries and fault containment. Remove boundaries whose only purpose is to keep two redundant catalogs or administration systems synchronized.

If physical source consolidation becomes advantageous, use an ADR and a history-preserving import into the destination module. Record original paths/commits and licenses. Do not duplicate the same active code in two repositories. Do not let a subtree or submodule resolve a donor branch tip. Avoid moving database/kernel code just for cosmetic repository uniformity.

## 5. Required consolidation register

Implement `architecture/consolidation-register.yaml` in OWN-01. Each inherited responsibility receives one disposition: **adopt**, **refactor**, **replace**, **remove**, or **retain as isolated engine**. Record current source, authoritative AmbisGIS owner, duplicates, migration, tests and compatibility consequences.

| Area | Initial disposition and outcome |
|---|---|
| GeoNode content/metadata/permissions | Adopt and refactor into the single AmbisGIS catalog and policy model. |
| GeoServer store/layer/style configuration | Retain engine mechanics; derive controlled configuration from AmbisGIS service definitions. No competing metadata owner. |
| MapStore/GeoNode application configuration | Consolidate into one versioned map/dashboard/application definition; reuse useful widgets. |
| Identity integration | One configured identity model; no separate product-user registration in inherited components. Keep identity provider and resource-policy responsibilities distinct. |
| Database layer definitions | One geodatabase schema authority; catalog stores references rather than a second editable schema. |
| Notebook source/runtime | Adopt source and product integration; retain separate security origins, users, files and execution boundaries. |
| Installation and updates | One configuration schema, release manifest, installer and upgrade contract. Inherited independent auto-updaters are disabled or replaced. |
| Legacy administration | Restrict during development; remove or route mutating operations through canonical policy before release. Emergency diagnostics must not become a backdoor. |

Adapter code remains acceptable between specialized modules whose source AmbisGIS controls. “No adapters” is not a requirement; “adapters to uncontrolled moving products as the permanent product strategy” is prohibited.

## 6. Branch, build and artifact rules

Use `ambisgis/main` for product development, task branches for work, and `ambisgis/release/<series>` for supported lines. Preserve donor reference commits and license history. Do not require rebasing product history on a donor branch. The fork relationship on GitHub is provenance, not a release dependency. Keep independent Git bundles/backups, including required LFS objects and submodule sources. [S55]

A release record includes product version; source repository/commit for every component; donor baseline for attribution; archive hashes; dependency lock hash; build recipe and toolchain identifiers; output image/package digests; migration range; license inventory; SBOM; tests; signatures and retention location. The supplied `release-lock.template.json` intentionally has unresolved values. It is a template, never a deployable lock.

Initial acquisition may download reviewed upstream sources and packages. The acceptance build uses only retained approved inputs. Avoid live package index resolution, Maven snapshot artifacts, floating Git refs, unrecorded frontend install scripts, container startup package installation or automatic desktop/notebook extension updates. Mirror permitted binaries as installation aids, but retain the source/build information needed for the independence and licensing requirements. Reproducible inputs are mandatory; byte-identical outputs are claimed only where demonstrated.

Builds of inherited Java modules need controlled coordinates and repository resolution. Audit GeoServer's GeoTools/GeoWebCache/extension dependency tuple. Refactoring one side without rebuilding the other is a product change requiring full affected contract tests. Native GIS stacks likewise need coherent shared-library/CRS-resource versions. This is AmbisGIS's responsibility, not the user's installation problem.

## 7. Upstream updates are optional inputs

Monitor disclosures and useful external changes. For each candidate record relevance, affected product branches, license/provenance, compatibility, migration and tests. Choose between a cherry-pick, an adapted backport, an independently authored fix, a larger deliberate import, or rejection with rationale. A whole upstream release is not mandatory just because it includes a needed correction.

Permanent product divergences are valid. They must be documented and supportable, not justified by minimizing the patch count. Contributing a reusable change upstream can reduce duplicated effort, but waiting for its acceptance must never block AmbisGIS's own release.

Independence does not justify insecure indefinite freezing. Define supported product lines and ownership for vulnerability triage. Where a correction cannot yet be made safe, provide a mitigation, disable the affected optional capability, or withhold the release. Do not invent a security service-level agreement without maintainers capable of meeting it. Use private reporting for undisclosed vulnerabilities; public project boards must not expose sensitive reports.

## 8. Independence acceptance drills

**T-OWN-01 — custody audit:** recover a selected source baseline from controlled storage. Verify hashes, licenses, assets and ancestry. Demonstrate that a pointer to an external remote is not mistaken for a retained copy.

**T-OWN-02 — moving-upstream immunity:** build the initial slice from the release inputs, change simulated donor defaults/APIs and build again without changing the product manifest. Those donor changes must not enter the build. Record actual reproducibility results, not assumptions.

**T-OWN-03 — canonical product state:** change metadata/sharing/service configuration through the product API; inspect every derived engine state and attempt alternate legacy write paths. Conflicting authority or policy bypass fails acceptance.

**T-OWN-04 — upstream-disconnected repair:** block upstream source/package/image hosts; restore controlled source and dependencies in a clean environment; rebuild selected server, database, desktop and notebook artifacts; correct a synthetic regression directly in owned source; test and package it; install; publish/query/edit/reconcile/post; exercise notebooks; restore from backup. Do not use an upstream patch or covert network download in the exercise. Provide network-denial evidence and toolchain/base-image provenance.

**T-OWN-05 — maintenance exercise:** take a disclosed or synthetic defect and prepare a product-specific fix/backport, impact assessment, regression tests, upgrade/recovery plan and release notes. Demonstrate a valid path even where importing the latest donor release would break an AmbisGIS contract.

These are required implementation tests, not tests that have been run during plan preparation. FND-07/FND-08 establish the initial custody/build foundation. OWN-01 consolidates models. OWN-02 and SEC-04 qualify full release independence.
