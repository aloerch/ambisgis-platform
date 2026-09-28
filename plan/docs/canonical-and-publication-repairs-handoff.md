# FND-07 canonical delivery and local publication repairs

Repository `aloerch/ambisgis-platform` (ID `1376927351`), branch
`fnd-07/canonical-and-publication-repairs`, based on current verified main
`0df95126d9fecd9df3cf1fd0cd88ab565a680989`. This is PR #70's owner merge,
with reviewed head `7d5ceb06f7a1814d4a95b7e4b05a2b46d8728720` as a direct parent.
Worktree: `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-canonical-and-publication-repairs`.
The checkpoint PR and final head are recorded in the live issue #6 delivery comment.

## Owner actions

Nine exact canonical refs are delivered and independently verified. Unchanged
reapplication made **zero source-ref and zero settings mutation attempts**.
GeoTools and QGIS now have exact, tested **local-only** source successors for review.
Neither old nor changed source ref in either held fork was published.

The [live owner authorization](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863464446)
was read directly, by `aloerch` (ID `15285626`), created/updated
`2026-09-28T04:35:51Z`; body SHA256
`87d79df2d4458d9570c269ff9d20310c4117f7d82c2dc23d4588ca505900da1f`.
The previous missing-comment gate is resolved. This decision is distinct from
old comment `5850316210` and from the unposted run-001 draft.
The [frozen authorization](../verification/canonical-and-publication-repairs/authorization.json)
preserves its actual text and metadata.

The next finite decision is the [combined changed-source publication proposal](../verification/canonical-and-publication-repairs/next-source-publication.json):
approve the exact two successors and creation-only review/canonical destinations,
with defaults and disabled Actions preserved. QGIS approval must explicitly
accept the narrow clean-snapshot boundary on the existing fork, or withhold its
publication pending a separate hosting disposition. No existing public branches,
tags or GitHub fork-network objects were purged or certified clean. A new public
repository, history rewrite, archive/binary release, PR merge, final FND-07
acceptance and FND-08 execution are outside this session's authorization.

## Canonical operations and actual recovery

The immutable canonical proposal itself hashes to
`519dd189533c6d077648f0b9bbf1f98e052e28d4d614414b6c04f141deb0d28d`.
Its `plan_sha256` field instead refers to the original promotion plan,
`a9477bbdcab4f85fad69cbf77ed04ed76de92efd63d3d663054bda34e4b573a6`.
Neither original file was edited. The distinct `--canonical` operation binds
both documents, the real decision and precisely these nine eligible IDs.

Every destination below is `refs/heads/ambisgis/main`. The exact prior review refs
remain intact; defaults retain their prior names and commits; Actions remains
disabled. Each mutation used GitHub's creation-only `POST /git/refs` endpoint,
never ref update, fast-forward, force push or settings mutation. Live review
commit/tree, public companion bytes, owner/repository identities, Actions and
visible executions were rechecked before creation. MapStore was created and
verified before its client. All nine server creation responses were received;
there were no uncertain responses or retries.

| Root | Repository ID | Exact commit | Exact tree | Result |
|---|---|---|---|---|
| postgresql | 1376927644 | `2ff1375b5dd8bf09d8cb0e795974528180fd75ca` | `598df31816bda464f5b904c0badbcb25bafcc4f1` | created / exact replay |
| postgis | 1376927690 | `9816f82458db774e62906cfb2c4f01f8b262c862` | `ee927efacdc5a00d698cab2da047ad2232d1f579` | created / exact replay |
| jupyterhub | 1376927753 | `129e6b0a06dcf1aa17b580bf0f0a61dfd9dbce3a` | `a9ab20c5ff0641870194d666fcd1516ee2f2d65e` | created / exact replay |
| jupyterlab | 1376927783 | `e7255a9334c12ad8f9cb15db27584215fab5ece2` | `0edadc56fb04f944097c0658a9a51686ba68bd16` | created / exact replay |
| geowebcache | 1376927892 | `b4e9a30c8e2be00b9aa87fb17324efa8e489ac22` | `8df655d13b9955776fe1532dfb27fac64612a772` | created / exact replay |
| geoserver | 1376927947 | `fd2fe1dfcc78fa974bdb81673872879336312077` | `c12018e88493a351c60c370f2a43894701acf995` | created / exact replay |
| geonode | 1376927978 | `2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4` | `f8fda01733dae258e319df14f42677cf3bd83e20` | created / exact replay |
| mapstore-client | 1376928013 | `a0d3f434cea69dadc93d35e13bc969b844aceea1` | `8055ca37333ee3037f63624f2e1d6ee548d416f1` | created / exact replay |
| mapstore | 1376928043 | `88064efbf20ef0aaffebe357f7a99a1ab4fb23b8` | `11b6eb8616b90c72570c4f3aad82212b52f1cdbe` | created / exact replay |

