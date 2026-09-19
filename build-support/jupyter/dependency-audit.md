# FND-02 Jupyter candidate and dependency audit

Source inspection and authoritative advisory review: **2026-09-19**. This records
experimental candidate selection and build boundaries; the run receipt and handoff
record actual artifacts, resolved dependency versions, tests, failures and omissions.
It is not a canonical baseline, security approval, license clearance or P6 acceptance.

## Owned candidates

| Component | Owned source | Annotated tag object | Peeled commit |
|---|---|---|---|
| JupyterHub 6.0.1 | `aloerch/ambisgis-jupyterhub`, tag `6.0.1` | `65de9c630531e0ac7630f6da166e91c54726e0af` | `3e516c6f382b481e815ec455befb2f14d80d337b` |
| JupyterLab 4.6.3 | `aloerch/ambisgis-jupyterlab`, tag `v4.6.3` | `9c81bd1442601ba5c6b20bbd46678b5b236d2721` | `e7255a9334c12ad8f9cb15db27584215fab5ece2` |

These identities came from retained owned Git objects using `git rev-parse TAG`
and `git rev-parse TAG^{}`. Tag identity does not assert verified release signatures.
No source-fork default branch or donor reference is changed by this selection.
Both selected source roots contain a BSD three-clause `LICENSE`; retain those
files and inherited copyright notices. This observation does not establish the
licenses of bundled dependencies, fonts, images or trademarks.

