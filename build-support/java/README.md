# FND-02 Java audit and dependency-input resolution

This retains a source/dependency audit and bounded toolchain/input resolution,
**not a complete Maven dependency lock, Java build, distribution, or runtime acceptance**. The selected owned roots are
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
   acceptance build. The selected JDK/Maven custody checkpoint is linked below; full source/build closure remains open.
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

## Toolchain and effective dependency resolution

The FND-02 resolution checkpoint is implemented by `toolchain.py`, `resolution.py`,
`maven_proxy.py`, `replay_model.py` and `resolution_inventory.py`. See
[toolchain custody](toolchain.md) and [ADR 003](../../plan/adrs/003-java-resolution-candidate.md).
The audit manifest above remains unchanged. The new work uses separate
`source-archives/java-resolution` custody and `build-worktrees/java-resolution`
source/repository copies. All commands below are explicit acquisition or model
operations; none compiles, packages, installs, deploys or runs Java tests.

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
TASK_TOOLS="$TASK_ROOT/build-worktrees/java-resolution/toolchain"
TASK_WORK="$TASK_ROOT/build-worktrees/java-resolution/new-resolution"
python3 build-support/java/toolchain.py \
  --custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --verify-extracted "$TASK_TOOLS"
python3 build-support/java/resolution.py prepare \
  --audit-custody "$TASK_ROOT/source-archives/java-audit" --work "$TASK_WORK"
python3 build-support/java/resolution.py effective --work "$TASK_WORK" \
  --custody "$TASK_ROOT/source-archives/java-resolution/maven" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --java "$TASK_TOOLS/jdk-17.0.20.1+1" \
  --maven "$TASK_TOOLS/apache-maven-3.9.16" --run-id model-01
```

Use `dependencies` instead of `effective` with another new run ID to invoke the
pinned Maven dependency plugin's `go-offline` goal. It resolves build/report
plugins and their dependencies as well as selected application inputs; it never
executes those plugins' lifecycle goals. An unsuccessful reactor run preserves
its true exit and skipped-project diagnostics. `--offline` permits only retained
proxy bytes; it is not a process network restriction.

All Maven resolution passes use fresh local repositories. Task-local settings
mirror every declared repository through a loopback acquisition proxy with only
Central and the OSGeo release repository allowed. Successful bytes, original and
final URLs, SHA256, size and repository identity are retained before Maven sees
them. First acquired origins and discovery metadata are frozen. Snapshots,
moving version aliases and donor core binaries are refused. The 19 exact
reviewed schema data archives in ADR 003 are allowed only after their actual ZIP
contents pass the source-resource validator; no executable core code is allowed. Metadata retention
is not source-build evidence. No inherited `.mvn`, user settings, credentials,
Maven/JVM environment options or mavenrc are accepted outside the recorded source
and toolchain configuration. Required source/configuration files are checked
before and after each invocation.

For a model replay using a file mirror, a fresh local repository, and actual
Linux x86-64 Internet socket denial:

```sh
python3 build-support/java/replay_model.py --work "$TASK_WORK" \
  --custody "$TASK_ROOT/source-archives/java-resolution/maven" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --tools "$TASK_TOOLS" \
  --output "$TASK_ROOT/build-worktrees/java-resolution/new-model-replay"
```

Add `--stage dependencies` with another fresh output directory to replay the
pinned dependency-acquisition goal against the same retained file mirror.
This also runs no lifecycle build.

The existing process-local seccomp runner records live AF_INET/AF_INET6 denial
probes. It does not isolate host files/tools or Unix-domain services. A successful run proves replay of the selected model or dependency-acquisition
goal from retained inputs, not a compiled Java or GIS offline rebuild.

`resolution_inventory.py --custody PATH --output NEW_FILE` verifies Maven custody
and reports POM-declared licenses, original notice bytes and candidate source
coverage. `--acquire-sources` deliberately fetches fixed GAV source classifiers
and POMs from each binary's recorded origin. Exit 2 means retained inputs pass
integrity verification but source/POM gaps remain. Source classifiers may omit
test/native sources; their retention never establishes source-to-binary identity
or license approval. Stop acquisition before taking a final inventory snapshot.

Primary goal references: [Maven effective POM](https://maven.apache.org/plugins/maven-help-plugin/effective-pom-mojo.html)
and [Maven go-offline](https://maven.apache.org/plugins/maven-dependency-plugin/go-offline-mojo.html).
