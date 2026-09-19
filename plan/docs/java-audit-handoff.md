# FND-02 Java audit — resumption record

The bounded Java dependency audit is on branch `fnd-02/java-dependency-audit` in
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java`, repository
`aloerch/ambisgis-platform` (ID `1376927351`). It starts from actual owner merge
`12bd2c5c88ab8573add1b483f1d53b4024649b39` of Jupyter PR #53. The previous
Jupyter handoff's open-PR observation is historical; its reviewed branch,
archives and runs remain preserved. FND-02 stays **In progress**.

This checkpoint is a source/dependency **audit**, not a retained transitive Maven
closure or completed Java build. No Java build/native/runtime test was started.

- Owned commits: GeoTools `aac73e9b89821331e77f67f1dd0921e541a78cfc`, GeoWebCache
  `59640420454b73f1e04e8409cc6ed43f4b24fed2`, GeoServer
  `e0673323400321c0f3409fbae68b4871dc328d8a`, GeoNode
  `a1db97e81dfc26c16bb4ee1a5d2b408877af66c9`.
- Audit custody: `/home/revelberry/Projects/AmbisGIS/source-archives/java-audit`;
  **70 recorded files / 902,064,509 bytes**, manifest SHA256
  `58afe0a757446e69e40ba3630f3361a464686254eca35ac691ef8cec4090957b`.
- Deterministic declaration inventory: **519 POMs / six Maven configurations**;
  SHA256 `e94d6d50282bd3222a49839f3fd1aa583e9a205c94a710242f873ed2ef019f80`.
  Actual audit exit **1** retains the malformed `src/maven/archetype/pom.xml`
  namespace diagnostic. Complete enumeration is not complete XML interpretation.
- **28 audit/custody + 175 package tests passed**, zero failures/errors/skips;
  strict plan checks and four schema/example checks passed. An initial host
  Python run skipped seven schema tests and strict validation failed for missing
  `jsonschema`; those outputs are retained separately. Final checks used the
  existing validation venv. Actual GWC source archive recovery matched its hash.
- Prior Jupyter custody was verified unchanged; database/Jupyter native/runtime
  checks were not repeated. Their results remain historical.

[Findings](java-dependency-audit.md), [machine evidence](../verification/java-dependency-audit.json),
[review](../verification/java-audit-review.txt), [ADR 002](../adrs/002-java-audit-before-build.md),
and [commands](../../build-support/java/README.md) retain exact limitations.

**Next ready FND-02 action:** retain exact JDK/Maven distributions/sources and
resolve the selected core/GeoNode extension graph into a fresh task-local Maven
repository. The current host PATH has no java/javac/mvn. Before builds, address
MapFish's `2.4-SNAPSHOT` source provenance or explicitly adopt/test a fixed-source
candidate; retained MapFish 2.4.1 is only an evaluation candidate and declares
GeoTools 34.4. Reconcile importer (used by GeoNode but absent from donor recipe),
WPS (donor recipe on / application default off), GeoFence PostgreSQL profiles,
OAuth and bootstrap configuration. The retained extension-recipe tree's license
provenance also needs review. Preserve all required capabilities and file notices.

Use separate source/build copies. Maven `validate` can mutate source via inherited
Spotless apply/POM sort. No inherited workflow or donor deployment namespace may
be used. Retain actual parent/BOM/plugin/test/native/source artifacts and hashes
before the acceptance build; a successful vanilla WAR does not establish GeoNode
compatibility. Client/MapStore and QGIS follow the recorded dependency graph.

GOV-02 is independently **In review** in [PR #52](https://github.com/aloerch/ambisgis-platform/pull/52),
branch `gov-02/saved-view-reconciliation`, head
`e19bc4960866d89c749e1d2d68427dd586130d2f`. The owner review filter is verified;
the unavailable roadmap picker instruction is withdrawn, with its exact UI
limitation retained for review. Delivery/Evidence changes were read back. The
remaining action is owner review of that PR; do not repeat settings or rerun the
importer. PR #52 remains open and unmerged.

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
TASK_GH=/tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh
cd "$TASK_ROOT/ambisgis-platform-java"
git status --short --branch
git remote -v
git log -2 --format='%H %s'
"$TASK_GH" api user --jq .login
"$TASK_GH" issue view 3 --repo aloerch/ambisgis-platform --comments
"$TASK_GH" pr list --repo aloerch/ambisgis-platform \
  --head fnd-02/java-dependency-audit --state all
python3 build-support/java/acquisition.py \
  --custody "$TASK_ROOT/source-archives/java-audit"
```

Verify retained tools before reuse. Git's inherited credential helper points to
absent `/usr/bin/gh`; pushes use the verified retained CLI via a per-command
helper override, without changing global credentials/configuration. No process
is left running. No PR merge, source-fork default, workflow, secret, deployment,
release or full-product acceptance was performed by this audit.
