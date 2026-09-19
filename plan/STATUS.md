# Implementation status — revision 2

The design has been revised for an independently maintained AmbisGIS product, with owned source/build/repair requirements and cross-repository GitHub Projects governance. The previous domain specifications remain, with conflicting upstream-led defaults replaced. Local package checks are recorded in VALIDATION.md.

No live GitHub repositories, forks, Projects, issues, secrets or workflows were created or changed while preparing this revision. No donor code has been acquired into product forks, no product build/engine/GUI/plugin has been implemented, and no GIS acceptance or independent-maintenance exercise has run. The repository bootstrap has mocked tests. The Project seed exporter is local only. The live Project importer remains GOV-01.

Next ready task: FND-01. After environment/preflight and explicit repository creation, begin source/license resolution, FND-07/FND-08 source custody/builds and GOV-01/GOV-02 governance according to the dependency graph. Do not let an unavailable Project credential prevent unrelated safe design/build work.

Future entries must record task ID, repo/branch/commit/PR, actual tests, failed/skipped checks, live Project updates, remaining acceptance and next action.
