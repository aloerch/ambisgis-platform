# FND-03 catalog identity and ACL spike

Declared for the new catalog boundary before successful runtime acceptance.
R08/R18, issue #4; FND-02 is accepted/Merged and its exact runtime inputs are reused.
This spike supports only WFS 1.0.0 GetFeature JSON for three synthetic layers.
Other service operations fail closed; wider T-AUTH-ALL remains future work.

| State | Gateway | Direct engine |
|---|---|---|
| Public item / anonymous, user A, user B | Real Point(1,2), PUBLIC_WITNESS | Same |
| Private item / owner A | Real Point(1,2), PRIVATE_WITNESS | Same |
| Private item / anonymous or B | Deny, no feature content | Same |
| Group item / member A or owner B | Real Point(1,2), GROUP_WITNESS | Same |
| Group item / anonymous | Deny | Same |
| Remove group membership, reuse A's bearer | First new request after native commit denied | Same |
| Restore group membership, reuse A's bearer | Allowed | Same |
| Share private item with B, then revoke | Allow then immediate committed revocation | Same |
| Revoke public grant, then restore | Anonymous denied then allowed | Same |
| Disable A, then enable | Denied then allowed with same bearer | Same |
| Delete A's native access tokens | First new request denied | Same |
| Thirty-two concurrent owner/revoked member requests | No identity mixing | Same |
| Catalog unavailable | Public and private fail closed | Same |
| Restart catalog | Persisted revocation remains denied, public works | Same |
| Inherited REST/web/cache admin / all users including admin | Denied | Same |
| Alternate endpoints, duplicate/extra parameters, write methods | Denied | Same |
| Invalid bearer on public item | Denied; no anonymous fallback | Same |

Identity comes from actual GeoNode HTTP login, CSRF, consent, PKCE S256 and token
exchange. Authorization reads the installed native OAuth token model, active
Profile, ResourceBase and guardian grants on every request. Sharing/membership
mutations use native ORM in committed disposable database transactions, not a
mock authority or an implemented product sharing UI.

The inherited engine starts separately for private controlled provisioning. A
real administrator can access it in that stage: that baseline deliberately fails
the new raw-admin criterion. It stops before the gateway starts. Final serving
has a mandatory servlet filter on all dispatches, no XML role grants, no active
inherited OAuth login filter, and one static principal-free internal transport
rule. That rule never changes as catalog sharing changes and cannot be edited
through the serving engine/gateway. Unsupported operations are denied.

Each response checks HTTP status, actual geometry and witness bytes, absence of
private content on denials, no response cookie, no-store and known secret values.
Readiness, source origins, selected WAR, compiler input/classes, network
restriction and clean teardown are independently recorded by the retained runner.
The new-request revocation claim applies after catalog commit; an already
authorized response cannot be recalled. There is no positive-decision cache.
