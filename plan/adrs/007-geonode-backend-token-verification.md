# ADR 007: explicit GeoNode backend token verification

Status: engineering candidate; fresh human security review required before merge.
Task: FND-02, [issue #3](https://github.com/aloerch/ambisgis-platform/issues/3).
This follows owner-merged PR #59 and its repaired GeoServer WAR. It does not
approve a release, deployment or unified AmbisGIS authorization policy.

## Observed contract

The owned GeoNode 5.1.0 candidate is commit
`a1db97e81dfc26c16bb4ee1a5d2b408877af66c9`. Its actual HTTP login, CSRF-protected
consent and authorization-code exchange with S256 PKCE issued tokens from the
persistent native user/application/token models. Those tokens reached the real
configured GeoServer WFS and REST paths.

The retained `integration-baseline-01` run showed why the earlier synthetic
verifier's assumptions could not be transferred to GeoNode. Native tokeninfo
returned 200 with missing or wrong client credentials, credentials from another
application, and a token issued to another application. The latter also obtained
protected GeoServer data. An inactive token owner still received tokeninfo 200
and protected GeoServer access. A reader browser session combined with an
outsider token instead returned 403: the inherited session-aware lookup refers
to `token.key`, whereas the selected token model stores `token`.

These are observed component contract mismatches. The unchanged GeoServer code
requires a returned `client_id` but does not compare it with its configured
client ID. GeoNode's selected token validity predicate checks expiry/scopes, not
user activity. The legacy tokeninfo response also contains the submitted token
in JSON and an Authorization header, and expresses remaining lifetime in
milliseconds. Secret-bearing protocol responses were kept separate from
resource responses and public evidence.

## Decision and repair boundary

Add `OAUTH2_BACKEND_TOKENINFO_STRICT`, default **False**, and explicitly enable it
in the disposable backend fixture. The strict branch requires a confidential
application's Basic credentials and a token belonging to that application. It
requires a present, active user with a nonblank principal and a valid native
token. Missing, malformed or incorrect client credentials cannot fall back to
browser identity or credentials in the request body. Browser session tokens
cannot replace the submitted token.

Successful strict responses retain the identity/application/scope fields needed
by the existing WAR and explicitly retain milliseconds. They omit the access
token and Authorization header. Success and denial responses use `no-store`,
static errors and secret-free diagnostics. The selected OAuth Toolkit 2.2.3.1
stores application secrets as a plain field; this guarded implementation uses
Django's constant-time comparison. This is not an assumption about later
Toolkit versions or approval of its wider security behavior.

The source repair changes exactly five paths: `geonode/api/views.py`,
`geonode/settings.py`, `geonode/security/middleware.py`, and new
`geonode/api/backend_tokeninfo.py` and `geonode/api/test_backend_tokeninfo.py`.
The [repair recipe](../../build-support/geonode/verifier_repair.py) verifies exact
baseline hashes, rejects unexpected edits or collisions, and records every
output hash before the owned wheel is rebuilt. It does not monkeypatch an
installed application. Run004 retains a fresh build from the repaired source
with external networking denied and the full permitted source-change set checked.
The baseline installation and failed evidence remain intact.

Two inherited middleware steps otherwise run before the view: user Basic
parsing can fail on malformed client credentials, and session-expiry control can
change the surrounding browser session. In strict mode only, these steps defer
when Django resolves the request to the exact owned `verify_token` callback.
There is no path-prefix whitelist or global authentication bypass. The strict
view still authenticates the client. Other routes, OAuth middleware and CSRF
configuration remain intact. The default-off branch preserves the inherited
tokeninfo response; enabling strict mode is an explicit compatibility change,
not demonstrated general browser/OIDC compatibility.

No Java code or dependency input changes are required. The integration retains
WAR SHA-256
`8a79a2cf7647be2f28591d7f04f975dc84cb00baaaea35cb3d5f2f293ea8f39f`.

## Evidence and remaining acceptance

`integration-repaired-01/native-tests.log` records **38 passing native tests**:
34 strict-verifier regressions and four unchanged authentication/encryption
cases, with no failures, errors or skips. Tests use native Django clients,
middleware, ORM models and rollback transactions on the migrated disposable
PostgreSQL catalog. They include cross-application denial, inactive/deleted
users, malformed credentials, expiry/revocation, token-free responses, expired
browser context preserved on both success and denial, default-off compatibility,
and a positive ordinary user Basic request outside tokeninfo. Twelve separate
source-transform tests passed. These counts are not full GeoNode acceptance;
final `integration-repaired-04` additionally passed 176 GeoServer HTTP requests,
48 protocol assertions, real cache measurements and service restart. Exact source
and result identities are in the final indexed receipts and handoff.

The comparison fixture manually mirrors GeoNode principals into GeoServer XML
users/roles and GeoFence rules. Real GeoNode group removal does not automatically
remove the corresponding XML role. This is explicit comparison evidence, not
identity synchronization or an additional permanent catalog/policy authority.
Nonzero cache staleness and eventual denial require measured HTTP results;
neither the repair nor a passing native test guarantees immediate revocation.

GeoNode cookies sent to GeoServer do not establish new GeoServer JSESSIONID
browser-context acceptance. Resource-request correlation does not attribute
concurrent verifier calls from overlapping global counters. Live GeoNode log
capture covers WARNING/ERROR plus targeted native strict-verifier DEBUG tests,
not a complete dependency DEBUG audit. The existing PostgreSQL exception to the
unchanged loopback supervisor remains explicit; it is not complete host/egress
isolation.

Fresh human review covers the opt-in contract, middleware scope, application
binding, browser-state preservation, response minimization and fixture limits.
It gates merging this checkpoint, not already-authorized engineering. FND-02
remains In progress. Full frontend/SSO, unified policy, publishing, independent
source/toolchain closure, license/brand, FND-07/FND-08, P1/P6, signing and deployment
require their own evidence and approvals. The Java ledger remains 48 structurally
accounted, 12 unresolved and four partial; GeoNode dependency custody is separate.
