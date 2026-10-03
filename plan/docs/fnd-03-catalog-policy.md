# FND-03 catalog identity and ACL implementation

Platform `aloerch/ambisgis-platform`, repository ID `1376927351`, branch
`fnd-03/catalog-policy-v2`, based on verified PR #72 merge
`8c3612dd3e4ee992d930f1417798b66f467784e9`. The live
[claim](https://github.com/aloerch/ambisgis-platform/issues/4#issuecomment-5966057973)
is authorized by the standing owner delegation. FND-02 remains accepted/Merged.
The task branch subsequently merged PR #73 main at
`7812efa3502ec1d7004b485d35b433eea56ce13e`; the only conflict was the active
STATUS text, resolved to preserve both current task states and historical records.
The executed policy/compiler/harness bytes are unchanged. Initial independent
security review found no material issues, with 77 supplementary adversarial checks;
final integration test/review binding and PR merge remain pending. No product release or complete T-AUTH-ALL pass is claimed.

The implementation adds a read-only catalog policy module and gateway in
`services/control-plane/ambisgis_policy`, plus a source-compiled mandatory engine
servlet filter in `services/gateway/CatalogPolicyFilter.java`.
[ADR 011](../adrs/011-catalog-read-policy-boundary.md) explains the single-authority
model. The native GeoNode token, user, ResourceBase and guardian permission
records are consulted afresh at both boundaries. There is no cached positive
grant or asynchronous ACL mirror. Inherited engine role grants are empty in the
serving configuration and its administration routes are denied.

The [declared matrix](../../build-support/geonode/catalog-matrix.md) is exercised
against the actual owned GeoNode build, PostgreSQL/PostGIS and accepted revision-4
GeoServer WAR SHA256
`90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1`.
The final native attempt is retained at
`/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd03-runtime/attempt-03`.
[Sanitized runtime evidence](../verification/fnd-03-catalog-policy/runtime.json)
binds all twelve executed source files to the actual snapshots and compiler
receipt; [request evidence](../verification/fnd-03-catalog-policy/requests.json)
records response hashes, statuses, geometry assertions, mutation acknowledgments
and request timestamps without tokens or fixture passwords.

| Criterion | Actual evidence |
|---|---|
| Public/private/group reads through gateway and engine | 142 total successful HTTP assertions include anonymous public, owner/private, member/group, outsider denials and real Point(1,2) GeoJSON. |
| Revocation through both paths | First new requests after committed group removal, private-share removal, public removal, user disablement and native token deletion deny immediately, with unchanged bearer where applicable. No polling delay or cache clear. |
| Persistence, failure and identity separation | Thirty-two concurrent member/owner requests pass; catalog outage fails closed for public/private; catalog and engine restarts retain revocation and public functionality. |
| One policy authority, no raw admin access | Catalog mutations do not change engine policy configuration. Raw REST/web/cache admin is denied for anonymous, both users and the native administrator; unsupported routes/parameters/write operations deny. A private pre-boundary provisioning baseline records that inherited raw admin would otherwise be accessible. |
| Real dependencies and cleanup | 482 migrations, 70 native GeoNode auth tests, 2,843 unchanged owned installed files, exact accepted WAR, successful source compilation under socket denial, loopback runtime supervision, zero diagnostic secret hits, all services/database stopped and private configuration scrubbed. |

Supporting regressions pass: 118 GeoNode harness tests, four Java runtime input
tests, 444 package tests and four strict schema/example checks. Package checks
are not GIS acceptance. Their expected negative receipt fixture prints a
`receipt identity mismatch` JSON record after unittest reports success; the
suite itself has zero failures/errors/skips.

Two unsuccessful attempts remain retained. Attempt 01 stopped on a harness
log-file creation race before the new HTTP journey. Attempt 02 passed 94 HTTP
assertions then stopped on a helper name shadowing Python's concurrency module.
Both faults were corrected, neither attempt was counted as accepted, and all
their disposable services were stopped. Attempt 03 passes every declared row
and the outer supervisor/integrity/cleanup gates.

Reproduce with a **fresh** output path, using the host namespace:

```sh
flatpak-spawn --host /usr/bin/python3 build-support/geonode/run.py \
  --python /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation/run-003/venv/bin/python \
  --output /home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd03-runtime/attempt-04 \
  --integration --strict-verifier --strict-roles --catalog-policy \
  --build /home/revelberry/Projects/AmbisGIS/build-worktrees/json-jpeg2000-remediation/aggregate-04 \
  --war-sha256 90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1 \
  --java-profile plan/verification/json-jpeg2000-remediation/runtime-profile.json
```

This demonstrates the FND-03 spike's unchanged criteria, with deliberate limits:
one-node Linux loopback, WFS 1.0.0 GetFeature JSON for synthetic resources,
native OAuth browser-form issuance, native ORM sharing administration, no
installer or general OIDC/browser/TLS deployment. Wider service outputs, caches,
notebooks and frontend authorization still require their own T-AUTH-ALL tests.
The existing PostgreSQL supervisor exception remains recorded. No fork source,
dependency lock, workflow, default branch or remote repository state changed in
this worker increment. The parent integrator owns PR/tracking/merge actions.
