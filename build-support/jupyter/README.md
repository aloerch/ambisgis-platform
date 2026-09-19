# Experimental owned Jupyter candidate/runtime slice

This FND-02 slice builds Hub 6.0.1 and Lab 4.6.3 from exact owned source exports,
including Hub Sass/React and Lab TypeScript/Rspack assets. It installs separate
Hub and user-server environments and provides a disposable loopback notebook
probe. It is not the notebook product, a deployment profile or P6 acceptance.

The [candidate/hook/security audit](dependency-audit.md), [exact input manifest](inputs.json),
[dependency/license lock](dependency-lock.json) and three hash-enforced Python
requirements files distinguish owned builds, retained third-party sources,
retained binary wheels/Node/native bindings and unretained host dependencies.
Large inputs, original notices and full logs remain outside Git. A matching
source distribution is a repair input, not a tested third-party rebuild.

## Verified-input build

Use an unused run directory; the build refuses an existing one. The observed
host is Linux x86_64, Python3.13.15 with venv/ensurepip, GCC15.2, Meson1.9.2,
Ninja1.13.2, shell/binutils/pkg-config and libc. Host tools, Python/stdlib and
headers are not fully retained. The broad linkage diagnostic reports an unused bundled musl variant on glibc;
its actual glibc loader selection is separately verified in the evidence.
Exact observed identities/linkage are evidence,
not a portable toolchain or an approved baseline. No global install is used.

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
cd "$TASK_ROOT/ambisgis-platform-jupyter"
TASK_INPUTS="$TASK_ROOT/source-archives/jupyter-slice"
TASK_RUN="$TASK_ROOT/build-worktrees/jupyter-slice/run-003"
python3 build-support/jupyter/acquisition.py --custody "$TASK_INPUTS"
python3 build-support/postgis/offline_exec.py \
  --evidence "$TASK_ROOT/build-worktrees/jupyter-slice/offline-run003.json" -- \
  python3 build-support/jupyter/build.py --custody "$TASK_INPUTS" --run "$TASK_RUN"
```

The existing Linux seccomp wrapper denies non-UNIX socket creation, io_uring,
ptrace and descriptor-import paths for the command and descendants. Its actual
IPv4/IPv6 denial and UNIX communication probes are recorded before execution.
The build verifies manifest hashes, copies only listed cache/wheel entries into
private stores, uses `pip --no-index --require-hashes`, `npm ci --offline
--ignore-scripts`, and immutable Yarn with networking/scripts disabled. No external
source/package access is needed. Host files and local UNIX services remain
accessible; this is a trusted build experiment, not a hostile-code sandbox.

The build records every command/exit/log hash and immutable recipe/input snapshots.
It source-builds only Hub, Lab and the two Linux-PAM core libraries. Node24.21.0,
146 Python dependency distributions and native JS tools are retained distributions;
Node, Yarn and Rspack repair sources and all Python sdists are also retained.
No PAM modules/helpers, OS accounts, host authentication configuration or sudo
are installed. PAM only supplies an isolated import dependency for native tests and the disposable Hub probe.

Hub's setuptools-scm file finder lacks Git metadata in an exported archive. The
recipe explicitly adds the five tracked migration/schema/template files to
MANIFEST.in and checks their wheel bytes against owned source. It explicitly
builds/asserts frontend outputs before wheel creation; archive-build suppression
of a frontend error cannot by itself count as acceptance.

Lab workspace links are checked against the owned extracted package directories,
then build utilities, TypeScript packages, nbconvert CSS and the production
(non-minimized) frontend are compiled. Generated static/schema/theme directories
are copied into a package tree shaped like an sdist. The selected normal wheel
hook skips npm when dev_mode is absent, preventing staging resolution from
replacing owned Lab core code with published npm packages. Third-party frontend
dependencies remain retained registry distributions. This transformation is an
experimental build recipe, not an upstream source change or release procedure.

## Real native and runtime checks

These need local TCP/WebSockets/ZeroMQ. **Do not run them through the IP-denying
build wrapper.** They sanitize their environments and bind/probe local services;
they do not demonstrate blocked external egress or multi-user isolation.

```sh
python3 build-support/jupyter/native_tests.py --run "$TASK_RUN" \
  --pam-library-dir "$TASK_RUN/pam/prefix/lib"
