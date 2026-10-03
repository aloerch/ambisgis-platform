# FND-07 GeoTools local publication repair

The [owner decision](https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863464446)
authorizes this local repair, and explicitly withholds GeoTools publication.
The final candidate is commit `3363c3d4ae8adfe3ed2024c27f92ec63855093be`,
tree `ebb65f687763ce40445eb02f6ce710dc1eaa1e00`, in
`aloerch/ambisgis-geotools` (ID `1376927869`). It remains local only.

The [receipt](../verification/canonical-and-publication-repairs/geotools-receipt.json)
is a source-publication sidecar to accepted FND-02 manifest
`0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99`.
The manifest, original source receipts and built artifacts remain unchanged.
The sidecar does not redefine the accepted functional candidate or claim that
previously executed source contained the new notices. Future builds acquire
new artifact identities under FND-08.

## Exact change and source history

The [two-file patch](../verification/canonical-and-publication-repairs/geotools-notices.patch)
adds one prominent XML comment after each original header and before `<project>`:

| File | Recorded functional change | Evidence |
|---|---|---|
| `build/maven/xmlcodegen/pom.xml` | EMF common/ecore dependency management at 2.15.0, recorded September 20 | Platform commit `d229468e1cef44f81d9be837068e0a80166b7eb7` |
| `modules/plugin/imagemosaic/pom.xml` | Oracle-only test dependency and unused provided ojdbc14 removed, recorded September 21 | Platform commit `e1b960588c51beb35f83c5f1c5d137e85a0d414c` |

Both notices separately record accepted-source materialization on
`2026-09-22` (UTC−07:00) and actual notice addition on `2026-09-28` (UTC).
The new commit has honest execution-time metadata. All original copyright,
license and attribution text remains, including the original LGPL terms.
No license version is converted and no copyright is reassigned.

| Source | Commit | Parent / interpretation |
|---|---|---|
| Accepted original base | `aac73e9b89821331e77f67f1dd0921e541a78cfc` | Tree `acfbe55e74aa9cc9d1134fadeefc4218390ad9ad`; original history retained |
| Previously held product | `f51fa68803c465f28a85c155e3e951df0d8788f7` | Direct child of accepted base; tree `60750f787dabf1a08e646e7d5f3f1497e560e94e`; preserved unchanged in prior custody |
| Notice-corrected publication candidate | `3363c3d4ae8adfe3ed2024c27f92ec63855093be` | Separate direct child of accepted base; tree `ebb65f687763ce40445eb02f6ce710dc1eaa1e00` |

The candidate replays precisely the previously accepted functional delta plus
these notices. Its only newly reachable commit relative to the accepted base
is the new candidate itself. The old unnotified modified product commit is
not an ancestor. No existing history/ref was rewritten or deleted.

All **17,920 tracked entries** were compared with the old product tree:
**17,918 are identical**, including modes and Git objects; only these two
POM blobs differ. Removing each exact inserted comment reproduces its old
file byte for byte. The parsed XML elements, attributes, text and configuration
are equal. No executable source, dependency value, build choice or behavior changes.

## Actual verification and retained recovery

[Execution evidence](../verification/canonical-and-publication-repairs/geotools-evidence.json)
binds the recipe, receipt, tools, tests, private outputs and the original first run.
Sixteen targeted tests passed without failures/errors/skips. They cover wrong
source/hash/date/authority, unsafe XML, missing/extra files, altered modes/notices,
changed configuration, incorrect ancestry, mutated receipts, a bad patch with a
recomputed checksum, recovery/proposal scope tampering, and final-check failure.
A failed final integrity check emits a failure record without a success receipt.
A real `git apply --check` also passed against the exact old product.

The retained Temurin `17.0.20.1+1` and Maven `3.9.16` distributions were verified
against their custody archives before use. One Java compiler invocation and four
strict Maven model parser/writer invocations passed with Internet sockets denied.
The serialized before/after models matched exactly for both files. Combined with
the complete source-tree comparison, this proves unchanged Maven configuration
inputs. No effective-POM resolver, dependency acquisition, Maven lifecycle,
Java service package, native suite or runtime suite was executed.
No byte-identical rebuilt package is claimed.

