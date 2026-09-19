# FND-02 owned Jupyter candidate/runtime evidence

The bounded Jupyter slice is implemented and reviewable. A clean retained-input
build produced owned Hub 6.0.1 and Lab 4.6.3 wheels, including their frontend builds;
329 selected native tests passed with no failures/skips. Two independent fresh-state
runtime probes passed standalone Lab and Hub → proxy → single-user launch, real
kernel execution, notebook save/reopen, authentication denial and orderly shutdown.
FND-02 stays **In progress**. This is an experimental development checkpoint, not
canonical baseline, license/security, FND-07/FND-08, P1 or P6 acceptance.

## Source and artifact identities

Repository `aloerch/ambisgis-platform` (ID 1376927351), branch
`fnd-02/jupyter-runtime`, based on actual PR #51 merge
`a3c2e2e696ea11bdc10c2ad202a240fbd0137f45`. PR #51's frozen reviewed head was
`1c3a9b7f85c45cb8f00ac2ebe70041b2fbd755b9`; no new work was added to it.
The source fork defaults and retained donor history were preserved.

| Owned root | Tag object | Peeled source commit |
|---|---|---|
| Hub 6.0.1, repository ID 1376927753 | `65de9c630531e0ac7630f6da166e91c54726e0af` | `3e516c6f382b481e815ec455befb2f14d80d337b` |
| Lab v4.6.3, repository ID 1376927783 | `9c81bd1442601ba5c6b20bbd46678b5b236d2721` | `e7255a9334c12ad8f9cb15db27584215fab5ece2` |

Final Hub wheel SHA256: `e3c8ddb0b8307e54debddc75af2ffc1fc59d690fa3cf987693da09e404d5a277`.
Final Lab wheel SHA256: `98c21e3a6a98e011418ad5d586f3679fdfe942254dd1ac1e3d1f4f10147b8d02`.
They were built locally from the owned exports; neither was downloaded from PyPI.
The runtime proves exact local wheel origins/versions, module bytes and all 418
installed Lab static assets against those wheels. Runtime versions include Server
2.21.1, ipykernel7.3.0, client8.10.0, websocket-client1.9.2, proxy5.3.0,
Node24.21.0/npm11.19.0 and host Python3.13.15. Hub and user servers use separate
venvs; GeoNode/spatial profiles are not forced into either environment.

[Machine evidence](../verification/jupyter-slice.json) links command/log/artifact
hashes and exact retained report locations. [Input manifest](../../build-support/jupyter/inputs.json),
[dependency/license lock](../../build-support/jupyter/dependency-lock.json),
[candidate/security/hook audit](../../build-support/jupyter/dependency-audit.md),
[executable recipes](../../build-support/jupyter/README.md) and
[handoff](jupyter-slice-handoff.md) support review and reproduction.

## Custody, build and repair boundaries

The local store `source-archives/jupyter-slice` contains **5,510 recorded files /
817,990,927 bytes**, including 146 Python dependency distributions with matching
sdists, 2,830 JavaScript distribution records across the npm/Yarn graphs, and
3,522 original notice records / 1,156 unique notice bodies. Counts include
cross-graph duplication and optional/unselected platform variants. Twenty-four
Python and eight JavaScript distribution records contain native/binary members;
these counts include bundled non-Linux launchers/variants and WebAssembly.

Hub and Lab are source-built owned roots. Linux-PAM1.7.2 supplies only locally
source-built libpam/libpam_misc for imports in tests/the disposable probe. No PAM
modules, helpers, accounts, host configuration or authentication operations were
installed. Node is a retained binary with source retained. Python dependency
wheels and native npm bindings are retained binaries, not locally rebuilt.
Yarn3.5.0 and Rspack2.0.2 corresponding repository sources are retained at actual
peeled commits, alongside the npm/Python source distributions and notices.
Source availability does not establish complete Rust/Cargo/native transitive
closure or that every third-party component can already be rebuilt/repaired.

Non-fork Server/kernel/client/proxy/toolchain dependencies remain controlled
Class B archives with hashes, original notices and source locations. A needed
repair uses these sources and a reviewed local patch/build recipe; permanent
product changes require the source/ADR review in chapter11. No new public repo
was created. Off-machine custody backup/restore and independent defect repair
remain untested. Provider checksum comparisons were performed; developer release
signature verification was not established. Source/license review remains human.

The final `run-002` completed **24 top-level commands**, plus its nested PAM
configure/compile/linkage commands, with zero nonzero exits under the existing
Linux seccomp denial of non-UNIX socket creation. The receipt demonstrates denied
IPv4/IPv6 sockets, permitted UNIX communication and inherited no_new_privs/filter
state. Fresh private caches/venvs install only manifest-listed inputs with hashes;
no network package/source acquisition is part of the build. This does not isolate
host files or local UNIX services and is not a hostile-code sandbox.

Hub's archive build initially omitted tracked data because setuptools-scm had no
Git metadata. The final recipe explicitly includes its original alembic.ini,
alembic README/mako template, event YAML schema and singleuser HTML template,
then verifies wheel bytes. It builds/checks Hub vendor assets, Sass and React
explicitly rather than accepting setup.py's archive error suppression.

Lab verifies **103 owned workspace links**, compiles owned TypeScript packages,
nbconvert CSS and the production non-minimized frontend. Generated assets enter
the Python wheel through its sdist-shaped packaging path, avoiding published
JupyterLab core packages from the staging build. Third-party frontend packages
remain registry distributions. Original license assets are retained. Builds are
repeatable from recorded inputs; byte-identical wheels across paths are not claimed.

