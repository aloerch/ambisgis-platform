# Owned GeoNode REST role-service contract

This bounded FND-02 candidate reuses owned GeoServer `src/extension/authkey`.
It supplies `org.geoserver.security.GeoServerRestRoleService` and configuration
alias `authKeyRESTRoleService`. Packaging the module does not configure its
separate URL-key authentication filter. The service remains read-only.
`role-service-repairs.json` binds exact original/repaired source bytes;
`role_service_repair.py` verifies every input and predicted output before writing
a disposable source copy. Original archives are unchanged. Fresh security review
is required; full unified policy, source closure and release remain unaccepted.

## Authority and payload

The active role service and OAuth configured role service refer to this REST
service. OAuth `UserGroupService` may retain XML identity records solely for
existence/enabled state. Their groups and grants must remain empty.
`AbstractUserGroupService.loadUserByUsername` recalculates authorities from the
active role service on each load. OAuth also merges that active service, so
leaving XML as a separate active authority would retain an unauthorized grant.

The service sends `Authorization: ApiKey <dedicated role-service key>` to actual
GeoNode endpoints. This is separate from bearer user tokens and confidential
client tokeninfo Basic credentials. Keys never belong in URLs. HTTP redirects
are refused to prevent forwarding the separate service credential.

With `strictGeoNodeRoles=true`:

- `GET /api/users/<username>` returns
  `{"users":[{"username":"<exact>","groups":["fixture-readers"]}]}`.
  The username is encoded as one URI path segment, never interpolated into a
  JSONPath. Exactly one matching identity is required. Another identity,
  duplicate users, missing groups or any malformed member rejects the entire
  grant. `{"users":[]}` means no membership. GeoNode performs exact active-user
  lookup without email fallback.
- Raw groups match `[a-z][a-z0-9_-]{0,149}` and become `ROLE_` plus
  locale-independent uppercase. `fixture-readers` becomes `ROLE_FIXTURE-READERS`.
  Mixed case, prefixed aliases and reserved system names are rejected.
- `GET /api/adminRole` must return `{"adminRole":"admin"}`. GeoNode emits raw
  `admin` membership exclusively for active superusers. This becomes native
  `ROLE_ADMINISTRATOR`. Strict mode rejects local admin/group-admin overrides.
  Unavailable or malformed administrative mapping grants no roles.
- `GET /api/roles` returns the raw groups for discovery. User membership comes
  from the users endpoint, never the global role list.

No caller header, URL parameter or XML grant sets membership. GeoServer still
adds `ROLE_AUTHENTICATED` after valid token verification; protected fixture
resources require their specific reader role. Public access uses the native
anonymous filter and rules.

Legacy generic providers retain configurable JSON paths and default-off strict
behavior. Per-instance caches, atomic parsing, safe URI segments,
locale-independent conversion and redirect refusal apply to both modes.
Malformed legacy arrays no longer preserve preceding partial grants.
Strict mode uses retained Jackson with duplicate-key detection and
`FAIL_ON_TRAILING_TOKENS` before extracting any field. JsonPath/json-smart remains
only in the legacy path. Strict by-name/group lookup validates the complete role
array before a match can return; malformed later values cannot preserve an
earlier grant.

## Caches and failures

| Layer | Mechanism/fixture setting | Consequence |
|---|---|---|
| GeoNode strict responses | Live committed ORM membership; no response cache | Fresh accepted lookup reads authoritative state. |
| REST role responses | Per-service Guava `expireAfterWrite`, 1000ms, maximum 100, concurrency 4 | Hits never renew entries. Expired failure has no stale fallback. Key changes partition cached data by SHA-256 of endpoint and credential. |
| OAuth authentication/authorities | Guava idle and absolute lifetimes of 2s | Stateless hits never put again. Expiry repeats verification and role calculation. |
| XML users/groups | In-memory identity configuration; file check interval 0 | No mirrored grants. Authorities recalculate from active REST service. Identity provisioning remains explicit. |
| GeoFence decisions | Native refresh 15000ms, expiry 30000ms unless fixture overrides | With role filtering, reader removal changes RuleFilter.role to UNKNOWN; old-role cache keys cannot satisfy new authorities. Fixed resource rules stay unchanged. |

