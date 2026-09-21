# ADR 008 — Source-owned GeoNode membership at the GeoServer role service

Status: implemented bounded fixture; fresh human security review required before merge.
Task: FND-02, which remains In progress. This does not accept the unified policy model.

## Problem and authority

PR #60's real GeoNode group removal left protected GIS access intact because an
independent XML role grant remained authoritative. Its historical comparison and
failed/merged checkpoint evidence are preserved. The selected owned GeoServer
source already contains GeoServerRestRoleService in extension/authkey, but that
module was absent from the previous aggregate.

The new aggregate builds that module from the unchanged owned source tuple and
retains importer, oauth2-geonode, geofence-server, geofence-server-postgres,
printing and postgis. No URL-key authentication filter is configured. GeoNode
owns tested membership and active is_superuser assignments; authenticated role
HTTP supplies the active GeoServer role service. Fixed native GeoFence rules own
this fixture's resource-to-role mapping. XML user records provide identity
existence only and contain no group memberships or role grants. Automatic user
provisioning and complete GeoNode object-sharing synchronization are unaccepted.

## Narrow owned changes

GeoNode OAUTH2_ROLE_SERVICE_STRICT defaults false and requires the existing
strict tokeninfo repair during source preparation. In strict mode the three
resolved role callbacks require a separate ApiKey and a configured exact active
service Profile, nonstaff/nonsuperuser, with people.view_profile and
auth.view_group. The fixture gives it an unusable password and no groups.
These are new explicit permission checks, not a claim about inherited least
privilege: legacy endpoints accepted a global API key or superuser session, and
an empty legacy key could remove protection. The strict role key is independent
from confidential-client credentials and user bearer tokens.

Strict reads permit GET only, return no-store, bind exact active usernames and
remove email fallback. Lowercase ASCII canonical groups map injectively to
ROLE_ plus uppercase; reserved/prefixed aliases are excluded. The synthetic
admin group follows active is_superuser exclusively. Exact-callback middleware
exceptions bypass legacy Basic/session-expiry handling only for strict role
views; strict tokeninfo's application binding, active-user checks, token-free
response and millisecond lifetime contract remain intact. Other native
middleware may add configuration-only session metadata/cookies. This is
separate from the GeoServer bearer no-cookie requirement.

GeoServer's strictGeoNodeRoles defaults false. Its guarded repair validates
complete expected payloads, exact unique username binding, canonical names,
administrator mapping and encoded username path segments. Malformed or missing
membership yields no grants. The response cache is per service instance and
partitions credentials, removing cross-instance cache borrowing. Successful
hits do not extend expireAfterWrite. Expired failures cannot reuse old grants;
previous successful snapshots retain only their finite original lifetime.
Transport connection/pool/read limits are explicit, redirects do not forward
credentials, and selected diagnostics avoid response/credential reflection.
Source preparation verifies exact inputs and predicted outputs before writes;
permanent behavior is rebuilt into wheels/JARs, never patched in an installation.

## Propagation and failure boundary

The experimental role cache expires after one second; authentication has a
two-second absolute/idle lifetime. Authorities are recalculated through the
active role service when authentication expires. GeoFence uses
SecurityContextUserResolver and current accepted authorities in its cache key;
removing the reader role changes that key despite its longer rule-cache TTL.
The fixed rules are unchanged throughout the test.

Measurements use one unchanged valid bearer, native committed-state monotonic
acknowledgments, actual role endpoint readback and protected HTTP responses.
Grant/removal/restoration and administrator demotion do not restart services,
clear caches, edit XML or mirror grants. Token revocation, disable/deletion,
role credential failure, transport faults and a later persistent-state restart
are distinct cases. Native ORM state changes are accurately labelled controlled
administration, not an HTTP admin workflow. Native request/status correlation
covers sequential/concurrent identity reuse.

The fixture's declared deadline is an experimental acceptance criterion, not a
proven maximum or production SLA. Read timeout is an idle timeout and does not
prove a total bound under an adversarial slow stream. Browser sessions,
multi-node propagation, full policy consolidation and security/license/release
acceptance remain separate. See the [role matrix](../../build-support/geonode/role-matrix.md),
[Java contract](../../build-support/java/role-service-contract.md) and
[handoff](../docs/geonode-role-propagation-handoff.md) for executed results and exact artifacts.
