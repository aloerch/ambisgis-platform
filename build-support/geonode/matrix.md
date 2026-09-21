# GeoNode identity integration pretest contract

This is a disposable FND-02 component fixture. Source candidate GeoNode 5.1.0
and owned MapStore client backend use real URLs/middleware/models/migrations.
The full frontend is deferred. PostgreSQL catalog owner/runtime identities are
separate from GeoFence and managed geodatabases. No production policy acceptance.

| Principal | Public WFS | Protected WFS | Administration |
|---|---|---|---|
| Anonymous / invalid / expired / revoked token | intentional public point | deny | deny |
| fixture-reader | public point | private point and geometry | deny, unchanged state |
| fixture-outsider | public point | deny | deny, unchanged state |
| fixture-disabled / removed / unknown | public policy only | deny | deny |
| fixture-unmapped (real GeoNode user; absent in GeoServer) | public policy only | deny | deny |
| fixture-admin | public point | private point | narrow disposable workspace create/read/delete |
| Token from second registered application | public policy only | expected application-bound denial; unexpected acceptance is a finding | deny |

Initially the #59 configured XML users/roles are explicit comparison counterparts,
not automatic synchronization. Reader maps to ROLE_FIXTURE_READER; administrator
to FIXTURE_ADMIN/ROLE_ADMINISTRATOR; outsider has no reader grant. Real GeoNode
role endpoints must separately demonstrate API-key access controls and group
changes. Any transition to HTTP-backed roles must be independently evidenced.

Positive tokens require actual HTTP authorization-code issuance, user login,
CSRF, consent, state and S256 PKCE. Controlled model mutations are negative
fixtures only. GeoNode verification response `expires_in` must be measured in
milliseconds; do not assume client Basic authentication, application binding,
active-user checks or browser-session behavior from the view alone.

Protected route controls include real WFS and REST. Fresh-token and primed
nonzero-cache expiry/revocation/role-change results are separate observations.
Immediate stale access is measured, not relabeled immediate revocation. Sequential
and concurrent cases require individual correlation, no inferred global counters.
Restart preserves the disposable database and configuration; persistence alone
is not authorization. Issuance/verification secrets may remain in authorized
protocol memory only; response headers (including duplicates), resource bodies
and captured logs are checked for leaks. Failed startup, assertion, integrity,
network proof, evidence or shutdown must yield an unsuccessful receipt.