The selected embedded GeoFence Spring context wires `SecurityContextUserResolver`,
which reads current Authentication authorities. It does not wire the older
`InternalUserResolver`, which searches inherited stores. Runtime inspection must
confirm that selection in the exact packaged artifact.

Configured `connectTimeout=1500` and `readTimeout=1500` are positive experimental
milliseconds. Defaults remain 30000. Pool acquisition uses the connect limit.
Read timeout bounds idle reads, not arbitrary total response time under slow
trickle. HTTP failure, timeout, malformed JSON and missing identity grant no
fresh privileges. Previously successful snapshots may authorize only for their
remaining absolute cache lifetimes. A malformed HTTP success can itself be cached
until expiry, producing temporary denial before recovery.

Role/authentication caches act serially: approximately 1s + 2s stale snapshot
potential in the healthy fixture, plus in-flight timing and sampling uncertainty.
The healthy propagation deadline is 7 seconds. Role transport failure has a
separate 15-second first-denial deadline and 35-second three-response confirmation
deadline, derived from up to six serial 1500ms lookups per authentication, serial
cache lifetime and sampling margin. These are fixture acceptance deadlines;
observations are not a proven production maximum/SLA. Grant/removal/demotion keep
the same valid token, leave fixed rules/XML unchanged, avoid restart/manual cache
clearing and sample from committed-state acknowledgement with a monotonic clock.
Restart, token revocation and account disable/deletion are separate cases.

## Native regression boundary

`AmbisGISRestRoleServiceTest` contains 37 focused native cases: exact identity and
case binding, duplicate rejection, canonical/reserved names, malformed partial
arrays, mapping failures, credentials, timeout, service-instance isolation,
credential rotation, repeated-hit absolute expiry, recovery, complete-document
JSON parsing, duplicate keys and atomic by-name/group lookups. A deterministic
Guava ticker tests write expiry independently of sleep timing. Reflection permits
the same tests against unchanged source, preserving failing assertions instead
of compiler errors. Eight Python guard tests cover exact inputs, atomic
preparation, retained originals and unsafe paths. Executed results/counts belong
in receipts. Native transport mocks are separate from packaged-WAR HTTP evidence.


The superseded initial native runs under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation`
executed 28 cases: 26 new plus two inherited. `role-native-baseline-02` recorded
nine failed assertions, 11 errors and eight passes, with zero skips.
`role-native-repaired-02` passed all 28 with zero failures/errors/skips. Earlier
`-01` attempts failed preparation because the initial manifest omitted the
aggregate source-root prefix; they remain unsuccessful receipts.
`aggregate-repaired-01` packaged the full seven-profile candidate with tests
skipped; native execution is the separate receipt above. Its inventory and
logging receipts passed, but independent parser review later found that the
JsonPath parser accepted ambiguous duplicate fields and non-JSON syntax.
Those results do not accept the final security candidate. The exact WAR SHA-256 is
`04a52132b873fc6a991173885dcfe51c57b4ea636b9e3889afa4e1b39baafd90`.
Real permission propagation acceptance belongs to the separate HTTP journey,
not those packaging or mock-transport results.

The independent `java-review-probes/RoleParseReview.java` and
`parser-result-before.txt` preserve six actual administrative grants from
ambiguous syntax against the initial repaired candidate. The guarded parser
repair adds eleven native cases and requires a new complete aggregate plus
repeat HTTP evidence. Final run/artifact identities supersede the initial WAR
above and are recorded in the current handoff and evidence index.

Final parser candidate `role-native-repaired-03` passed 39 cases (37 added plus
two inherited), with zero failures/errors/skips. The same 39 tests on the prior
repaired candidate (`role-native-baseline-03`) failed eleven assertions, with
zero errors/skips. `aggregate-repaired-02` packaging skips tests explicitly;
its exact WAR `a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`
passed class/source inventory, logging and the real `integration-03` matrix.
See the handoff for measured timing, full counts and retained failures.