Choose this pair for a new disposable development runtime because both declare
Python >=3.10, Lab requires Jupyter Server 2, and Hub's default single-user entrypoint
uses its Jupyter Server extension when Server >=2 is present. There is no declared
Hub/Lab exact-version lock: actual build, package-origin and runtime tests are
required to demonstrate this pair. Keep the same owned Hub wheel version in the
control-plane and single-user environments. The retained Lab 4.7 prereleases are
not needed for the experiment. Hub 6.0.1 includes a proxy-binding regression fix
particularly relevant to a loopback-only fixture. Hub 6 introduces a database
schema change; creating a disposable SQLite database here does not test upgrading
an existing Hub database. [Hub changelog](https://jupyterhub.readthedocs.io/en/6.0.1/reference/changelog.html)

## Source declarations and environment boundaries

| Boundary | Declarations or required inputs | Custody and verification |
|---|---|---|
| Hub Python build | `setuptools>=77`, `setuptools-scm`; `setuptools.build_meta`; dynamic requirements from `requirements.txt` | Retain exact backend distributions and their hashes. Audit `setup.py` frontend hooks below. |
| Hub control plane | `aiohttp`, `aiodns`, `alembic>=1.4`, `certipy>=0.1.2`, `idna`, `jinja2>=2.11`, `jupyter_events>=0.11`, `oauthlib>=3`, `packaging`, POSIX `pamela>=1.1`, `prometheus_client>=0.5`, `pydantic>=2`, `python-dateutil`, `requests`, `SQLAlchemy>=1.4.1`, `tornado>=6.5`, `traitlets>=5.4` | Resolve separately from GeoNode and the user environment. SQLite is sufficient only for the disposable fixture. PAM's host library remains relevant even if the test authenticator does not use PAM. |
| Lab Python build/runtime builder | `hatchling>=1.21.1`, `jupyter-builder>=1.0.2`; hook dependency `hatch-jupyter-builder>=0.3.2`; `hatchling.build` | `jupyter-builder` is a separate third-party distribution in this candidate, not an owned package in this Lab revision. Retain it explicitly. |
| Lab server environment | `jupyter_server>=2.19,<3`, `jupyterlab_server>=2.28,<3`, `ipykernel>=6.5,!=6.30.0`, `jupyter-lsp>=2`, `notebook_shim>=0.2`, `async_lru>=1`, `httpx>=0.25,<1`, `jinja2>=3.0.3`, `jupyter_core`, `packaging>=23.2`, `tornado>=6.2`, `traitlets` | Resolve a full transitive lock including `jupyter_client`, ZeroMQ/`pyzmq`, IPython, `nbformat`, `nbclient`/`nbconvert` where required, WebSocket and terminal machinery, and native wheels. Record actual imports and kernel executable. |
| Conditional Python dependencies | Lab `tomli>=1.2.2` for Python <3.11 and `typing-extensions>=4.4` for Python <3.12 | Evaluate markers for the recorded interpreter; do not advertise a cross-platform lock from one resolution. |
| JS toolchain | Lab root `packageManager=yarn@3.5.0`; Lab application `node>=20`; Rspack core/CLI `2.0.2`; Hub npm lockfile version 3 | Hub's selected React router dependency requires Node >=22.22, stronger than Lab's root minimum. Use the separately retained, verified Node 24 candidate. Yarn and Rspack/native binding distributions need explicit retention. |
| Hub frontend | Root `package-lock.json` has 190 package records; `jsx/package-lock.json` has 972, including each root record | Preserve both exact locks and npm integrity fields. Counts are source observations, not counts of installed or source-built dependencies. |
| Proxy | `jupyterhub.proxy.ConfigurableHTTPProxy` invokes `configurable-http-proxy` | It is external to the two owned roots. Pin and retain its exact package and transitive inputs; do not install globally. Source declaration alone does not select a proxy version. |
| Authentication/spawning | Native Hub defaults are PAM and `LocalProcessSpawner`; native `SimpleLocalProcessSpawner` is explicitly testing-only and provides no user isolation | A local fixture may use a scoped authenticator and unprivileged simple spawner with disposable credentials. Neither proves SSO or multi-user isolation. Bind Hub, proxy public/API, single-user server and kernel connections to loopback. |
| Test tools | Hub declares `pytest`, `pytest-asyncio>=1.1`, optional `cryptography`, `requests-mock`, `mock`, `beautifulsoup4[html5lib]`, browser and other extras. Lab declares `pytest>=7`, `pytest-jupyter>=0.5.3`, `pytest-tornasync`, coverage, timeout, console-script and other extras | Retain the dependencies actually used. Browser engines are additional retained binaries if browser tests run; absence must be reported. Do not count an HTTP asset fetch as a browser test. |

Declarations are in the selected
[Hub pyproject](https://github.com/aloerch/ambisgis-jupyterhub/blob/3e516c6f382b481e815ec455befb2f14d80d337b/pyproject.toml),
[Hub requirements](https://github.com/aloerch/ambisgis-jupyterhub/blob/3e516c6f382b481e815ec455befb2f14d80d337b/requirements.txt),
[Lab pyproject](https://github.com/aloerch/ambisgis-jupyterlab/blob/e7255a9334c12ad8f9cb15db27584215fab5ece2/pyproject.toml),
and [Lab package.json](https://github.com/aloerch/ambisgis-jupyterlab/blob/e7255a9334c12ad8f9cb15db27584215fab5ece2/package.json).
The retained lock/manifest supplies exact resolved versions; these source ranges
must not become installation instructions for an unrecorded later resolution.

## Frontend and installation hook audit

Hub `setup.py` runs `npm install` from its `js` and `jsx` commands. Its `build_py`
wrapper suppresses frontend errors when `.git` is absent. Consequently a successful
wheel command on an exported archive is insufficient proof of a complete frontend.
Use the exact root and JSX locks, disable unreviewed install scripts, and explicitly
run reviewed `bower-lite`, Sass and JSX webpack steps. `bower-lite` copies root npm
runtime dependencies into `share/jupyterhub/static/components`; Sass emits
`static/css/style.min.css` and its map; webpack emits `static/js/admin-react.js`.
Assert those outputs and their installed copies. The root lock flags install hooks
for `@parcel/watcher` and `fsevents`; the JSX lock flags `fsevents` and
`unrs-resolver`. Retaining native optional packages is distinct from building them.

Lab's ordinary wheel hook builds `jupyterlab/staging`, whose dependencies refer to
published `@jupyterlab/*` packages. That path alone does not establish owned frontend
source provenance. Build the workspace packages in the retained monorepo
(`build:packages` invokes `tsc -b`) and bundle `dev_mode` using its reviewed Rspack
configuration. The application sets `buildDir=./static`, `outputDir=.`;
`Build.ensureAssets` emits schemas/themes into `dev_mode`, and the bundle goes to
`dev_mode/static`. Package the three generated directories as
`jupyterlab/static`, `jupyterlab/schemas`, `jupyterlab/themes`, with a recorded build
transformation that prevents the wheel hook replacing them from npm staging.
Verify workspace module resolution and installed static package version 4.6.3.
`build:nbconvert:css` is a separate Rspack target if its output is needed.

Lab `.yarnrc.yml` already disables dependency scripts and telemetry. Its root
`postinstall` calls `scripts/ensure-buildutils.js`; build scripts and the selected
builder are executable inputs and still require review. Avoid `build:core`,
`update-core-mode` and `deduplicate` in a frozen replay: these invoke additional
`jlpm`, staging resolution and/or `jlpm dlx` downloads. The inherited release
hooks also start a local package repository and publish distributions into it;
this fixture need not invoke release or publishing hooks.

## Current advisory and support evidence

The following public upstream evidence informed acquisition selection, checked
2026-09-19. It is not a complete dependency vulnerability scan or an assertion
that these candidates are free of vulnerabilities.

| Advisory / support input | Observed scope and implication |
|---|---|
| [Hub share scopes after user rename, GHSA-mj6q-mp44-53v8](https://github.com/jupyterhub/jupyterhub/security/advisories/GHSA-mj6q-mp44-53v8) | Affects >=5.0,<5.5.2; patched 5.5.2. Candidate 6.0.1 lies outside the published affected range. |
| [Hub share-link XSS, GHSA-c4gm-pwx9-9w8j](https://github.com/jupyterhub/jupyterhub/security/advisories/GHSA-c4gm-pwx9-9w8j) | Affects >=5.0,<5.5.1, when user-initiated sharing is enabled; patched 5.5.1. |
| [Hub limited-admin scope enforcement, GHSA-69wv-m5fw-2fhp](https://github.com/jupyterhub/jupyterhub/security/advisories/GHSA-69wv-m5fw-2fhp) | Affects >=2.0,<=5.5.0 with filtered administrative roles; patched 5.5.1. |
| [Hub failed-login log exhaustion, GHSA-p43p-whwx-q52h](https://github.com/jupyterhub/jupyterhub/security/advisories/GHSA-p43p-whwx-q52h) | Affects <5.5.0; patched 5.5.0. |
| [Lab settings-file XSS, GHSA-pppj-hq3g-57pj](https://github.com/jupyterlab/jupyterlab/security/advisories/GHSA-pppj-hq3g-57pj) | 4.6.0–4.6.1 affected; patched 4.6.2. Shared writable settings remain an operational trust boundary. |
| [Lab plugin-lock bypass, GHSA-h5v5-8746-g7mm](https://github.com/jupyterlab/jupyterlab/security/advisories/GHSA-h5v5-8746-g7mm) | 4.6.0–4.6.1 affected; patched 4.6.2. Preserve the native handler regression tests. |
| [Lab extension-name canonicalization, GHSA-89vp-jrxv-24w8](https://github.com/jupyterlab/jupyterlab/security/advisories/GHSA-89vp-jrxv-24w8) | 4.6.0–4.6.1 affected; patched 4.6.2. Advisory's 4.5 range overlaps its patched 4.5.10 entry; selection here uses its unambiguous 4.6 range. |
| [Lab image-viewer XSS, GHSA-gx64-gj6p-pc4c](https://github.com/jupyterlab/jupyterlab/security/advisories/GHSA-gx64-gj6p-pc4c) | 4.6.0–4.6.1 affected; patched 4.6.2. |
| [Lab lifecycle](https://jupyterlab.readthedocs.io/en/4.6.x/getting_started/lifecycle.html) | Major 4 is listed active. The policy maintains a major until one year after the next major's general release; no fixed support promise for this AmbisGIS candidate follows. |
| [Node 24.21.0 release](https://nodejs.org/en/blog/release/v24.21.0) | Released 2026-09-08 as LTS. Select an exact distribution, retain hashes/source and report whether signature verification was actually performed. |

The wider [Hub advisory list](https://github.com/jupyterhub/jupyterhub/security)
and [Lab advisory list](https://github.com/jupyterlab/jupyterlab/security) also
include earlier XSRF, redirect, extension-policy and rendering disclosures.
Production suitability still requires triage of the entire resolved graph,
including Server, proxy, Node, Python, native libraries and frontend dependencies.
AmbisGIS owns that triage and repair decision; no automatic donor synchronization
or release adoption is implied.

## Retention, repair and test limits

Classify every input in the generated manifest: owned source build, retained
third-party source, retained binary distribution, or unretained host dependency.
A Python wheel or native npm binding remains a binary input even when its matching
source archive is retained. Retain distribution/source URLs, SHA-256, package
name/version, license metadata and available license/notice files, plus build,
runtime and test roles. Preserve source package and npm integrity metadata.
The two owned source wheels and generated frontend assets require their own
artifact hashes and commands. Do not label the complete environment source-built.

Required non-fork components such as Jupyter Server, kernel/client machinery,
`jupyter-builder`, configurable HTTP proxy and native transitive dependencies
belong in controlled dependency storage. Repair can use retained corresponding
source and a reviewed patch/build recipe without adding a public repository.
A retained source archive is a repair input, not evidence that its rebuild works;
missing sources or untested native repair paths remain explicit FND-07/FND-08
gaps. Python/stdlib, libc/loader, PAM, shell, host libraries and any browser/runtime
binary not retained remain host dependencies. No Java/client/QGIS build is part of
this notebook slice.

A useful bounded native set is Hub `test_utils.py`, `test_slugs.py`,
`test_objects.py`, `test_version.py`, plus Lab `test_extensions.py`,
`test_plugin_manager_handler.py`, `test_custom_css_handler.py`. Preserve upstream
fixtures, assertions and pytest settings. Hub's global conftest imports PAM,
Certipy, SQLAlchemy, requests and asyncio machinery even for helper modules.
Lab's root conftest enables `pytest_jupyter.jupyter_server`,
`jupyterlab_server.pytest_plugin` and `jupyterlab.pytest_plugin`; handler tests use
actual local HTTP servers, while some extension interactions are deliberately
mocked. These modules are a selected native subset, not the full upstream suite.
Any additional native suites and JavaScript/browser tests must report separately.

The disposable runtime must verify installed origins/versions, generated assets,
server startup, a real kernel execution, notebook save/reopen and orderly process
shutdown. If exercised, Hub/proxy/single-user launch is a separate integration
result. Build network denial may deny all IP sockets; runtime requires loopback
TCP/WebSockets/ZeroMQ. Loopback binding alone is not proof of blocked external
network access. Preserve the exact enforcement mechanism and its limits.

Remaining product work includes SSO/delegation, immutable spatial profiles and
native GIS provenance, per-user origins/containers, resource/network limits,
catalog/SDK policy integration, scheduling, publishing, backup/restore and P6
acceptance. A trusted-user spawner or arithmetic notebook cannot close these gates.
