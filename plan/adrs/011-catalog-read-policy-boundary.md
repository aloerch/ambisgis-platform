# ADR 011: one catalog read-policy authority at both request boundaries

Status: implemented spike; fresh real runtime passed; independent review pending.
Task: FND-03 / R08 / R18, platform issue #4. Standing delegation governs routine
security engineering and review; acceptance criteria remain unchanged.

GeoNode ResourceBase and guardian grants are the authoritative object-sharing
model. Its native Profile/groups and OAuth access-token records determine the
current identity. A read-only internal decision endpoint checks these records
on every request without copying grants or caching successful decisions. It
binds each token to the configured native application, read scope, active user
and future expiry. Invalid credentials never fall back to anonymous access.

The owned gateway checks that endpoint before forwarding a supported request.
A first-party Java servlet filter independently checks it at the direct engine
listener, before the inherited engine dispatch. Both reject unsupported paths,
methods, duplicate keys and parameters. No caller-supplied resource assertion or
forwarded identity header can replace the parsed request target. The endpoint
itself requires a distinct internal service credential and returns only 204,
denial or unavailable, never a token, permission list or metadata payload.

The spike admits only WFS 1.0.0 GetFeature JSON with one canonical resource name.
GeoServer renders actual synthetic shapefiles from the exact accepted owned WAR.
An internal principal-free transport permission permits rendering behind the
mandatory filter. Inherited role grants and the login filter are removed from
the serving configuration, and all raw administration routes are denied even
with a valid administrator bearer. Controlled boot provisioning ends before the
product request listeners are opened. There is no asynchronous ACL copy or
second mutable object policy authority on the serving path.

Revocation is enforced on the first new request after the native catalog
transaction commits. Gateway and engine make independent fresh checks; a revoke
between them is denied at the latter. Requests already authorized may finish.
Catalog failure denies public and private reads; it cannot reuse old grants.
Response cache control is no-store. Wider caches, distributed policy epochs and
additional output types will require their own tests before activation.

The owned source/build inputs remain authoritative. This is a consolidated
product module alongside source-owned GeoNode and GeoServer, not a remotely
maintained authorization plugin. The Java filter is compiled from committed
first-party source against retained servlet inputs; installed GeoNode and WAR
bytes are verified unchanged. No source fork, dependency or accepted candidate
identity changes in this increment. Fixture controls are separate from serving
code and use synthetic local databases only.

Limits: this does not deliver OIDC deployment configuration, general browser
SSO, a sharing UI, installation, all T-AUTH-ALL surfaces, or a product release.
The gateway and policy endpoint use loopback HTTP in a supervised development
environment. An installer must enforce private listeners and service credential
custody; TLS/private service transport is deployment work. Native catalog
middleware and migrations stay active. The actual test matrix and results are
linked from the [FND-03 handoff](../docs/fnd-03-catalog-policy.md); package checks
alone do not accept this ADR.
