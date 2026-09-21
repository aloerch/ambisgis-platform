# FND-02 source-owned GeoNode identity handoff

Repository `aloerch/ambisgis-platform`; branch `fnd-02/geonode-identity-integration`;
worktree `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-geonode-identity`.
[FND-02 #3](https://github.com/aloerch/ambisgis-platform/issues/3) remains **In progress**.
This checkpoint begins at verified main `360b1e87b392d0e6cb8bf64fac543f75e6f27eb2`:
the owner merged [#59](https://github.com/aloerch/ambisgis-platform/pull/59) from
reviewed head `c899ab0791ec87ef0a002b3953aa6a8268c4dc3e`. Its predecessor
[#58](https://github.com/aloerch/ambisgis-platform/pull/58) is also merged at
`b68e3d59bafb4bbf7b2007c76e5e59a25b4139e7`. Older dated open-PR observations
remain historical. Old branches, worktrees, failed attempts and custody are preserved;
the original plan checkout's user-modified STATUS is untouched.

## Source and runtime boundary

GeoNode owned commit `a1db97e81dfc26c16bb4ee1a5d2b408877af66c9` (tag 5.1.0,
package 5.1.0.post1) and owned MapStore client backend commit
`7ca4822125b67999c97cb4aa1faa84b8a28eee9b` (5.1.0) are independently built
into wheels. Run004 restores retained inputs with external networking denied,
checks exact source trees and the five-file verifier repair, rebuilds both owned
packages, installs 211 recorded distributions, and passes `pip check` and native
imports. A second fresh run005 rebuild/install replay has retained namespace,
interface/route and actual outbound-denial proof in `offline-replay-005-attempt-02`;
its recipe/input bytes stayed unchanged. The earlier proof-only wrapper failed on
route formatting before any build and is retained. Runtime acceptance uses the
unchanged run004 installation, not run005. Installed owned files are compared byte-for-byte to those built wheels
before and after runtime; a fresh private Python cache avoids stale installed bytecode.
Loaded module paths/hashes and executed fixture sources are retained per attempt.

[Recipes](../../build-support/geonode/README.md), the separate
[GeoNode dependency inventory](../verification/geonode-identity/dependencies.json)
and [evidence index](../verification/geonode-identity/evidence.json) distinguish
publisher binary inputs from source-built packages. GDAL and psycopg2 are built
against the retained owned native prefix, using retained CPython 3.12.14 headers.
GeoNode's GDAL requirement is explicitly adjusted to the owned 3.10.3 build;
headless execution omits uWSGI/pylibmc and uses a threaded stdlib WSGI server,
LocMemCache and synchronous Celery with an in-memory broker. Existing owned client
static assets are copied by native collectstatic; no npm rebuild or frontend
acceptance is claimed. Ten dependencies lack published sdists in the acquisition
record. Source-bearing wheels, publisher notices and retained metadata are accounted
for separately from complete source correspondence. Host Python/toolchain closure,
licenses and production suitability remain open. The Java ledger is unchanged:
**48 structurally accounted / 12 unresolved / four partial**, not a ledger for
these additional Python inputs.

The fixture loads actual GeoNode apps, URLs, middleware, Profile users, OAuth models,
role endpoints, signals and migrations. Native initialization uses **482 migrations**;
the selected source's six silenced system checks are disclosed, not added by this
fixture. The source default `UPDATE_RESOURCE_LINKS_AT_MIGRATE=False` leaves the optional
existing-dataset link/catalog repair loop inactive; native migration and auth/user/login
signal receivers remain connected. This empty-catalog slice does not test dataset link
repair. GeoNode and GeoFence have separate databases. GeoNode migration owner and
runtime DML roles are separate: the actual runtime is not superuser, cannot create
roles/databases/schema objects, has no replication/BYPASSRLS, owns no relations and
is not a member of the migration role. Only the task fixture cluster is touched.

The WAR is unchanged from #59, SHA-256
`8a79a2cf7647be2f28591d7f04f975dc84cb00baaaea35cb3d5f2f293ea8f39f`.
It is staged and loaded as that exact artifact, with class/library origins checked.
No newly compiled Java is represented as being inside this WAR. The application
fixture enables #59's default-false stateless bearer option. JDK connect/read
timeouts of 1500ms bound the transport-failure probes; these are runtime properties,
not a Java source change.

## Native findings and guarded repair

The preserved baseline actually issued authorization-code tokens with native login,
CSRF, user consent, S256 PKCE and state checks. It then demonstrated real failures:
tokeninfo accepted missing/wrong client authentication, another client's credentials,
a token belonging to a second application and an inactive principal. GeoServer
accepted the wrong-application and disabled-owner tokens. A reader session changed
lookup of an outsider token and produced a native 403. Those baseline expectations
were retained as failures.

[ADR 007](../adrs/007-geonode-backend-token-verification.md) explains the narrow
source-owned repair. `OAUTH2_BACKEND_TOKENINFO_STRICT` defaults **False**; this
fixture enables it explicitly. Strict mode requires the registered confidential
client's Basic credentials, binds the supplied token to that client, checks native
validity and the active nonempty user, and never uses a browser session as fallback.
Its token-free, no-store response preserves GeoNode's **milliseconds** contract.
Exact-view middleware guards prevent client Basic credentials being interpreted as
user credentials and prevent browser session mutation on this endpoint. Other
routes, the shared legacy verifier, native issuance, consent and CSRF remain intact.
This new security behavior requires fresh human review before merging.

The configured role service uses explicitly mirrored XML principals/roles and
native GeoFence policy. GeoNode's actual role/user/admin endpoints require their
separate ApiKey; bearer verification credentials do not replace that protection.
The exact WAR lacks the authkey extension containing GeoServerRestRoleService, so
this fixture does not claim automatic GeoNode role synchronization. Real GeoNode
group removal is observed through its protected API, and access through the local
XML comparison remains a limitation until a supported authoritative policy path
exists. FND-03 or unified product authorization is not accepted by this checkpoint.

## Results and interpretation

Frozen implementation: `08d1d910552f47d1ab8893c4a7fcd42c0cbacb44`;
`build-support/geonode` tree `56ea403505f5e4b00d5776b978fe6aae69d3597d`.
Subsequent checkpoint changes are documentation/evidence only. Executed tooling
hashes bind the final runtime to these Python files. The evidence index and
publication record carry the final outcomes and PR identity.

Fresh checks passed **96 GeoNode harness tests**, **366 Java tooling tests**,
**176 plan-package tests** and **four schema/example checks**, with no failures,
errors or skips. The independently rerun #59 synthetic configured-WAR suite passed
**177 HTTP requests plus one session-policy assertion** (178 records), including
restart. These remain separately labeled synthetic regression results. No new
Java JUnit suite ran: the unchanged Java source and WAR retain #59's historical
708 cases (707 pass/one inherited skip); those are not fresh native results here.
Package tests are distinct from native/GIS acceptance.
The strict runtime's selected **38 native tests** consist of four unchanged native
auth/encryption tests and 34 repaired-verifier ORM/Django Client cases; failures,
errors and skips are all zero. They include default-off compatibility, malformed
Basic headers, cross-application rejection, expired/deleted/inactive users, stale
browser-session preservation and ordinary Basic authentication outside tokeninfo.

Final `integration-repaired-04` returned **exit 0**. All **176 GeoServer HTTP
requests** passed (168 initial, eight after restart), as did **48 protocol assertions**
across **102 harness-driven GeoNode HTTP requests**. Assertions and requests overlap;
they must not be summed as distinct HTTP traffic. All 64 sequential/concurrent
resource requests had exactly one matching passive case/status record, and actual
sequential servlet workers served both allowed and denied identities. The unchanged
supervisor passed 79 parent and 79 exec-child probes, observed zero UDP packets,
and confirmed task-group cleanup. Both services, PostgreSQL and credential cleanup
completed. All 2,841 installed owned files matched before/after.

With a real two-second authentication cache, revoked access persisted through
**1.7713s** and was denied by **2.0496s** after the revocation request began.
A four-second stored expiry was denied by **4.2705s** after its mutation command
completed. These are bounded observations, not an immediate-revocation guarantee.
After native group removal, XML-authorized access remained 200 at **1.6916s** with
no verification and at **2.2822s** with fresh verification: policy propagation is
explicitly unimplemented. Native-success-gated timeout and truncated-response
probes denied access in 1.5105s and 0.0257s respectively. All six startup/restart
logger controls appeared once; raw/late and known/credential/PEM/opaque source
redaction counters were zero in their documented capture scope.

The real HTTP journey uses public/protected WFS and administrative REST resources,
positive controls on the same routes and readback after denied writes. It includes
real HTTP issuance and revocation, controlled stored-token expiry, active unmapped
and removed users, inactivity, group changes, sequential/concurrent requests,
foreign GeoNode cookies, cache observations and restart against persistent fixture
state. The delay/truncated-body tests are explicitly injected transport faults
**after actual native verifier success**; they are not claims that GeoNode emits
malformed protocol. A separate stopped-verifier test checks unavailable service.
The preceding #59 synthetic suite remains separately labeled regression evidence.

GeoNode cookies sent to GeoServer are not native GeoServer browser SSO. #59's native
JSESSIONID context-restoration tests remain historical. Browser logout and OAuth
grant lifetime are tested separately; logout is not asserted to revoke all grants.
Concurrency attribution uses individual GeoServer request IDs, statuses and workers;
no global verification-counter window establishes per-request concurrent identity.
Selected OAuth issuance/verification values are checked against explicit allowed
channels; duplicate headers and resource/error outputs are scanned. Intermediate
login/consent HTML retains safe metadata, not an exhaustive raw-response leak audit. Live source logging is WARNING/ERROR, with
explicit capture controls and redaction counters; targeted strict-helper DEBUG
coverage is separate from a full dependency DEBUG audit.

## Retained failures, containment and resumption

Retained root: `/home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-identity`.
Original acquisition and failed startup inputs remain unchanged; corrected immutable
custody is `/home/revelberry/Projects/AmbisGIS/source-archives/geonode-identity-v2`.
Startup01 exposed settings initialization ordering; startup02 exposed incompatible
preferred binary django-tastypie 0.14.0 against Django 5.2.15. The supported original
range admits explicitly selected source-built 0.14.7. Startup03 passed full migration,
initialization, native tests and cleanup. Baseline01 preserves the actual verifier
security failures. Repaired01 passed its 38 native tests and all 69 reached GeoServer
rows, then failed on harness logout form selection; strict token-response expectations
and disabled-account redirect recognition were also corrected from inspected source.
Repaired02 reached all 176 GeoServer rows, cache/role/expiry and restart checks,
then failed its native logout cookie classification; the source response was the
expected 302. The final harness classifies only the decoded native signed-out
notification on this row, verifies the browser session cookie is cleared and keeps
credential/duplicate-cookie scans. It does not authenticate a message cookie.
Repaired03 passed all resource and protocol rows but failed the sequential
mixed-worker coverage gate: a repeated four-identity order aligned with worker
scheduling. The fixture now rotates each round while preserving 32 sequential and
32 concurrent requests and the actual mixed-worker proof requirement. The change
is in the final frozen implementation; it does not change authentication decisions.
These attempts remain unsuccessful receipts, never overwritten by later success.

GeoNode and GeoServer run under the unchanged trusted-fixture loopback supervisor.
PostgreSQL alone retains #59's explicit exception because backend setsid is denied:
SCRAM on 127.0.0.1 TCP only, no Unix listener, owned binaries, explicit shutdown.
The supervisor is not a sandbox against hostile code, filesystem access or unrelated
loopback services. No additional daemon is moved outside it. Every attempt has fresh
private output/configuration; cleanup removes OAuth grants/tokens/sessions, invalidates
fixture passwords/client secrets, scrubs ephemeral config/keys and stops task processes.
Failed integrity, logging, network proof, cleanup or tests must fail the overall receipt.

To repeat the exact integration from retained run004, use a fresh output directory:

```sh
flatpak-spawn --host /usr/bin/python3 build-support/geonode/run.py \
  --python /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-identity/run-004/venv/bin/python \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-identity/REPLACE_WITH_FRESH_RUN \
  --integration --strict-verifier
```

Full frontend/browser SSO, publishing, unified policy, restore, source/toolchain
closure, FND-07/FND-08, P1/P6 and security/license/signing/deployment gates remain
unaccepted. This is a bounded component checkpoint, not a released GIS distribution.
The next dependency-ready work remains within In-progress FND-02: implement and test
the owned GeoNode-to-GeoServer role-service path (including its missing WAR module,
separate endpoint authentication and measured policy-cache propagation), then repeat
the exact resource matrix. Verify current main, issue dependencies and source custody
before a new branch; do not repeat completed token issuance work or silently promote
FND-03. Owner review of this PR gates merging; it does not authorize deployment.
