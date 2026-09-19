# FND-02 Java resolution — resumption record

Worktree: `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-resolution`.
Repository: `aloerch/ambisgis-platform` (ID `1376927351`). Branch:
`fnd-02/java-toolchain-resolution`, based on audit head
`c2ec4bfd37ba1afa789330972f103d0e6c977fdf` of open [PR #54](https://github.com/aloerch/ambisgis-platform/pull/54).
The new checkpoint is in **[PR #55](https://github.com/aloerch/ambisgis-platform/pull/55), open and unmerged**, stacked on PR #54.
Implemented/tested checkpoint commit: `48b95a984dcf04ff52f4611f90e6219c6ad723cb`.
Later commits record publication/Project evidence only; verify the current review
head with `gh pr view 55 --repo aloerch/ambisgis-platform --json state,headRefOid`.
FND-02 Evidence now links PR #55; Delivery remains In progress, with readback in
[the Project receipt](../verification/java-resolution-project-evidence.json).
The prior audit branch, archives and evidence are preserved. FND-02 remains
**In progress**; this is toolchain/input resolution, not a Java build acceptance.

Read [checkpoint evidence](java-resolution-evidence.md),
[machine results](../verification/java-resolution.json),
[ADR 003](../adrs/003-java-resolution-candidate.md), and
[reproduction commands](../../build-support/java/README.md).

Exact owned sources remain GeoTools `aac73e9b89821331e77f67f1dd0921e541a78cfc`,
GeoWebCache `59640420454b73f1e04e8409cc6ed43f4b24fed2`, GeoServer
`e0673323400321c0f3409fbae68b4871dc328d8a` and audited GeoNode
`a1db97e81dfc26c16bb4ee1a5d2b408877af66c9`. MapFish 2.4.1 and GeoFence 3.8.3
remain Class B evaluation candidates with exact source identities in ADR 003.

Custody is under `/home/revelberry/Projects/AmbisGIS/source-archives/java-resolution`.
The toolchain is Temurin 17.0.20.1+1 and Maven 3.9.16, retained with publisher
sources and original notices. Checksums and installed-tree verification passed;
trusted signature verification and complete bootstrap/native closure remain open.
The frozen snapshot verifies **34,118 files / 1,682,220,066 bytes**, manifest
SHA256 `2a9cc548d2d7709e39c6bef547e9befa7176a897fa6859a8bb7bae2ed14c7f07`.
Both network-denied model/dependency replays passed; all 157 selected dependency
modules succeeded from 9,142 retained mirror files. **140 tooling + 175 package
tests** and strict/four schema checks passed without failures/skips. The final
source inventory exits **2** with 64 missing classifiers; full source closure
is not complete. The earlier `java-audit` custody is unchanged. Actual source classifiers, parent/
BOM/plugin/test inputs, schema resources, notices and failures are retained with
hashes; remaining source gaps are never treated as source-built binaries.

Prepared source and fresh Maven repositories are under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-resolution`.
Use new run IDs/output directories and separate source/build copies. Maven
`validate` can modify POM/source formatting; do not introduce lifecycle goals as
a way to resolve dependencies. Do not reuse inherited workflows or donor
namespaces. Keep source archives and all failed run receipts intact.

**Next ready action:** complete the recorded source/provenance gaps and explicit
extension/profile decisions before the owned Java acceptance build. Prioritize
missing sources used by selected referencing/XML/importer, GeoFence/PostgreSQL
and test paths; then account for remaining plugin/application transitives. Review
schema file-level rights and offline repackaging, MapFish 2.4.1 compatibility,
GeoFence GeoTools alignment, SLF4J 1.x/2.x mediation/bindings, WPS, OAuth and bootstrap assets. Preserve all
required capabilities. Client/MapStore and QGIS follow the dependency graph.

GOV-02 PR #52 was owner-merged at
`fc77ab978e567ce5d55e3428d1249a3b332da09d` on 2026-09-19T21:54:27Z; the older
handoff's open/in-review state is historical. This Java session did not alter
its settings or rerun the importer. Database/Jupyter native/runtime results also
remain historical and were not repeated.

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
TASK_GH=/tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh
cd "$TASK_ROOT/ambisgis-platform-java-resolution"
git status --short --branch
git remote -v
git log -2 --format='%H %s'
"$TASK_GH" api user --jq .login
"$TASK_GH" issue view 3 --repo aloerch/ambisgis-platform --comments
"$TASK_GH" pr list --repo aloerch/ambisgis-platform \
  --head fnd-02/java-toolchain-resolution --state all
python3 build-support/java/toolchain.py \
  --custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --verify-extracted "$TASK_ROOT/build-worktrees/java-resolution/toolchain"
python3 build-support/java/acquisition.py \
  --custody "$TASK_ROOT/source-archives/java-resolution" \
  --manifest "$TASK_ROOT/source-archives/java-resolution/custody-snapshot-01.json"
```

Verify the retained CLI before reuse: archive SHA256
`9bca2d1c16825f109907a23307628a2f0698fbf99662b73a5cf0b020293072b8`,
binary SHA256 `ea857a3f0f7d4276cf5848b236542c5048e2eaa7bdd1b6ddec238f8793e74bff`.
Git's inherited credential helper points to absent `/usr/bin/gh`; use the verified
CLI via a per-command helper override. Global credentials/configuration remain
unchanged. No task process remains running. No Java compilation/native/runtime test, deployment, release or
full-product acceptance was performed by this checkpoint.
