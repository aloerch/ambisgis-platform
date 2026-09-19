# Evidence register

Research date: **19 September 2026**. These are primary project, standards, and vendor sources. A citation such as [S01] in the specifications points to this register. Source statements describe upstream capabilities; all architecture, requirements, performance targets, implementation tasks, and acceptance criteria are **proposals**, not claims of an implemented product.

“Stable,” “latest,” and “current” documentation URLs are moving references. Some pages reviewed contained release examples or version labels inconsistent with their navigation. **No version number on a documentation page is an approved dependency pin.** Task FND-02 must select and record a tested release tuple, source commits, dependency locks, image digests, license evidence, and security advisories before implementation depends on it. Esri reference behavior targets the user's **ArcGIS Enterprise 11.5 / ArcGIS Pro 3.5.x** environment unless a test explicitly names another version; current Esri documentation may describe newer behavior.

| ID | Primary source | Evidence used / limitation |
|---|---|---|
| S01 | GeoServer REST: https://docs.geoserver.org/stable/en/user/rest/index.html | Administration/configuration API, not a ready-made ArcGIS FeatureServer contract. |
| S02 | GeoServer metadata extension: https://docs.geoserver.org/stable/en/user/extensions/metadata/index.html | Customizable metadata fields and REST/CSW integration exist; standalone GeoNetwork is not inherently required. |
| S03 | GeoServer vector tiles: https://docs.geoserver.org/stable/en/user/extensions/vectortiles/index.html | Vector tile extension; exact formats and installation depend on the selected release. |
| S04 | GeoServer ImageMosaic: https://docs.geoserver.org/stable/en/user/data/raster/imagemosaic/index.html | Raster mosaics and coverage-serving foundations, not complete Image Server parity. |
| S05 | GeoServer OGC API modules: https://docs.geoserver.org/stable/en/user/community/ogc-api/ | Module maturity varies. Do not label every OGC API implementation stable or certified. |
| S06 | GeoNode overview: https://docs.geonode.org/projects/v4/en/4.4.x/about/index.html | Integrated geospatial content, metadata, discovery, and sharing. License description differs from repository header; see S31. |
| S07 | GeoNode components: https://docs.geonode.org/projects/v4/en/4.4.x/advanced/components/index.html | Existing component/security integration, including GeoServer and GeoFence, needs preservation and testing. |
| S08 | GeoNode installation: https://docs.geonode.org/projects/v4/en/4.4.x/install/basic/index.html | An integrated deployment baseline exists; new installer should automate and simplify rather than ignore it. |
| S09 | MapStore dashboards: https://docs.mapstore.geosolutionsgroup.com/en/latest/user-guide/exploring-dashboards/ | Maps, charts, tables, counters, and connected widgets are reusable foundations. |
| S10 | MapStore application contexts: https://docs.mapstore.geosolutionsgroup.com/en/latest/user-guide/application-context/ | Configurable application/context foundation; not a drop-in Experience Builder replacement. |
| S11 | QGIS Server introduction: https://docs.qgis.org/3.44/en/docs/server_manual/introduction.html | Desktop/server share rendering libraries; QGIS Server provides an alternative renderer, not a portal. |
| S12 | QGIS Server configuration: https://docs.qgis.org/3.44/en/docs/server_manual/getting_started.html | Project-based serving and server deployment. This documentation branch is not a mandated runtime version. |
| S13 | PostGIS documentation: https://postgis.net/documentation/ | Spatial database foundation; application geodatabase semantics must be assessed separately. |
| S14 | PostgreSQL MVCC: https://www.postgresql.org/docs/current/mvcc-intro.html | Database concurrency/snapshots are not an application-level named-branch/reconcile/post workflow. |
| S15 | Kart: https://kartproject.org/ | Existing spatial/tabular version control; assess reusable merge ideas and working-copy support, not assumed service equivalence. |
| S16 | GeoGig: https://geogig.org/ | Existing distributed geospatial version-control approach; assess against service workflow requirements. |
| S17 | QGIS versioning plugin: https://plugins.qgis.org/plugins/qgis_versioning/ | An existing PostGIS/QGIS history/branching approach. The registry's release history alone does not establish current maintenance or fitness. |
| S18 | JupyterHub web security: https://jupyterhub.readthedocs.io/en/stable/explanation/websecurity.html | Default semi-trusted assumptions and need for per-user domains for robust browser isolation. |
| S19 | Jupyter Docker Stacks: https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html | Base scientific images; a reproducible geospatial environment still needs to be assembled. |
| S20 | Esri version-management REST: https://developers.arcgis.com/rest/services-reference/enterprise/version-management-service/ | Public reference for branch editing/version lifecycle. Our native API is not asserted protocol-compatible. |
| S21 | Esri feature service REST: https://developers.arcgis.com/rest/services-reference/enterprise/feature-service/ | Reference for service/layer resources and capability flags. Only tested operations may be advertised. |
| S22 | Esri applyEdits: https://developers.arcgis.com/rest/services-reference/enterprise/apply-edits-feature-service/ | Reference for edit result, rollback, and transaction behavior; versions must be tested explicitly. |
| S23 | Esri branch scenarios: https://doc.esri.com/en/arcgis-pro/latest/help/data/geodatabases/overview/branch-version-scenarios.html | Workflow reference; do not copy internal SDE implementation. |
| S24 | OGC API Features Part 1: https://docs.ogc.org/is/17-069r4/17-069r4.html | Read/query standard foundation; does not by itself solve versioned editing. |
| S25 | GeoNetwork: https://geonetwork-opensource.org/ | Rich metadata validation, harvesting, and catalog workflows; optional advanced profile, not mandatory basic installation. |
| S26 | pycsw: https://pycsw.org/ | Lightweight catalog/standards component; bundle behind the product when needed. |
| S27 | GDAL OpenFileGDB: https://gdal.org/en/stable/drivers/vector/openfilegdb.html | File-geodatabase read/write capabilities, domains/relationships and limitations; not an enterprise geodatabase or ArcPy substitute. |
| S28 | PostgreSQL license: https://www.postgresql.org/about/licence/ | Preserve permissive PostgreSQL license. |
| S29 | PostGIS introduction/license: https://postgis.net/docs/manual-3.6/postgis_introduction.html | GPL licensing for PostGIS; verify source files at selected commit. |
| S30 | GeoServer license: https://docs.geoserver.org/stable/en/user/introduction/license/ | GPL terms; preserve upstream notices and corresponding source obligations. |
| S31 | GeoNode repository license: https://github.com/GeoNode/geonode/blob/master/LICENSE | Reviewed header says GPL v2 or later, while included complete text is GPL v3 and docs describe GPL3+. Preserve verbatim; resolve exact selected-release/file scope in legal inventory. |
| S32 | MapStore license: https://github.com/geosolutions-it/MapStore2/blob/master/LICENSE.txt | Reviewed BSD-style two-condition license with additional disclaimer text; preserve the actual license file. |
| S33 | QGIS license: https://qgis.org/license/ | GPL terms and branding distinct from product code; verify plugin obligations. |
| S34 | Keycloak OIDC: https://www.keycloak.org/securing-apps/oidc-layers | Standard identity endpoints and flows. Deployment uses supported authorization-code/PKCE or device flows, not embedded passwords. |
| S35 | GitHub forks API: https://docs.github.com/en/rest/repos/forks | Public forks can be named; creation is asynchronous. Bootstrap verifies actual parent and readiness. |
| S36 | GitHub CLI repository create: https://cli.github.com/manual/gh_repo_create | CLI/API repository creation foundation; authentication must exist in the local environment. |
| S37 | OpenAI AGENTS.md guidance: https://developers.openai.com/codex/guides/agents-md | Agent instructions and scoped repository guidance. Re-check current behavior in the installed Codex version. |
| S38 | OpenAI Codex IDE: https://developers.openai.com/codex/ide/ | VS Code workflow reference; no claim that an agent can autonomously prove production correctness. |
| S39 | G3W-SUITE: https://g3w-suite.readthedocs.io/en/latest/ | Integrated QGIS-oriented publishing, access control, and web-editing alternative worth evaluating in P0. |
| S40 | Lizmap: https://docs.lizmap.com/current/en/ | QGIS-oriented web publishing alternative; evaluate end-to-end publishing before writing new glue. |
| S41 | pygeoapi: https://pygeoapi.io/ | Standards-oriented API implementation candidate; not an ArcGIS REST compatibility layer. |
| S42 | Martin: https://maplibre.org/martin/ | Specialized vector-tile server candidate; add only for measured benefit. |
| S43 | TiTiler: https://developmentseed.org/titiler/ | Specialized raster/COG tile serving candidate; not full Image Server functionality. |
| S44 | Koop upstream README: https://github.com/koopjs/koop | GeoServices/FeatureServer output and provider/plugin architecture; evaluate reuse for C1, not evidence of complete edits/versioning. |
| S45 | MapServer / OSGeo: https://www.osgeo.org/projects/mapserver/ | Mapping engine, OGC services and MapCache; compare as an alternative, not a default extra renderer. |
| S46 | Mapbender: https://mapbender.org/ | Browser-configured map applications and QGIS2Mapbender publication workflow. |
| S47 | QWC Services upstream README: https://github.com/qwc-services/qwc-docker | QGIS Web Client service components for authentication/permissions, editing, search and permalinks. |