The [canonical receipt summary](../verification/canonical-and-publication-repairs/canonical-delivery.json)
links actual apply and unchanged replay journals. The first read-only preflight
reported eight ready rows and held the client specifically because MapStore's
canonical ref was not yet present; no writes occurred. Actual apply then ordered
the child before the client and passed all nine rows. Reapply passed with nine
already-exact results and zero mutation-attempt events.

A complete before/after ref comparison on all eleven forks found only these nine
additions: no prior branch/tag/ref changed or disappeared, and no relevant setting
changed. Raw inventories remain private in run-002; the publishable
[comparison](../verification/canonical-and-publication-repairs/source-state-comparison.json)
binds their hashes and per-root results. Visible hooks, Actions runs and selected
commit checks/statuses were empty; this does not assert knowledge of invisible
third-party integrations. Platform/account settings, protections, secrets and
workflows were untouched.

The [fresh remote recovery](../verification/canonical-and-publication-repairs/canonical-remote-delivery.json)
fetched each complete source tip into a new independent **depth-one** store,
using only its owned HTTPS remote. All nine exact commit/tree identities, 59
original notice paths and `git fsck` checks passed without alternates, hardlinks,
promisor objects or donor fallback. Full ancestry and functional-diff recovery
were deliberately reused from PR #70's same-object receipt SHA256
`ea237c635a6990d739ffe1cb9fe191e2f506c947f33400f286b3586822389e90`;
this session does not claim nine new full-history recoveries.

The client's unchanged `.gitmodules` still names the donor URL. Both promotion
and fresh verification used the documented process-only mapping from
`https://github.com/geosolutions-it/MapStore2.git` to
`https://github.com/aloerch/ambisgis-mapstore.git`, and verified the exact gitlink
`88064efbf20ef0aaffebe357f7a99a1ab4fb23b8`. Ordinary donor-recursive cloning is
not represented as self-contained. No `.gitmodules` source was edited.

