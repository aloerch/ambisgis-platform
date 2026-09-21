# FND-02 owned frontend checkpoint

The current execution authority is the [finite completion checklist](fnd-02-completion.md).
FND-02 remains **In progress**. Start was verified merged main
`433cb7d8fb662b05bd1f67e8825938d0770a0d41`, owner-merged PR #61, whose reviewed
head `8477c301a2d618b963c66047e590c3994366d0de` and source branch remain preserved.
The dated role handoff's arbitrary Java-gap next action is superseded. This
checkpoint does not accept FND-03/FND-05/FND-07/FND-08 or any release gate.

## Exact build and replay

Review [PR #62](https://github.com/aloerch/ambisgis-platform/pull/62). Frozen
implementation/evidence commit: `2eb07794dc9fd014e8002112bd45a95309f8cf9e`;
frontend tooling tree: `3228af78d063c9ae10e89ab6705dd380a4db6e38`.
Publication-only documentation commits preserve that tree. Final pushed head is
pinned by the closing issue evidence comment.

Platform branch: `fnd-02/completion-frontend`; worktree:
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-frontend`.
Owned client `7ca4822125b67999c97cb4aa1faa84b8a28eee9b` and exact owned MapStore
gitlink `0f3518737f29f4049b131247ce981e94519d9ab0` compiled through the client's
native webpack path into six applications, **960 dist files: 595 JavaScript and
32 CSS files**, plus assets. Full staged static tree: **1,038 files**. This is a
fresh compilation; inherited dist and translations were removed before building.
No standalone MapStore Java catalog, dev server or donor CDN supplied the viewer.

The [recipe](../../build-support/frontend/README.md),
[complete lock](../../build-support/frontend/dependency-lock.json) and
[reviewed input identities](../../build-support/frontend/inputs.json) retain
2,022 registry archives and three exact helper/Git sources. npm installed 2,403
packages from a 2,410-entry lock using Node **24.18.1** / npm **11.16.0**.
The inherited legacy-peer-deps setting is explicit; no force/audit-fix/upgrade.
Only the reviewed MapStore postinstall hook executes. Other registry hooks,
including native/prebuilt/browser downloads, stay disabled and inventoried.

Retained root:
`/home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion`.
`build-01` is the browser-served build; `build-02` is a fresh retained-input replay;
`build-03` exercises the final reviewed manifest/lock authority guards. Each has
new source recovery, Node extraction, node_modules and npm cache. Install, hook,
compiler and source recovery use the existing socket-denying runner with actual
kernel probes. The final recipe also rejects replacement of the reviewed root
manifest or lock before creating output. Failed commands cannot publish success.

The two first builds are **replayable, not byte-identical**. Complete raw output
manifests are retained. Measured differences are fully accounted for by exact
build-directory strings in `@zip.js/zip.js` and `@spz-loader/core`, and webpack
fullhash references. Diagnostic normalization changed no artifact. No cross-host
reproducibility claim. Five webpack warnings remain: three optional copy paths
(client translations/configs and Cesium navigation), asset size and entry size.
The public 2D smoke passes; no Cesium/3D acceptance is inferred.

## Real backend/browser demonstration

Successful immutable attempt: `browser-smoke-06`. It uses the unchanged #61 WAR
`a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`,
GeoNode wheel `d4194e17bfaa517d829b47550022bc0831a3fe0872483d968ecbf29251cd5c28`
and client backend wheel `1ba859afca3993da35f05e838185fa027d0f9779a4cb26124dd638617157442b`.
Installed owned backend files verify before and after. collectstatic's entire
mapstore subtree is replaced by the hash-verified compiled tree. Every loaded
mapstore asset is checked against the complete manifest, including `gn-map.js`
and loaded chunks. Original wheels and prior build directories remain untouched.

The actual GeoNode `/maps/<pk>/embed` route reads a persisted synthetic public Map
and its native API metadata. The single known `fixture:public_points` WMS layer
comes from the real owned GeoServer. Browser-facing service URLs use GeoNode's
existing `/gs/wms` and `/gs/pdf` proxy paths; internal service URLs remain exact
loopback URLs. Existing strict token/role verification, stateless GeoServer,
CSRF and proxy restrictions remain intact. No mocked API response or CORS bypass.

Before and after one service restart, each browser phase records **109 responses,
43 distinct verified frontend artifacts, three rendered states** (initial, zoom,
reload). All six states have 556 red witness pixels in the real OpenLayers layer
canvas. Wheel zoom reduces the actual WMS GetMap BBOX. DOM resource identity,
API responses, WMS PNG hashes, screenshots and network outcomes are retained.
There are no unexpected external requests, missing resources, failed requests,
page errors or blocking console errors. Native anonymous `/api/v2/userinfo/` 401
and its exact browser console message are separately recorded as expected denial;
it was not converted to successful authentication or hidden by a broad exception.

Browser: retained Playwright **1.63.0**, its matched Chromium **153.0.8010.12**,
revision **1243**, launched with `chromiumSandbox:true`. The current
[Playwright release](https://playwright.dev/docs/release-notes) and
[browser/sandbox documentation](https://playwright.dev/docs/api/class-browsertype#browser-type-launch-option-chromium-sandbox)
were checked; the [Chrome for Testing index](https://googlechromelabs.github.io/chrome-for-testing/)
listed a newer stable patch 153.0.8010.52. This is the matched retained automation
runtime, not a claim of newest Chrome or security clearance. Archives and all
extracted files are hashed in `browser-inputs/retention.json`.

The backend remains under the unchanged loopback supervisor: **79 parent and 79
exec-child probes passed**, zero datagram packets, task group and broker sockets
closed. PostgreSQL alone retains #61's documented native setsid/SCRAM exception.
The browser runs separately with its sandbox and exact task-origin request
allowlist, including WebSocket rejection. This is not host-wide egress proof or
a broader supervisor exemption. Both services and database stopped; native stored
credentials were invalidated, disposable secret files scrubbed and diagnostic
secret/security hits were zero. The browser closed in both phases.

## Actual tests, failed evidence and limits

- Native client: **358 passed** across all 40 test files; selected owned framework:
  **152 passed** across seven config/resource/WMS/WFS/security test files. No skips.
  This is not the entire MapStore suite. [Selection/commands](../../build-support/frontend/native-tests.md).
- Nonmutating client ESLint: **five inherited errors**, one JSX wrap and four
  indentation errors. No auto-fix or source expectation change. This checkpoint
  does not claim lint passes.
- Build/lock/integrity harness: **22 tests passed**; browser artifact harness:
  **nine passed**; directly reused loopback harness: **15 passed**.
- Plan package checks: **176 tests and four strict schema/example checks passed**
  in the retained verified Python environment. These are package checks, not GIS
  product acceptance. Unchanged Java/database/Jupyter/backend native suites were
  not repeated; their exact historical evidence remains linked from the checklist.

Independent review found and fixed incomplete input-manifest validation, symlink
confinement, alteration of prior output on rejected reuse, audit metadata/path
validation, reviewed-root manifest/lock binding, and a late browser-response
acceptance gap. Positive/negative probes, exact reviewed source hashes and failed
attempts remain retained. First framework run had one native fixture URL timeout;
a precise retained fixture mapping fixed it and the actual suite passed.
Browser attempts 01–05 remain failures: native layer fixture path; cross-origin
WMS/canvas path; optional print URL; generated tooling bytecode twice. Same-origin
native proxy configuration and inherited no-bytecode environment fixed the scoped
fixture defects; no backend authorization/security check was weakened.

The bounded dependency inventory records notices, advertised lifecycle scripts,
package engines and generated/native/WASM content. **18 packages lack a package.json
license declaration**: 12 have notice-named text, three have README/source terms,
two have alternate declarations only, and no terms were found for `web-ifc` 0.0.50
in the bounded retained scan. These are evidence findings, not license clearance.
In particular `web-ifc`, emitter-component's version-mismatched metadata and jsonp's
incomplete notice evidence need explicit selection/rights disposition under F02-06.
The build contains retained third-party generated assets; their comprehensive
corresponding-source/toolchain rebuild remains FND-08. Required unusable source or
invalid rights cannot be waived by a successful build or owner recording a limit.

## Resume and owner decision

Use fresh output names with the commands in the frontend recipe and smoke runbook.
The [compact evidence index](../verification/frontend-completion/evidence.json)
binds exact output manifests, source/lock identities, native and browser outcomes,
independent review and retained failures. Large original receipts stay retained.

Owner review is for this exact new frontend/checklist PR: manifest substitutions,
input guards, browser containment/proxy staging, failed evidence and license
selection findings. #61's approval does not approve these changes. Review gates
merging the checkpoint; engineering can continue independently. No merge,
auto-merge, branch deletion, source-default change, workflow activation, release
or deployment is performed here.

Next dependency-ready engineering is **F02-04: the missing owned QGIS desktop/server
candidate build**, with its exact native-library prerequisites, in a later bounded
session. F02-05 combination/GWC gaps, F02-06 consolidated selection/license
proposal, F02-07 maintenance-policy binding and F02-08 final criterion report and
explicit owner acceptance remain. Do not return to an arbitrary Java gap or
expand authorization work by default. FND-02 stays In progress.

[Project publication/readback](../verification/frontend-completion/project/README.md)
records 75 items (66 tasks + nine PRs), preservation of all 74 prior items/views,
and #62 alone in the unchanged open-PR queue. FND-02 Delivery stays In progress.