The candidate and recovered source have separate complete object stores, with
no alternates, shared objects, hooks, filters or donor fallback. Fresh recovery
unbundled the original retained base archive and the new exact delta, checked
its predecessor, checked out the candidate, passed `git fsck`, and repeated the
complete source/notice/ancestry comparison. The private bundle chain is:

- Base: `/home/revelberry/Projects/AmbisGIS/source-archives/ambisgis-geotools-9a4f847e8b83.bundle`,
  SHA256 `c738143f1179d2a8964e11f84bfa84a24c463c95cef4e9c459b31d8b37454212`.
- Delta: `/home/revelberry/Projects/AmbisGIS/build-worktrees/canonical-and-publication-repairs/run-002/geotools-v2/geotools-notices.bundle`,
  1,855 bytes, SHA256 `58563222303ed0122b1843cd0101b73282b89e944651eaed022d6534f45e9db5`,
  with sole prerequisite `aac73e9b89821331e77f67f1dd0921e541a78cfc`.

These bundles remain private custody and are not uploaded with the platform PR.
The new bundle does not require the old modified product delta.
Original donor notices and all other source files remain in their original history.

An initial successful source/model/recovery run remains under `run-002/geotools`,
with its original producer recipe separately retained. Independent review found
that its final verifier trusted some mutable receipt fields and a receipt-provided
patch hash. The strengthened recipe requires an external frozen receipt digest,
reconstructs the exact patch, checks recovery and proposal scope, and writes a
success receipt only after final integrity checks. It ran again from fresh stores
under `run-002/geotools-v2`. Only the latter commit is proposed. Both runs have the
same corrected source tree; neither old run nor old receipt was edited.

## Finite next owner decision

The recorded LGPL-2.1 section 2(b) hold concerned missing prominent file-specific
change/date notices. Both modified files now carry those notices, with original
license/copyright text preserved and no unnotified modified product ancestor
introduced by this proposed ref. This is the scoped basis for subsequent source
review; remaining applicable rights and distribution obligations are not waived.

Approve creation only of these absent refs in repository ID `1376927869`, both
at commit `3363c3d4ae8adfe3ed2024c27f92ec63855093be`, tree
`ebb65f687763ce40445eb02f6ce710dc1eaa1e00`:

- Review: `refs/heads/ambisgis/review/fnd-07-notices-v1`.
- Canonical: `refs/heads/ambisgis/main`.

The [fresh read-only observation](../verification/canonical-and-publication-repairs/geotools-remote-preflight.json)
at `2026-09-28T04:52:24.553477+00:00` found both refs absent; the older held
`ambisgis/review/fnd-07-baseline-v4` ref was also absent. Default `main` remains
`9a4f847e8b83875169e279999659052a0cc2bf14` and Actions is disabled.
Preserve all defaults/refs/settings, recheck this state before any later approved
write, treat exact existing refs as no-ops and different refs as collisions.
This run made zero GeoTools remote writes. Final FND-07 acceptance remains pending;
FND-08 has not started.

## Exact resume commands

From the integrated platform checkout, inspect help before use:

```sh
python3 build-support/source_publication/geotools_notice.py --help
python3 build-support/source_publication/geotools_notice.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS \
  --authorization plan/verification/canonical-and-publication-repairs/authorization.json \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/canonical-and-publication-repairs/run-002/geotools-v2 \
  --receipt-sha256 5fe6003847a95da95a280a958b1e27fdbf0ecd43a219251e257827c46534a2f8 \
  --verify
python3 -m unittest discover -s plan/tests -p test_geotools_publication.py -v
```

The receipt digest is frozen independently in the platform evidence. Verification
recomputes source membership, exact patch/model bytes, ancestry and bundle identity;
a subprocess zero exit cannot override a failed integrity check. New preparation
requires a new empty output and the retained `build-support/postgis/offline_exec.py`
wrapper shown in the execution evidence. A fresh preparation creates a newly dated
commit requiring its own exact review. No command here publishes a source ref.
