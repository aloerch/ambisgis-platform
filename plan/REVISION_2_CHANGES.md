# Revision 2 — controlling changes

**19 September 2026. Replaces, rather than merely supplements, the first plan.**

The user clarified that the goal is an independently maintained GIS product made from forked and combined source—not an upstream-led integration distribution. The old plan's thin-fork policy, preference for unchanged externally supplied PostgreSQL/PostGIS, and exclusion of QGIS core from source custody were inconsistent with that goal.

The revised requirements are binding:

1. Own the selected source baselines, builds, patch path, contracts and release authority. Donor releases are optional inputs; upstream acceptance or synchronization is never required.
2. Combine and refactor product responsibilities, not just logos and login. Retain one catalog, metadata authority, policy model, service lifecycle, installer and supported product release. Preserve process boundaries where security, storage or fault isolation justify them.
3. Retain complete relevant dependency/build inputs. Demonstrate an upstream-disconnected rebuild and independent synthetic-defect repair. Pinning alone is not independence, and indefinite insecure freezing is prohibited.
4. Use **AmbisGIS** as the working product name and `ambisgis-` as the repository prefix. This is not a trademark clearance. Brand/configuration choices must be reversible.
5. Use one cross-repository GitHub Project, **AmbisGIS — Product Development**, with issue-backed work, explicit dependencies, review/evidence gates and safe repeatable provisioning.

## Concrete package changes

The repository manifest now has four new projects and eleven forks (fifteen total), including PostgreSQL, PostGIS, QGIS, GeoTools, GeoWebCache, JupyterHub and JupyterLab source custody. The plugin repository is `ambisgis-qgis-plugin`; `ambisgis-qgis` is the actual QGIS fork.

Two detailed chapters cover independent product maintenance and GitHub Projects. Seven new tasks bring the backlog to 66; four additional requirements bring traceability to 24. Existing task IDs and the original five capability goals are retained. The architecture, component documents, roadmap, source-lock template, bootstrap, agent rules and start prompt have been updated rather than leaving contradictory instructions in an addendum.

The new Project seed exporter is a local executable aid. The live Project provisioner is a clearly specified Codex task, not something claimed to exist already. GitHub CLI/GraphQL capabilities and permission requirements are cited in the Project chapter; no live Project/repository writes occurred during this revision.

## First action for Codex

Use this revision's `AGENTS.md` and `CODEX_START_PROMPT.md`. Do not run the old eight-repository bootstrap. Verify actual remote state before writes. The previous plan had not created repositories, but Codex must not assume that remains true when it executes.
