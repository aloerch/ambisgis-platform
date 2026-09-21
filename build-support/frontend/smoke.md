# Owned frontend public-map smoke

`smoke.py` stages one complete compiled MapStore client artifact tree into a
fresh disposable GeoNode collectstatic directory. It removes the inherited
MapStore tree first, verifies every staged file, and hashes every browser-loaded
MapStore response. The source-built #61 GeoNode/client wheels remain unchanged
and are checked before and after execution. The source-built #61 GeoServer WAR
is pinned to SHA-256
`a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`.

From this platform worktree on the verified host:

```sh
flatpak-spawn --host /usr/bin/python3 build-support/frontend/smoke.py \
  --frontend /home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion/build-01/client/geonode_mapstore_client/static/mapstore \
  --frontend-manifest /home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion/build-01/output-manifest.json \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion/browser-smoke-07
python3 -m unittest discover -s build-support/frontend -p smoke_tests.py -v
```

The output must not exist. `browser-smoke-06` is the final successful retained
attempt; do not rerun into it. It consumed build-01's complete 960-file output
manifest. Nine artifact custody/style-path regression cases pass without skips.
These harness cases are separate from the actual browser/backend journey.

The native anonymous route is `/maps/<pk>/embed`. A native GeoNode Map record
stores a synthetic public WMS layer in `blob`; its viewer configuration comes
from the real permission-checked `/api/v2/maps/<pk>/` endpoint. The map references
`/gs/wms`, GeoNode's inherited fixed-downstream GeoServer proxy. Browser-facing
`GEOSERVER_PUBLIC_LOCATION` and `OGC_SERVER.default.PUBLIC_LOCATION` use the same
native `/gs/` path, including printing metadata. The internal GeoServer URL stays
an exact task-local loopback service. No new proxy, CORS exemption, changed CSRF
rule, mock API, alternate catalogue, external basemap, or development server is
used. Strict token/role checks and stateless GeoServer configuration are retained.

The synthetic GeoServer shapefile contains one point at longitude 1, latitude 2;
its task-only native SLD paints a red circle. Initial and restarted browser
phases each record 109 responses, 43 distinct hash-verified MapStore assets,
three real WMS PNGs and three rendered canvas observations (load, zoom, reload).
Each observation contains 556 red pixels. Wheel zoom shrinks the actual WMS BBOX
span from 1,345,291.697819102 to 672,645.848909551. Both serving processes restart
with identical frontend and WAR bytes before the second browser phase.

Each phase has zero unexpected external requests, failed requests, blocking
console errors, or page errors. The native anonymous `/api/v2/userinfo/` probe
returns 401 once per page load; the exact same-origin path/status and its exact
console URL/message are recorded as expected nonblocking denials. All resource,
configuration, WMS and other console/network failures remain fatal. A screenshot
alone is insufficient: actual canvas pixels, backend JSON, WMS bodies, loaded
bundle/chunk hashes, zoom BBOX changes and reload/restart are all required.
Screenshots and PNG responses have retained SHA-256 bindings.

Browser inputs are retained under
`build-worktrees/frontend-completion/browser-inputs`, with complete file hashes,
archive hashes, source locations and original notices in `retention.json`:

- Playwright core 1.63.0, archive SHA-256
  `2fda0eda3a76a396807b27cef81d33578b9370698c9cb0f62669f6be897916db`.
- Its matching Chromium revision 1243 / Chrome for Testing 153.0.8010.12,
  archive SHA-256
  `a44ba545f6ea207d81307658c292c9efd38f7ac9eaea56859c12bf36f45c750e`.

The archives allow restoration of their `playwright-core/` and `chromium/`
directories at the retained root; verify their recorded SHA-256 before extraction.
Every smoke invocation checks both archive and extracted file manifests. No
existing global npm/browser cache is required. These are retained tool binaries
and package sources, not a browser/toolchain source rebuild. Host shared libraries
remain host dependencies.

The [current Playwright release notes](https://playwright.dev/docs/release-notes)
identify release 1.63. [Browser guidance](https://playwright.dev/docs/browsers)
and [launch documentation](https://playwright.dev/docs/api/class-browsertype)
support using the matched browser; Chromium sandboxing is explicitly enabled
because Playwright defaults it off. The official
[Chrome for Testing availability](https://googlechromelabs.github.io/chrome-for-testing/)
listed newer stable 153.0.8010.52 during verification. The retained matched test
browser is not claimed to be the latest Chrome patch or a security-cleared
production browser. The observations are retained in `support-check.json`.

The backend uses the unchanged loopback seccomp supervisor; final evidence has
79 parent and 79 exec-child probes passed, zero received UDP packets and task
process-group cleanup. PostgreSQL alone retains #61's documented SCRAM/loopback
exception because native `setsid` is denied. Chromium runs separately with its
own sandbox intact, exact task-origin application request allowlisting and
unexpected-request failure. This browser boundary is not host-wide egress or
hostile-code/filesystem isolation. No host security setting was changed.

All final task services and browsers stopped; synthetic stored credentials were
invalidated, private configuration/key files scrubbed, and the disposable database
stopped. Source/manifest, network-proof and cleanup failures prevent success.
The final read-only process audit finds no remaining task browser/smoke process;
concurrent authorized frontend build processes and unrelated user processes were
left untouched. The safe compact summary is
`build-worktrees/frontend-completion/browser-evidence-summary.json`; raw evidence
and source snapshots remain in each attempt.

Failures remain preserved: attempt 01 found a fixture layer path typo; 02 exposed
cross-origin map/print failures; 03 rendered the map but still failed print CORS;
04 and 05 passed both browser phases but failed immutable-tooling checks because
Python generated 12 and then one bytecode cache file. The final runner propagates
`PYTHONDONTWRITEBYTECODE=1` through the unchanged supervisor's nested execs rather
than excluding unexpected files. Those failed attempts remain failed.

This proves one public map candidate combination. It does not establish private
browser access, SSO, full sharing/policy, publishing fidelity, accessibility,
production deployment, source/license closure, or FND-02 task acceptance.
