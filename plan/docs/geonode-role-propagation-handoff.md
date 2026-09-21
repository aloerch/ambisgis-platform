# FND-02 authoritative GeoNode role propagation

Repository `aloerch/ambisgis-platform`; branch `fnd-02/geonode-role-propagation`;
worktree `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-geonode-roles`.
[FND-02 #3](https://github.com/aloerch/ambisgis-platform/issues/3) remains **In progress**.
Frozen implementation: `d935fb48a7e0721b1e25f67eccfe3ed836c890fc`.
GeoNode tooling tree `c4543603a01b6999626f99f7900a5988594ceae4`;
Java tooling tree `e55a18232e9f59124fbd151b3135556ee736b227`.
All 120 executed tooling files match that implementation. Later changes are
handoff/evidence only. Publication identity and owner actions are recorded below.

The verified starting main is `a58eff30305de4f4f24b8f5c9075672c4745aa5f`, the
owner's merge of [#60](https://github.com/aloerch/ambisgis-platform/pull/60), whose
reviewed head was `7dfe6288bf1383be29e18de467aa0801f798ba6f`. Its prior branch,
archives, manual-XML comparison and failed evidence remain intact. Its dated
open-PR prose is historical, not a remaining owner obligation. The original plan
checkout's user-modified STATUS was preserved. Owner login/ID, relevant repository
IDs/remotes, issue/dependency, main ancestry and worktrees were checked before writes.

## Implemented boundary

GeoNode's active exact usernames, canonical group membership and is_superuser now
control actual configured GeoServer/GeoFence WFS and REST resources over authenticated
HTTP. The fresh aggregate includes source-built authkey for GeoServerRestRoleService;
URL-key authentication is not enabled and the protected-route bypass probes deny.
The active role service and OAuth UGS path agree. Local XML records supply identity
existence only; role grants and local group memberships are empty. Fixed resource
rules are enforced by real GeoFence, and their HTTP readback hashes stay unchanged.

[ADR 008](../adrs/008-authoritative-geonode-role-service.md), the
[pre-run matrix](../../build-support/geonode/role-matrix.md) and
[Java contract](../../build-support/java/role-service-contract.md) describe the
opt-in strict endpoints, dedicated nonstaff/non-superuser service Profile and
separate ApiKey, exact username binding/no email fallback, reserved-name handling,
strict JSON, cache isolation and failure policy. Membership/admin changes are
controlled native ORM operations, not an asserted HTTP administration workflow.
GeoNode's inherited middleware may issue configuration cookies; GeoServer bearer
requests create none. Strict tokeninfo's confidential-client binding, active-user
validation, token-free response, millisecond contract and narrow scope remain tested.

## Exact artifacts and custody

Final WAR SHA-256:
`a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`.
GeoNode wheel SHA-256:
`d4194e17bfaa517d829b47550022bc0831a3fe0872483d968ecbf29251cd5c28`.
MapStore client backend wheel SHA-256:
`1ba859afca3993da35f05e838185fa027d0f9779a4cb26124dd638617157442b`.

Retained root:
`/home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation`.
Final runs: `run-003`, `build-proof-003`, `aggregate-repaired-02`,
`aggregate-repaired-02-inventory`, `aggregate-repaired-02-logging`,
`role-native-repaired-03`, `oauth-native-regression-01`, `native-02`, `integration-03`.
The [compact index](../verification/geonode-role-propagation/evidence.json) binds
source trees, guarded recipes, configuration, artifacts, actual receipts and
independent review. [HTTP evidence](../verification/geonode-role-propagation/http-results.json)
and [loaded configuration/class origins](../verification/geonode-role-propagation/configuration.json)
select validated non-secret fields; raw private configuration is never copied.

The source tuple is unchanged. Seven profiles are the previous importer,
oauth2-geonode, geofence-server, geofence-server-postgres, printing and postgis
plus authkey. All 157 aggregate modules packaged with tests **explicitly skipped**;
369 libraries, 406 WAR files and repaired class definitions were checked separately.
The only additional library is owned-source-built gs-authkey; no external library
was added, removed or changed, and no new input acquisition was needed. Retained
Java dependency/source inputs and notices remain authoritative. The Java ledger
stays **48 structural / 12 unresolved / four partial**. The separate
[GeoNode dependency inventory](../verification/geonode-identity/dependencies.json)
is unchanged: 211 installed distributions, not a complete third-party source rebuild.
Both rebuilt Python wheels and all 2,843 installed owned files were verified before
and after runtime. The network-denied build proof is separate from loopback runtime.

## Actual results and measured limits

Final `integration-03` exited **0**: **393 GeoServer HTTP requests** (384 initial,
nine after restart), **82 protocol assertions across 156 harness-driven GeoNode
HTTP requests**, and **70 native Django cases** passed. Protocol assertions overlap
requests and are not additional traffic; internal role-service HTTP is additional
native endpoint traffic. All 96 sequential/concurrent resource cases have one
matching request/status record; actual servlet workers reused allowed and denied
identities. Role checks include revoked/restored concurrent states.

| Change, same valid token | Last permitted response after committed acknowledgment | First changed response | Three stable target responses by |
|---|---:|---:|---:|
| Reader group removal | 0.760808 s | denial 1.084476 s | 1.600277 s |
| Reader group restoration | — | allowed 0.559804 s | 1.082163 s |
| Administrator demotion | 0.775988 s | denial 1.094112 s | 1.607412 s |
| Administrator restoration | — | allowed 0.543625 s | 1.065615 s |
| Role service principal disabled | 0.757084 s | denial 1.127973 s | 1.644939 s |
| Delayed role HTTP responses | 1.074536 s | completed denial 10.436227 s | 10.952597 s |

Times use the host monotonic clock and committed native mutation acknowledgment.
Sampling is 250ms plus request duration; exact request start/end intervals are
retained. These are observations, not an exact revocation instant, proven maximum
or production SLA. The delayed request spent about nine seconds in six serial
1500ms role lookups; **10.436227s is completed denial latency, not ten seconds of
successful stale access**.

REST snapshots expire one second after write; OAuth authentication expires after
two seconds absolute/idle. Hits do not renew absolute expiry. GeoFence's current-role
cache key changes on membership removal; its fixed-rule refresh/expiry defaults
are 15s/30s. GeoNode strict role reads have no application membership cache and
return no-store. Healthy membership changes retained a seven-second deadline.
Failure tests declared a separate 15s first-denial and 35s three-confirmation
window from serial calls/cache/sampling; any return to the prior privilege state
fails. Read timeout bounds idle reads, not adversarial total stream duration.

Missing/wrong/revoked service credentials, actual timeout, malformed JSON,
syntactically truncated JSON, an HTTP body shorter than advertised, duplicate
fields and trailing content deny after finite old-cache validity and recover
automatically. Token verification stays independently healthy. Unknown/inactive
identities, reserved names and username/email collisions have focused native/HTTP
coverage. Administrator demotion prevents a later write; readback proves no object
was created. Fixed rules/XML stay unchanged. A later restart with persistent
revoked membership denies before restoration, and verifies the same artifact.

Token revocation is separate: last allowed at 1.7772s and denied by 2.0592s after
revocation began. A stored four-second expiry was denied by 4.3634s after its
mutation command completed. No immediate-revocation or global browser logout claim.

Fresh checks: **112 GeoNode harness**, **379 Java tooling**, **176 plan tests** and
**four schema/example checks**, all pass without skips. Selected Java role tests:
**39/39 pass** (37 added, two inherited). Fresh OAuth/security: **708 cases,
707 pass and one inherited AuthenticationFilterTest.testSSL skip**, zero failures/errors.
Native GeoNode: 32 role + 34 strict verifier + four inherited cases, zero skips.
Packaging and mock-transport native cases are distinct from real HTTP acceptance.
Unrelated database/Jupyter/XML/printing suites were not rerun.

Eight live capture controls appeared exactly once; raw/late known-secret hits and
all recorded source redaction counters were zero. GeoServer selected security
logging is exercised; GeoNode live capture is WARNING/ERROR, not a full dependency
DEBUG audit. Both services and the disposable database stopped; stored credentials
were invalidated and private files scrubbed. The unchanged supervisor passed 79
parent and 79 exec-child probes, observed zero UDP packets and confirmed task-group
cleanup. PostgreSQL alone retains the documented SCRAM/loopback supervision
exception for native setsid. This is not hostile-code/host/filesystem isolation.

## Preserved failures and independent review

`integration-01` stopped at the harness's unsupported PUT/DELETE negative probes;
its 66 preceding resource checks passed. `integration-02` failed its original
seven-second timeout deadline at 10.36s. The healthy bound was retained; the final
fault-only timing declaration reflects the actual serial call path.

Initial Java role repair passed 28 native cases but independent compiled-JAR
review found permissive JSON parsing and a partial global-role lookup. The old
candidate with the eleven new tests (`role-native-baseline-03`) failed exactly
11 assertions, zero errors/skips. Final strict parsing rejects those cases and
passes all 39. Independent positive/negative probes against final WAR library
bytes confirm reader/admin mapping and malformed-response denial. The earlier
original-source baseline (nine failures/11 errors/eight passes) and initial build
preparation failures remain retained.

`native-01` preserved 19 failing records from overly broad GeoNode cookie/session
metadata assertions; no role authentication failure was concealed. Corrected
native tests allow only the exact inherited configuration metadata shape and
require other authentication/session fields unchanged. Final rebuilt `run-003`
passes all 70. Initial plan invocation lacked jsonschema (seven skips; strict
validator failed); the retained validation environment then passed all 176/four.

Independent review covered Java changes, build/profile guards, the Python source
contract and HTTP evidence. The final detailed reviewer authored the Python repair
and explicitly excludes it from their independent source-review claim; a separate
agent reviewed that contract. Human security review remains required. Automatic
approval review refused an initial raw configuration/readiness export; a read-only
field audit and explicit validated allowlist replaced it. No raw export occurred.

## PR and Project publication

Review [PR #61](https://github.com/aloerch/ambisgis-platform/pull/61) against
`ambisgis/main`. Its publication snapshot head is
`7ebc480fae0dedc70271ed17756387f5fefedd07`; the source implementation is frozen at
`d935fb48a7e0721b1e25f67eccfe3ed836c890fc`. Later publication documentation commits
leave both tooling trees unchanged. The final pushed head is pinned in the
[FND-02 issue evidence comment](https://github.com/aloerch/ambisgis-platform/issues/3)
after that push; verify the live PR head before reviewing.

[Project publication evidence](../verification/geonode-role-propagation/project/README.md)
records **74 items: 66 tasks + eight PRs**. Exactly two authorized writes added
#61 by content identity and linked its Evidence; all 73 prior item values/archive
decisions, fields, repositories and view configurations/order were preserved.
No Task ID, Delivery or Review gate was copied to the PR. FND-02 stays In progress;
only #61 matches the unchanged `is:pr is:open` queue. This is API readback, with no
new UI setup claim. Final read-only verification uses a fresh retained directory.

## Resume and owner boundary

From the new platform worktree, use fresh output directories; never overwrite an
attempt. The final exact runtime command was:

```sh
flatpak-spawn --host /usr/bin/python3 build-support/geonode/run.py \
  --python /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation/run-003/venv/bin/python \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation/integration-03 \
  --integration --strict-verifier --strict-roles \
  --build /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation/aggregate-repaired-02 \
  --war-sha256 a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52
```

For reproduction change only the output to a new name, such as `integration-04`.
Build commands and exact retained invocations are in the recipes and indexed
receipts; the disconnected Python replay is `build-proof-003/replay.py` (one
immutable attempt, not a file to rerun into its old output). Required plan commands
were run from this worktree's `plan/` using the verified validation environment:
`PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 -m unittest discover -s tests -v`
and `PATH=/tmp/ambisgis-validation-venv/bin:$PATH python3 tools/validate_package.py --require-schemas`.

Owner review should inspect ADR 008, guarded source changes, malformed-response
failures/fixes, actual role readbacks and timing/failure boundaries. Approval gates
merging this new security-sensitive checkpoint, not continued authorized engineering.
No merge, auto-merge, deployment, release, branch deletion, default-branch change,
workflow/secret installation or new repository was performed.

The next dependency-ready bounded work is continued FND-02 source/compatibility
closure, choosing one unresolved Java ledger entry and proving its retained-source
repair/build correspondence. Full catalog-object sharing/unified policy, frontend
and browser SSO, publishing, multi-node revocation, source/toolchain closure,
FND-03/FND-07/FND-08, P1/P6 and final security/license/signing/release acceptance
remain open; none is automatically closed by this slice.