## Evidence versus engineering assumptions

The project selection is not a benchmark result, security audit, legal opinion, or exhaustive inventory of all GIS software. “New work” means the proposed integrated product does not yet have an accepted implementation; it does not mean no other project has ever addressed that problem. All performance numbers in the design are proposed acceptance targets. All license decisions require exact-release, dependency, trademark, and redistribution review before public binary release.


## Revision 2 evidence — reviewed 19 September 2026

The original survey is retained. These references support the revised ownership/governance plan; links to repositories do not certify a selected build or its license closure.

| ID | Primary source | URL | Relevance / limitation |
|---|---|---|---|
| S48 | GitHub: About Projects | https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects | User/org-level table, board and roadmap over issues/PRs; custom fields. |
| S49 | GitHub: Projects API | https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects | GraphQL queries/mutations; project identity and authorization. |
| S50 | GitHub CLI: project | https://cli.github.com/manual/gh_project | CLI command family and project scope. |
| S51 | GitHub CLI: field-create | https://cli.github.com/manual/gh_project_field-create | TEXT, SINGLE_SELECT, DATE, NUMBER creation; do not invent iteration/view CLI flags. |
| S52 | GitHub: Automating Projects with Actions | https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions | Repository GITHUB_TOKEN cannot access Projects; appropriate user PAT / organization App required. |
| S53 | Microsoft: About Azure DevOps projects | https://learn.microsoft.com/en-us/azure/devops/organizations/projects/about-projects?view=azure-devops | Azure DevOps project is a broader service/security container, not a one-to-one equivalent of GitHub Projects. |
| S54 | USPTO: Comprehensive clearance search | https://www.uspto.gov/trademarks/search/comprehensive-clearance-search-similar-trademarks | Exact-name web searching is not clearance; similar marks and common-law use matter. |
| S55 | GitHub: Forks | https://docs.github.com/en/pull-requests/reference/forks | Separate repositories with own settings; fork-network relationship and visibility behavior. |
| S56 | PostgreSQL source mirror | https://github.com/postgres/postgres | Initial source donor; GitHub mirror is not the PostgreSQL upstream PR workflow. |
| S57 | PostGIS source mirror | https://github.com/postgis/postgis | Initial source donor; exact baseline and canonical provenance verification remain P0. |
| S58 | QGIS source | https://github.com/qgis/QGIS | Initial source for owned desktop/server fork; license/asset audit at selected commit. |
| S59 | JupyterHub source | https://github.com/jupyterhub/jupyterhub | Initial source for owned notebook service fork. |
| S60 | JupyterLab source | https://github.com/jupyterlab/jupyterlab | Initial source for owned workbench fork. |
| S61 | GeoTools source | https://github.com/geotools/geotools | Initial source for owned geospatial Java library fork. |
| S62 | GeoWebCache source | https://github.com/GeoWebCache/geowebcache | Initial source for owned tile-engine fork. |
| S63 | GitHub: About milestones | https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/about-milestones | Milestones group issues/PRs within a repository. |
| S64 | GitHub: Creating issue dependencies | https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies | Native blocked-by/blocking relationships and documented CLI operations; verify installed CLI capabilities. |
| S65 | OpenAI: AGENTS.md guidance | https://developers.openai.com/codex/guides/agents-md/ | Root and scoped agent instructions; current page redirects to ChatGPT Learn. |
