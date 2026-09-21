# Owned integrated frontend candidate

This bounded FND-02 recipe compiles the actual GeoNode client and its exact owned
MapStore gitlink. It does not start MapStore's independent Java catalog/backend.
The [completion checklist](../../plan/docs/fnd-02-completion.md) retains all four
original criteria and later-task boundaries. No production or release acceptance.

`inputs.json` binds the retained input manifest; `dependency-lock.json` is the
complete npm v3 replay lock. Original npm resolution and license/hook/binary
inventories remain at the hash-bound retained paths rather than duplicated here.
The two reviewed package substitutions are guarded in `build.py`: project master
→ local exact project archive; patcher master tarball → local exact patcher archive.
The actual transitive nomnom Git dependency is also retained at its observed
commit; its original manifest constraint stays recorded in the acquisition lock.
All resolved replay archive locations are local. No new public source forks.

## Acquisition and source audit

The acquired client is `7ca4822125b67999c97cb4aa1faa84b8a28eee9b`; its gitlink is
MapStore `0f3518737f29f4049b131247ce981e94519d9ab0`. Both come from already retained
owned Git bundles, including correct Git metadata for the native version plugins.
Helper project `a842cf070e07ce996bb81189cd6cb92c4d2d809f` and patcher
`34c9e799affd0f37875b6f9968d2b5a96ce5688a` were acquired from exact codeload URLs;
nomnom is `559dfcd9436b3beeeccdc0a4f28f0e3f988379ca`. Originals/notices remain intact.
The raw acquisition scripts/lock/logs are preserved under
`build-worktrees/frontend-completion/{acquire-bootstrap.py,prepare-first.py,acquire-01}`.
They are historical acquisition records, not commands to rerun over those paths.
`retain.py` converts that observed graph into verified local archives and a replay
lock; its allowlist refuses unknown Git or nonregistry origins.

Both owned packages already set `legacy-peer-deps=true`; this is inherited,
explicitly preserved compatibility behavior. No force, audit-fix, version update,
global npm install or unexplained peer suppression was introduced. The acquisition
command was `npm install --ignore-scripts --no-audit --no-fund` with a fresh local
cache; all replay commands use `npm ci --offline --ignore-scripts` with another
empty cache. The graph has 2,410 lock entries, 2,022 distinct registry archives and
2,403 packages installed on Linux. Optional platform entries remain retained.

The source's old Node 20 suggestion is EOL according to the current
[official support table](https://nodejs.org/en/about/previous-releases). Selected
Node 24.18.1 is in the supported 24 LTS line and is the
[July security release](https://nodejs.org/en/blog/release/v24.18.1), matching the
compatible retained host tool version. The official vulnerability index inspected
on 2026-09-21 lists July 29 as its latest security release; 24.21.0 is a newer LTS
feature release, so this is not a claim to the newest version. The selected
[official Linux archive](https://nodejs.org/dist/v24.18.1/SHASUMS256.txt) is verified
at SHA-256 `d6c664df3f3f61458e8c277585571328522d705166723a7c7823a9253a4d15a0`;
it includes npm 11.16.0. No signature-verification or full compiler-source rebuild
claim. Host shared libraries remain a recorded broader toolchain-closure limit.

Project's compile path runs local clean/version/webpack operations. Client
postCompile relocates fresh chunks, themes, translations and IFC assets into its
Python package static tree. MapStore's reviewed hook removes nested graticule
modules and copies the retained patched Mocha. It is executed explicitly under
network denial; dependency scripts remain disabled. Inventory includes every
advertised install/prepare hook: canvas's native binary download, Cesium's prepare
browser download, optional Darwin fsevents, protobuf and core-js hooks are not run.
Registry packages carry generated JavaScript and some WASM/native files; retained
archives/notices are not proof of independent third-party source rebuilds.

## Fresh build and replay

Run on the verified Linux x86-64 host through the established host bridge if the
IDE's tool sandbox cannot initialize. Never change host security configuration.

```sh
flatpak-spawn --host python3 build-support/frontend/build.py \
  --inputs /home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion/retained-01 \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion/build-NEW
```

Choose a genuinely fresh output. A preexisting attempt is never altered. The
manifest must enumerate every retained file; missing/duplicate/changed inputs or
symlinks fail closed. A new Node extraction, owned source recovery, empty npm
cache and node_modules are used. Checked-in dist/translations are removed before
compilation. The existing `postgis/offline_exec.py` denies Internet-family socket
creation for every install/hook/compiler process and descendants and records real
kernel probes. AF_UNIX/host files are accessible; this is the existing trusted-code
build control, not hostile-code isolation. No proxy or global cache supplies replay.

The receipt snapshots the executed recipe. All six native entry points must exist;
full output filenames/sizes/hashes are recorded in `output-manifest.json`.
`success.json` is created only after command, network proof, output and retained
input checks. Failure files/logs remain in the failed attempt. Native checks and
browser acceptance are separate from build success. Run the same command with a
second fresh output to demonstrate replay; compare actual output manifests before
making any byte-identity claim.

Package deprecation/security advisories and incomplete license metadata remain
review inputs. `audit_inputs.py` inspects actual retained package metadata/notices
without turning an SPDX declaration into legal clearance. Original GeoNode and
Java selection blockers remain on F02-06; broader retained-source/binary closure
remains FND-08. A required unusable or impermissible input still blocks selection.
