# Authoritative role fixture acceptance matrix

Declared before the first strict-role HTTP execution. The old XML comparison is
historical evidence in PR #60 and remains reproducible without `--strict-roles`.
The new candidate uses exact rebuilt Python wheels and the newly packaged complete
WAR; it does not use the old WAR as new acceptance evidence.

| Principal/state | Public WFS | Protected WFS | Administrator REST |
|---|---|---|---|
| Anonymous | PUBLIC_WITNESS Point(1,2) | deny/no protected content | deny |
| Active outsider with valid token | public | deny | deny |
| Active reader, GeoNode fixture-readers member | public | PRIVATE_WITNESS Point(1,2) | deny; writes leave state unchanged |
| Same reader, membership removed, same valid token | public | stable denial within measured deadline | deny |
| Same reader, membership restored, same valid token | public | real geometry/content returns | deny |
| Active GeoNode superuser | public | protected read | harmless disposable create/read/delete |
| Same administrator, authoritative demotion, same valid token | public | no implied read role | stable REST denial; denied write leaves no object |
| Disabled/deleted/unknown identity or revoked/expired token | explicit public policy only | deny | deny |
| Unconfigured authkey query parameter, no/outsider bearer | public policy only | deny | no bypass |
| Role endpoint credential absent/incorrect/revoked | tokeninfo still independently validates | fresh trust denied; finite old-cache window measured | no new grant |
| Role response timeout/malformed/duplicate/trailing/truncated | tokeninfo unaffected | expire bounded cached privileges; deny and recover automatically | no new grant |

GeoNode owns group membership and is_superuser. Its dedicated nonstaff,
non-superuser service Profile has an unusable password, no group memberships and
exactly people.view_profile/auth.view_group direct permissions. A separate random
role-service ApiKey is never a tokeninfo client secret or user bearer token.
These read permission checks are an explicit new source opt-in, not an inherited
least-privilege claim. Native GeoNode middleware may set configuration cookies;
GeoServer bearer responses may not create cookies.

The active GeoServer REST role service and OAuth UGS path use the same service.
Local XML user records establish identity existence only; role registry has zero
grants. Canonical fixture-readers maps to ROLE_FIXTURE-READERS; admin is emitted
solely for active GeoNode superusers and maps ROLE_ADMIN to ROLE_ADMINISTRATOR.
Fixed resource rules are provisioned once through real GeoFence REST. They do not
implement full GeoNode object-sharing synchronization or the unified product policy.

REST membership cache expires 1000ms after write; authentication expires after 2s
absolute/idle lifetime. Hits do not renew absolute expiry. GeoFence decisions use
current accepted authorities in their keys, so role removal changes the key.
Healthy serial staleness may approach 3s; the test deadline is 7s including
transport/sampling margin, with 250ms sampling and three stable target responses. Role transport failures
have a separate 15s first-denial deadline: the inherited UGS plus OAuth role calculation makes
up to six serial calls at 1500ms each, plus 3s serial cache lifetime and 3s margin.
Three stable completed failure responses have a 35s confirmation deadline
(3 × 6 × 1.5s transport + 3s cache + 5s margin); no authorization may return
after the first target result. The retained integration-02 failed its original 7s fault deadline at 10.36s; this
is transport-call timing, not indefinite stale authorization. Healthy membership
and administrator propagation retain the original 7s deadline.
Measurements start at native committed-state acknowledgment using the host
monotonic clock. Endpoint readback, immutable configuration hashes and token
validity are checked separately. This is a measured single-process fixture,
not a proof of production maximum, general slow-trickle bound, browser sessions
or multi-node revocation.

Native ORM mutations are explicitly controlled setup/administration operations;
no HTTP administration workflow is claimed from them. No restart or manual cache
clear occurs during grant/removal/restoration/demotion sequences. One later
restart preserves the same databases/configuration after membership removal;
old XML grants must not resurrect access.

Transport receipt modes distinguish syntactically truncated JSON (`truncate`)
from an HTTP body shorter than its advertised length (`short-body`). Duplicate
field corruption repeats actual native payload data, never inventing identities
or roles. Trailing-content corruption appends invalid bytes after native JSON.
