# Implementation status

FND-01: [plan seed PR #1](https://github.com/aloerch/ambisgis-platform/pull/1), branch `fnd-01/seed-plan`, commit `aa70fcc`, is open for human review. All fifteen approved public repositories/forks were created and verified; all are cloned. Eleven complete Git bundles are retained locally and verified. Canonical product branches, approved baselines, LFS/submodule/dependency closure and owned builds remain incomplete.

GOV-01: this branch implements the dry-run/idempotent Project importer, its guarded GitHub adapter and safety tests. The [public Project](https://github.com/users/aloerch/projects/2) and all 66 task issues exist; live field/item/dependency seeding and readback are in progress. The task remains gated on FND-01 review, complete live verification and its own human review. [GOV-01 issue](https://github.com/aloerch/ambisgis-platform/issues/8).

Validation: 138 package/governance tests pass with no skips, and strict plan/schema validation passes. [Actual test output](plan/verification/project-importer-tests.txt). Stateful fake transport tests establish importer behavior, not GIS integration or security acceptance. Initial live preflight verified owner, all fifteen recorded repository IDs, Project collisions, scope and API capability checks.

GOV-02 remains incomplete: view grouping/sorting/filtering/date mappings and evidence transitions need verification. No GIS engine, owned product build, database/REST/UI/notebook journey or release has been accepted. No inherited workflows have been enabled; no default branches have changed.

Next: finish GOV-01 readback/idempotency evidence, review FND-01, then advance FND-02 source/license/dependency resolution using actual acquired-source evidence. Initial JSON statuses are unchanged seeds.
