# F02-05 embedded GeoWebCache smoke

This is a finite combination fixture, not a cache framework or product policy.
It reuses the exact owned #61 WAR and retained strict GeoNode/role backend. No
component rebuild, standalone cache, upstream WAR or browser run is involved.

From the platform worktree, choose an **unused** output name:

```sh
flatpak-spawn --host /usr/bin/python3 -B build-support/gwc/smoke.py \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/combination-gwc/smoke-NEW

flatpak-spawn --host \
  /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation/run-003/venv/bin/python \
  -B -m unittest discover -s build-support/gwc -p 'test_*.py' -v
```

The host/IDE `/tmp` namespaces differ. The runner uses host Python 3.13,
retained GeoNode Python 3.12/Pillow, verified Temurin 17 and staged Jetty inputs.
The unchanged trusted-fixture loopback supervisor controls GeoNode, GeoServer,
the HTTP client and decoder. PostgreSQL alone uses the documented authenticated
loopback/native-setsid exception. These controls do not establish hostile-code,
filesystem, other-user or whole-host isolation.

`probe.py` defines acceptance before requesting tiles: actual capabilities,
PNG 256×256; independently specified Point(1,2), red 28px circle, projected pixel
position and radial/interior checks; genuine MISS with exactly one new entry;
identical request HIT with the exact layer/grid/index-derived persistent entry;
same config/data/WAR restart followed by HIT; invalid-layer OWS error with valid
control; real reader positive and anonymous/outsider denials before/after warming
and restart. urllib has no response cache, cookies or redirect acceptance.

The explicit `-Dgwc.context.suffix=gwc` is required by this aggregate's property
configuration. File-only attempts are retained failures; the exact resolver
ordering cause has not been proven. The new fixture's `gwc-gs.xml` explicitly
enables GWC data security, uses one PNG grid, 1×1 metatiles and zero async saving
threads. The existing source-supported authenticated GWC layer REST operation
creates only the two synthetic layers. Security filters, roles and fixed GeoFence
resource rules remain unchanged. Native authorization failure is HTTP400 with a
GWC HTML error page; only its exact protected-layer denial is accepted. An HTML
login page, generic 500 or empty exception does not count as denial.

The fixture's opt-in launcher diagnostic exports only active cache settings and
controller mappings. It does not export arbitrary beans or credentials. Native
startup/lazy authentication generate CSP/keystore/user schema files. Every
original configured security file must remain equal after initialization; the
entire active security set is then checked across tile requests and restart.
Catalog/style/cache settings and tile metadata/hashes are also checked across
restart. Failures in assertions, origin/integrity checks, capture, supervision or
cleanup fail the result. Each attempt is private and exclusive; prior caches,
outputs and failures are never deleted or reused. Credentials are invalidated
and scrubbed after task services stop; only resulting tile/config evidence stays.

See [the compact matrix](../../plan/docs/fnd-02-combination-smoke.md) for exact
reused-versus-fresh scope, retained attempt identities, pass/failure receipts,
limits and owner review. F02-06 source/license selection remains separate.
