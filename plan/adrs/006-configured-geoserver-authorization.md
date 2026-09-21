# ADR 006: configured GeoServer authorization and aggregate runtime

Status: engineering candidate; fresh human security review required before merge.
Task: FND-02, issue #3. Builds on owner-merged PR #58.

This slice tests the actual owned aggregate application's security manager,
servlet mapping, OAuth filter, configured XML identity/role services, GeoFence
policy and WFS/REST resources. The GeoNode opaque-token verification endpoint is
synthetic. This is inherited component enforcement evidence, not actual GeoNode
server/browser SSO acceptance or the permanent AmbisGIS policy authority.

The fixture creates an external disposable catalog and identities, with no
inherited production/bootstrap data or default credentials. Its two generated
Shapefiles contain one point each. Anonymous access to the public point remains
intentional. A separately provisioned reader gets the private point; an outsider
and malformed credentials must be denied. A distinct administrator creates and
removes temporary workspaces; forbidden requests are followed by authorized state
checks. No managed AmbisGIS branch tables are involved.

GeoFence remains in the aggregate. Its native H2 default failed geometry-table
initialization in the first real startup. The selected PostgreSQL profile instead
uses the previously built, hash-verified owned PostgreSQL 15.19/PostGIS 3.5.7 in a
fresh task-owned database. A real supervised attempt proved that PostgreSQL's
mandatory backend setsid is incompatible with the retained supervisor. The
supervisor is unchanged. The database runs outside it with SCRAM authentication,
127.0.0.1 TCP only and no Unix listener; the application and identity HTTP fixture
remain supervised with actual parent/exec-child network proof. This is an explicit
additional environment limitation, not complete process/filesystem/egress isolation.

The real WFS deny path initially produced errors under GeoFence HIDE semantics.
The fixture now uses native MIXED catalog mode with an EXCLUDE filter for the
fallback private-layer rule. Native GeoFence converts this to denied read access
and the actual security chain emits a challenge. The earlier explicit reader
allow remains. No proxy rewrites responses or manufactures authorization results.

The baseline full matrix exposed two service-fixture policy failures: the inherited
session-scoped OAuth template creates a session despite a non-creating outer
context filter; that cookie causes a later outsider bearer to be ignored. An
explicit opt-in stateless bearer mode is implemented for the owned OAuth
configuration. Its default remains the inherited browser behavior. The opt-in path
uses the actual token services and configured roles, isolates request context,
avoids session-template access, and restores prior context on all exit paths.
A real Spring persistence-wrapper regression exposed early response commits
saving or removing that context before `finally`. A native `@Transient` request
context prevents both persistence paths; tests inspect the browser session during
`sendError` and `flushBuffer`, before restoration. The opt-in UserGroupService path
requires an enabled provisioned user, including for the reserved `root` name. The
configured HTTP regression matrix remains authoritative; a source/unit patch alone
is insufficient acceptance.

Cache and OAuth diagnostics also exposed fixture credentials under DEBUG. Guarded
source repairs remove cache keys, cookies and reflected identity/exception data
from diagnostic messages while retaining useful static categories. Native failing
and repaired positive-capture tests and real HTTP DEBUG capture are separate
witnesses. Fresh verification and actual nonzero-cache behavior are tested
separately. An allowed cached decision is not immediate revocation.

The ten retained runtime artifacts (Jetty 10.0.25, Servlet 4 API and SLF4J API) already have retained binary,
source, POM and notice records. A small project-owned launcher consumes the exact
WAR and an external data directory. A first origin guard caught Jetty reusing
Maven's adjacent exploded directory; the launcher now stages a byte-identical WAR
in a new runtime directory and verifies actual loaded application JAR bytes against
original WAR entries. Runtime presence/startup does not establish full printing,
GeoFence policy, rendering, publishing or release acceptance.

Every attempt retains independent packaging, native-test, network, HTTP, integrity
and cleanup evidence. Packaging with tests skipped stays packaging evidence.
Missing logger controls, failed scenarios, secret leaks, changed bytes or cleanup
failures must prevent success. A fresh final aggregate follows configured tests,
then repeats the core matrix and restart on that exact artifact.

The 64 source dispositions remain 48 structurally accounted, 12 unresolved and four
partial unless separately changed by actual evidence. Shaded-source, schema-rights,
source/binary correspondence and host/toolchain gaps remain. FND-02 stays In progress;
FND-07/FND-08, P1/P6 and security/license/brand/signing/deployment gates remain separate.