The linkage scan inspected80 ELF files and resolved14 library paths, including
nine unretained host libraries (Python, libc/loader, C++/GCC runtime, math,
pthread/rt/dl). It exited1 because a bundled, unused Parcel watcher **musl**
prebuild cannot load on this glibc host. That diagnostic is retained unchanged.
A separate real Node import selected its glibc sibling successfully and its
linkage had no missing dependencies. The audit is not full dynamic-loader,
Python-stdlib, compiler/header or toolchain source closure.

## Actual native and runtime results

| Selected native suite | Result |
|---|---:|
| Hub Python utils/slugs/objects/version | 137 passed |
| Lab Python extensions/plugin-manager/custom-CSS handlers | 69 passed |
| Hub JSX | 55 passed |
| Lab coreutils | 62 passed |
| Lab nbformat | 6 passed |
| Total | **329 passed; 0 failed/errors/skipped** |

The native report contains exact commands and upstream assertions/fixtures;
Lab's inherited unknown pytest option warning is preserved. Some native tests use
mocks. These are selected suites, not all upstream tests or browser tests.

Two fresh-state runtime reports, `runtime-ivnhawpn` and `runtime-tgw1e3j7`, each:

- Verified installed wheel origins and exact Lab asset hashes, fetched Lab over
  HTTP, and rejected missing/invalid credentials.
- Started a real ipykernel through Server HTTP and WebSockets; execution returned
  `AMBISGIS_KERNEL_RESULT=285`, count1, an OK reply and idle notification.
- Saved and reopened the executed notebook with identical source/IDs/count/output.
  The Server-added `metadata.trusted=true` annotation is explicitly checked.
- Launched owned Hub with retained proxy and owned singleuser entrypoint for the
  existing unprivileged OS user. A service token scoped to that user's server
  controlled lifecycle/access; interactive login and broader access were denied.
- Observed seven standalone and ten Hub/proxy/kernel TCP listeners, all
  `127.0.0.1`; shut down with exit0, no forced cleanup, no remaining descendants,
  stopped singleuser server and no retained private credential directories.

All four executed notebooks had SHA256
`fe87ee918a863c83abf5d7a28266f90321f6169c685fd9d4f4d70bb7a705a163`.
Both passes had the same418-asset manifest SHA256
`9c0d114ec2143877b9b56cd78bc25a50995962b207263ccfc41ddc505a17f647`.
This is repeatability of the local runtime fixture, not a host-restart/restore test.
Runtime networking was separate from build isolation; external egress denial was
not enforced or claimed. Same-user spawning is explicitly not multi-user isolation.

## Failures retained and limitations

Exploratory evidence is preserved: fixture `WARNING` versus traitlets `WARN`,
notebook trust-metadata normalization, the real Hub wheel data omission, initial
native collection without libpam, and PAM's first artifact-copy attempt matching
an intermediate directory. Fixes preserved upstream assertions and original
source data. A standalone-only probe explicitly records Hub skipped before the
packaging repair; the final two full probes have no Hub skip. The raw linkage
scan's incompatible unused musl variant remains a documented nonzero diagnostic.
Yarn's optional TypeScript compatibility-patch and peer warnings were preserved;
actual owned compilation and selected tests passed.

No full upstream or browser/accessibility suite, PAM authentication, production
SSO/delegation, two-user origin/filesystem/network isolation, quotas, scheduling,
GIS package profile, catalog/SDK authorization, publishing saga, revocation,
backup/host restart or P6 acceptance is established. Required managed-data API
boundaries and isolated notebook origins/runtimes remain unchanged. No Java/client
build was included. FND-07/FND-08 and canonical-baseline/license/security gates
remain distinct from this bounded source build/runtime checkpoint.

## Tooling verification

Current run: **20 Jupyter harness tests, 22 existing database-harness tests and
175 plan package tests passed with no failures/skips**, plus strict validation
and all four schemas/examples. These are tooling checks, not GIS acceptance.
[Package output](../verification/jupyter-package-tests.txt),
[schema output](../verification/jupyter-schemas.txt),
[Jupyter harness output](../verification/jupyter-harness-tests.txt) and
[database harness output](../verification/jupyter-database-harness-tests.txt)
are retained. No PostgreSQL/PostGIS native rebuild was repeated.

## Review and next action

Independent contexts reviewed build custody, package origins, runtime credential
handling/cleanup and native evidence. Material findings were fixed and rechecked;
see [review record](../verification/jupyter-slice-review.txt). Review the new Jupyter
PR for this bounded checkpoint only. No merge, release, deployment, signing,
secrets installation, workflow enablement or source-fork default change occurred.

GOV-02's separate [PR #52](https://github.com/aloerch/ambisgis-platform/pull/52)
accepts attributed owner evidence and supported readback. Issue#9 still needs the
view5 Review gate restriction and view4 Status-hidden/derived-only confirmation;
its [exact separate instructions](https://github.com/aloerch/ambisgis-platform/blob/gov-02/saved-view-reconciliation/plan/docs/project-view-reconciliation.md)
block only GOV-02. No Project progress/settings reset was performed.

The next ready engineering action remains within FND-02: audit and retain the
Java rendering dependency closure in GeoTools34.5 → GeoWebCache1.28.5 →
GeoServer2.28.5 order, including actual GeoNode extensions; then the exact
MapStore/client pair and QGIS dependencies according to their source declarations.
Read the live issue/dependency evidence and claim a separate branch first. This
slice does not make their builds, FND-07/FND-08 or P1 automatically Ready/accepted.