python3 build-support/jupyter/runtime_probe.py \
  --hub-env "$TASK_RUN/hub-env" --user-env "$TASK_RUN/user-env" \
  --work-root "$TASK_RUN/runtime-evidence" \
  --node-bin "$TASK_RUN/sources/node-v24.21.0-linux-x64/bin" \
  --proxy "$TASK_RUN/proxy/node_modules/.bin/configurable-http-proxy"
python3 build-support/jupyter/host_audit.py --run "$TASK_RUN" \
  --output "$TASK_RUN/native-linkage.json"
```

Native suites preserve upstream assertions/fixtures: Hub utils/slugs/objects/version;
Lab extensions/plugin-manager/custom-CSS handlers; Hub JSX; Lab coreutils/nbformat.
Some inherited tests use mocks; real HTTP/kernel/Hub integration is separate.
The full upstream suites, browser/accessibility tests, dependency library suites,
PAM authentication, production OIDC and all GIS profiles remain outside this
bounded selection. Reports enumerate actual failures/skips; no pass is inferred
from collection alone. An additional invocation uses a new `--output` directory.

The broad `host_audit.py` scan deliberately preserves an exit1 diagnostic for the
bundled unused Parcel musl binary on this glibc host. The recorded actual Node
loader selects its glibc sibling, whose dependencies all resolve; consult
`native-linkage-selection.json` in the final run. Do not erase that original
scan result or treat it as a required runtime-library failure.

The runtime checks installed versions/imports/local wheel hashes against the
successful build receipt, every installed Lab static asset against that wheel,
auth denial, real kernel execution over WebSockets, notebook save/reopen and
orderly shutdown. The Contents API's `metadata.trusted` annotation is recorded;
cell source, IDs, counts and outputs must otherwise match exactly. Observed TCP
listeners belonging to fixture descendants must all be IPv4 loopback.

With `--proxy`, it additionally launches Hub → configurable-http-proxy → the
single-user server, executes/reopens a notebook through the proxy, and stops the
server/Hub/proxy. Interactive authentication is denied; a disposable narrowly
scoped service token controls only the current OS user's fixture server. The
same-user SimpleLocalProcessSpawner supplies **no security isolation**. Credentials
are excluded from argv/report and redacted before log persistence; temporary
cookies/database/config are removed after shutdown. Omitting `--proxy` explicitly
reports Hub integration skipped. No skipping is needed for the final evidence.

## Acquisition, custody and recovery

`acquisition.py` defaults to verification. `--fetch --owned-root "$TASK_ROOT"`
may restore missing URL-backed distributions or exact owned Git archives, always
checking their recorded hashes. It never re-resolves dependencies. Retained
metadata/cache/notice files without acquisition URLs must be restored from custody
backup; a missing cache entry is a hard failure. Custody is currently this local
workspace; off-machine disaster recovery and third-party repair remain FND-07/FND-08
work. Preserve original full-history bundles and all previous build runs.

`resolve_inputs.py` is the explicit initial-acquisition proposal procedure, not a
replay command. It takes `--custody`, `--stage` containing audited source/Node exports,
and `--resolver-python` pointing to a verified isolated pip environment. It refuses
to re-resolve a completed custody store. Source declarations and the two Hub locks/
Lab yarn.lock are authoritative inputs; new proposals need fresh stores and review.
Only reviewed build commands run scripts; acquisition disables dependency hooks.
The exact successful original resolution reports/logs remain in `acquisition/`.
`inventory.py` reads archives without executing them, retaining original notices
by hash and reporting native members in both Python and JavaScript distributions.

The two Python startup hooks were inspected: setuptools's distutils shim and
coverage's conditional process-start hook. Sanitized builds omit the coverage
trigger variables. npm/Yarn hook metadata is retained in the full local inventory;
automatic install scripts remain disabled. Yarn's inherited TypeScript optional
compatibility-patch warning is preserved; the actual compilation/tests determine
success. Build artifacts are not claimed byte-identical across paths/runs.

## Tooling checks

```sh
python3 -m unittest discover -s build-support/jupyter -p 'test_*.py' -v
python3 -m unittest discover -s build-support/postgis -p 'test_*.py' -v
cd plan
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 -m unittest discover -s tests -v
PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 tools/validate_package.py --require-schemas
```

These tooling checks are not GIS product tests. The database harness is rerun;
the previously accepted PostgreSQL/PostGIS native builds are historical evidence
and are not repeated by this slice. See the [final evidence](../../plan/docs/jupyter-slice-evidence.md)
and [handoff](../../plan/docs/jupyter-slice-handoff.md) for exact results and gates.
