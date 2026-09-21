# Separately identified frontend recipe replay

The F06-FE-RECIPE remediation uses the owner's 2026-09-21 prompt, course B.
PR #65 accepted the earlier consolidation; it did not authorize or accept these
new outputs. The original `frontend-completion/build-01` receipt binds inputs,
commands and output, but has no contemporaneous executed recipe snapshot/hash.
Later source commits and later build snapshots cannot recover that identity.
The original build and receipt remain unchanged.

From a reviewed platform revision, invoke the new wrapper on the verified host:

```sh
flatpak-spawn --host python3 -B build-support/frontend/replay.py \
  --inputs /home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion/retained-01 \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-qgis-remediation/frontend/replay-NEW
```

The wrapper requires a fresh attempt. It copies the reviewed frontend, PostgreSQL
build-denial, GeoNode and Java runtime tooling into `frozen-platform`, binds every
file, then executes **that copy** of `frontend/build.py`. Existing source, reviewed
input, lock, offline install/build and complete output guards remain authoritative.
The frozen tree must match before and after execution; command or integrity failure
makes `replay-result.json` fail and preserves logs. Source checkout, Node extraction,
npm cache, node_modules and generated output are fresh. Native/browser tooling is
included for a subsequent exact invocation; this wrapper's build success alone
does not accept native tests, browser behavior or distribution.

Use `frozen-platform/build-support/frontend/native_tests.py` with the new build's
client and Node paths, the retained sandboxed Chromium and a fresh test output.
Keep nonmutating lint failures visible. Use the frozen `frontend/smoke.py` with
the new static MapStore tree and `build/output-manifest.json` to stage the actual
compiled artifacts through the real owned backend. The existing smoke verifies
all loaded MapStore responses, public WMS rendering, zoom/reload and one service
restart, plus network proof, credential invalidation, secret scrubbing and cleanup.
Afterward verify `tooling-manifest.json` again; generated files or changed tooling
must fail the evidence. The established PostgreSQL-only exception remains explicit.

Raw before/after manifests, source-package patches and exact IFC asset comparisons
must be retained. Differing build paths or webpack fullhashes are not silently
normalized into byte equality. Any changed IFC/WASM/API bytes require affected
real IFC checks; unchanged same-version assets keep their separate source/notice
finding and do not imply full 3D product acceptance.