The [delivery announcement](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863702485)
links the nine new canonical endpoints to the existing immutable
[source-publication companion and original notices](https://github.com/aloerch/ambisgis-platform/blob/936e37d6be25decc89ceb3d4b8c1be60c61de9ed/plan/verification/source-ref-promotion/publication-rights.md).
Those public bytes were reverified before each creation. Original notice texts,
GPL/LGPL conditions and Web-IFC covered-source availability remain applicable;
no new archive/binary distribution is claimed.

## Two local source proposals

| Root | Local commit | Local tree | Proposed review ref |
|---|---|---|---|
| GeoTools | `3363c3d4ae8adfe3ed2024c27f92ec63855093be` | `ebb65f687763ce40445eb02f6ce710dc1eaa1e00` | `refs/heads/ambisgis/review/fnd-07-notices-v1` |
| QGIS | `86af40542b219b0da6df1a43914413443330c0c0` | `84ea1b18fdf5721819fee34fe06cdef7ea82afdc` | `refs/heads/ambisgis/review/fnd-07-publication-snapshot-v1` |

Both also propose `refs/heads/ambisgis/main` at the same respective identity,
subject to a subsequent exact owner decision and fresh absence/settings checks.
The unchanged accepted FND-02 manifest SHA256 remains
`0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99`.
These sidecars map publication-only source deltas to that accepted functional
composition. They neither replace the manifest nor retroactively change old
source, test receipts or artifact identities. Future corrected-source builds
receive their own artifact identities under FND-08.

[GeoTools details and resume commands](geotools-publication-repair.md): two accurate
XML notice insertions preserve every other byte and all 17,918 other entries.
Historical functional dates, September 22 materialization and September 28 UTC
notice addition are distinguished. XML configuration and actual retained Maven
strict-model output are equal. The corrected commit directly parents the original
accepted base, avoiding the previously unpublished unnotified modified product
ancestor; old source/history stays retained. The exact new delta plus original
base bundle restored into an independent repository with Internet sockets denied.
Sixteen guards, exact patch verification and final trusted-receipt checks pass.
The recorded two-file LGPL modification-notice condition is addressed; original
terms and all remaining obligations are preserved.

[QGIS details, ADR and resume commands](qgis-publication-snapshot.md): the new
isolated parentless source has 32,451 entries and exactly 32,995 stored/reachable
objects. It omits precisely 1,130 palette paths, changes 19 catalogues to remove
107 references, retains 265 ColorBrewer palettes and all 84 affected original
metadata/notice files, and adds explicit source provenance/notices. Complete
original-file/mode/blob mapping is retained inside the local source candidate;
original complete history remains separately under its actual custody constraints.
No unrelated executable/provider/Python/CMake input changed.

The self-contained 209,753,585-byte QGIS bundle restored into a fresh isolated
repository; no excluded object, extra parent/ref, alternate, shared object, hook,
filter or donor download supplied it. Of 4,370 accepted resource/notice entries,
4,351 are byte-identical and 19 differ only by XML modification comments; one new
publication notice is added. XML behavior, all ColorBrewer bytes and original
notices compare exactly. The strict new `publication_selection.py` adapter rejects
partial/missing/corrupt stages and replays without mutation. The original
`resource_selection.py` remains byte-for-byte unchanged, preserving accepted
source-restoration hash guards. Native/runtime tests are reused only within these
unchanged input/behavior bounds; no large QGIS or Java rebuild occurred.

The QGIS snapshot addresses the identified palette-source hold for its own
reachable content. It does not remove or certify content exposed by other refs
or the existing fork network. The owner may approve this bounded source ref on
that documented basis or withhold QGIS delivery for a separate hosting decision;
this work does not silently create another public repository.

## Verification, failures and review

Current integrated test results, exact commands and hashes are recorded in
[validation.json](../verification/canonical-and-publication-repairs/validation.json).
The run-001 346-test baseline remains historical and was not substituted for
implementation. New canonical/race/settings/interruption guards, actual remote
creation/replay/recovery, both local repaired-source recoveries and final
source/resource integrity checks are separate evidence categories. Candidate
eligibility can remain exit 2 for later ungranted gates; no permission was invented.
Fresh integrated package validation passes **415 tests with zero failures/errors/skips**
and four schemas. Candidate integrity/report and both trusted repaired-source
verifiers pass; eligibility retains exit 2. Package/schema checks are not GIS
product acceptance.

[Independent engineering review](../verification/canonical-and-publication-repairs/independent-review.json)
is bound to the final recipe/verifier hashes and has no unresolved material
engineering finding. Earlier QGIS quoting failure, preliminary local snapshots,
and the first GeoTools producer remain retained under fresh names. Material
review fixes strengthened receipt/patch/final-success checks, made QGIS verification
refuse missing retained stages, and separated its adapter to preserve accepted
recipe hashes. No unsuccessful attempt was relabeled successful. Exact original
POM whitespace in the permitted patch is preserved; its documented whitespace
warnings are not silently fixed by changing source/license context.

A [final integration review](../verification/canonical-and-publication-repairs/final-integration-review.json)
independently recomputed all-eleven ref preservation and exact nine creation/replay
results, checked both successor identities/parents and immutable legacy inputs,
and found no prohibited source payload or unresolved material integration issue.
[Preservation evidence](../verification/canonical-and-publication-repairs/preserved-checkpoints.json)
confirms all 32 run-001 file hashes and the untouched original plan user edit.

## Original task criteria and next work

1. **Owned source revision and retained baseline:** all eleven original sources
   remain retained; nine canonical refs now resolve exactly and recover; the two
   tested successors remain local pending changed-source review and delivery.
2. **No copyright reassignment or blanket relicensing:** original terms/notices
   stay preserved. The two bounded repairs address their stated source holds;
   no blanket clearance, distribution release or existing-history purge is claimed.
3. **Required additional assets enumerated; nulls remain blockers:** accepted asset
   inventory and custody receipts stay intact. New sidecars enumerate precise
   notice/resource changes, source histories and bundle identities; no missing
   payload receives an invented identity.

Final FND-07 acceptance requires the remaining source delivery and explicit owner
decision against these unchanged criteria. FND-02 remains accepted/Merged, FND-07
remains open for review, and FND-08 remains unstarted. Full build/drift checks and
OWN-02 repair qualification remain outside this batch. Next task is this same
FND-07 exact changed-source publication decision, not a new milestone.

## Retained commands

Use the host namespace (`flatpak-spawn --host sh` from the IDE), the integrated
worktree, and the retained Python environment:

```sh
export PATH=/home/revelberry/Projects/AmbisGIS/build-worktrees/jupyter-slice/run-002/hub-env/bin:$PATH
cd /home/revelberry/Projects/AmbisGIS/ambisgis-platform-canonical-and-publication-repairs/plan
python3 tools/promote_source_refs.py --help
python3 tools/promote_source_refs.py --canonical --workspace-root /home/revelberry/Projects/AmbisGIS --authorization verification/canonical-and-publication-repairs/authorization.json --publication-evidence verification/source-ref-promotion/publication-evidence.json --publication-sha256 0133d14729dac54a7680418b4f54977f0a6d607992cbe3bd5cfdcbb794aecf84 --receipt /home/revelberry/Projects/AmbisGIS/build-worktrees/canonical-and-publication-repairs/run-002/resume-preflight-01.jsonl
```

The command is read-only; choose a new receipt filename. The authorized unchanged
`--apply` is already proven zero-write. The exact successful apply/replay command
records and full independent stores remain in run-002. To investigate actual
remote corruption, `verify_canonical_delivery.py --help` documents the independent
fetch command; use a fresh output and do not repeat large histories without cause.
The two component handoffs give trusted-receipt local verification commands.
No command in this handoff authorizes a changed GeoTools/QGIS source push.
