# FND-02 Java rendering dependency audit

This is a static source/dependency audit, **not a Maven dependency lock, Java
build, distribution, or runtime acceptance**. The selected owned roots are
GeoTools 34.5, GeoWebCache 1.28.5, GeoServer 2.28.5 and GeoNode 5.1.0. Exact
commits, archive hashes and audit research inputs are in `inputs.json`.

Read [the findings](../../plan/docs/java-dependency-audit.md) and
[the handoff](../../plan/docs/java-audit-handoff.md) before acquisition/build work.
The archives preserve original source/notices. `inputs.json` inventories only
retained audit inputs; it deliberately does not call them a complete closure.

## Verify and reproduce

From the platform worktree, using Python's standard library and Git:

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
python3 build-support/java/acquisition.py \
  --custody "$TASK_ROOT/source-archives/java-audit"
python3 build-support/java/audit.py --owned-root "$TASK_ROOT" \
  --output /tmp/ambisgis-java-audit-fresh.json
python3 -m unittest discover -s build-support/java -p 'test_*.py' -v
```

Use a new output filename on every audit. The source inventory is deterministic;
compare its SHA256 with the recorded declaration inventory. The audit reads Git
objects at exact selected commits, verifies owned origins and tag identities,
and never checks out or executes donor code, invokes Maven, or uses the network.
It preserves literal properties, parent dependencies, profiles/activation,
plugin executions/dependencies, repositories, deployment targets and `.mvn`
configuration. Findings are declarations requiring interpretation; they do not
establish effective Maven resolution, selected profiles or runtime dependencies.
Malformed POMs produce explicit diagnostics and a nonzero exit; they are retained
and accounted for, never repaired or silently excluded.

`acquisition.py` fails on missing, changed, duplicate or unsafe manifest paths.
A successful result states `build_ready: false`. It can recreate missing owned
Git archives only, from the exact source commits and verified origins:

```sh
python3 build-support/java/acquisition.py \
  --custody "$TASK_ROOT/source-archives/java-audit" \
  --restore-owned --owned-root "$TASK_ROOT"
```

Existing changed files are never overwritten. Restore research metadata,
Class B source archives and the declaration inventory from retained backup; the
manifest records URLs/hashes and the inventory can also be regenerated with the
auditor. No external resolver or install hook is invoked by recovery. The earlier
full-history Git bundles remain recorded in `source-archives/inventory.json`;
the selected source tar files do not replace those history backups. Archives
have not been represented as retaining any external LFS or submodule content.

## Before a Java build

1. Select the exact core and GeoNode extension profile set. Record deliberate
   exclusions against required product capabilities; a vanilla WAR is insufficient.
2. Resolve the printing snapshot/source ambiguity. The retained MapFish 2.4.1
   source is an **evaluation candidate**, not an accepted substitution. Its
   declared GeoTools 34.4 also needs alignment/compatibility evidence with 34.5.
3. Retain exact JDK/Maven distributions and their sources/licenses; obtain a
   complete effective Maven graph, including parent/BOM, plugin, test, classifier,
   platform and extension inputs, into a fresh isolated repository. Record every
   source/artifact URL, hash and license; never resolve moving snapshots for the
   acceptance build. No selected Java toolchain is currently retained here.
4. Inspect inherited Maven goals: `validate` binds source-formatting actions;
   build only in disposable owned-source copies with the recorded check/skip
   choice. Keep settings and local Maven repository task-local. Do not run
   `deploy`, inherited CI or donor integration download scripts.
5. Prove controlled artifact origins, a retained-input/network-denied rebuild,
   native tests and real loopback rendering/importer/OAuth/GeoFence/printing tests
   before any component or integration acceptance. Add real database, policy,
   publication/revoke and recovery tests for the product tasks.

Package checks run from `plan/` and are separate from Java/GIS tests:

```sh
cd plan
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

Use the retained `/tmp/ambisgis-validation-venv/bin/python` for strict schema
validation when the host Python lacks `jsonschema`; do not install globally.
