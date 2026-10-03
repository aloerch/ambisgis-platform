# Supplemental installation authorization and recovery checks

This driver increment addresses PLT01-GAP-04 and the repeated journey portion
of GAP-06. Its Python tests are inert protocol, cleanup and independent-oracle
guards. No successful installed journey, native permission mutation or restored
service is claimed until the integrator runs the independently reviewed driver
against a fresh selected installation and binds the actual receipts.

The existing native Guardian object-permission API remains authoritative.
`catalog_permission_probe.py` derives one unmanaged diagnostic ResourceBase UUID
and the installation viewer from the existing private configuration and markers.
It uses the catalog serving role, never the initializer/migration role. It
requires the viewer initially ungranted, snapshots the sample's native user/group
grants and relevant identity/group/global policy, and accepts only a bounded
grant/revoke/grant sequence plus finish. Each change commits the one
`view_resourcebase` tuple using native `assign_perm`/`remove_perm`. The exact
program is bound to the catalog container and retained in the bundle closure.
There is no public admin endpoint, arbitrary code/SQL, object selection, copied
policy model or new service dependency.

The journey keeps the same viewer access token across allow, deny and allow
phases. Each phase checks gateway features/map/metadata and direct-engine
features/map; each positive response passes the independent feature/pixel and
metadata oracles. Regranting and successfully reading with the same token proves
that the intervening denials were item-policy changes, not token revocation.
The child session restores its initially absent tuple in `finally`, including
on input errors or stdin EOF, and compares the complete original policy snapshot.
The parent requires this acknowledgement and confirms final outsider denial.
Token-family cleanup remains the outer `finally`. Restoration errors, a lost
child or forced termination fail acceptance and require reconciliation; they
cannot be reported as restored. Unrelated concurrent policy changes are never
overwritten merely to reproduce the snapshot. Concurrency qualification remains
a separate requirement.

Actual wire negatives include repeated Authorization headers (same credential,
both orders of owner/outsider), malformed/extra/duplicate fields, unsupported
versions/resources/operations, engine administration paths and POST/PUT/DELETE
methods. The direct client targets only `geoserver:8080` beneath `/geoserver/`.
Its only nonempty body is a fixed WFS transaction containing zero feature
operations. Before constructing a connection, the method, literal path/query
and body must match the finite declared acceptance cases: the two exact fixture
queries and their listed malformed GET variants, the two fixed admin GET paths,
bodyless write-method checks on the exact fixture queries, or the empty
transaction POST to `/geoserver/wfs`. Administrative writes, other resources,
path normalization/encoding alternatives and arbitrary bodies are rejected.
The original broad-prefix admission is retained as an inert failing regression
in `acceptance-target-negative-001`; no connection or service was contacted.
The driver checks the source-defined gateway404/direct403 route boundaries and
denied malformed data responses, then repeats positive independent oracles to
detect unintended data or metadata changes. These requests are the ordinary
declared product-boundary checks, not the held runtime vulnerability probe.

Full journeys repeat after restart, repeated init/up and renderer recovery.
The existing old-title and exact installation/credential checks run first, so
a journey's later metadata edit cannot hide lost state. Native principal IDs,
resource UUID and restored policy fingerprint must remain equal across runs.
During the renderer fault the gateway must remain running and return its actual
`/health/live` response while useful map readiness is false and doctor fails.

The full port/nonloopback/IPv6/egress matrix, UID/GID/passwd and SELinux behavior,
read-only-root/capability/seccomp/cgroup observations, concurrent initialization,
installed SQL-role checks, log redaction, transient-unit/process cleanup and
host portability remain unpassed separate acceptance items. The held targeted
probe stays held. Neither these unit tests nor a later successful bounded
journey replaces those items or establishes full installation/MVP acceptance.
