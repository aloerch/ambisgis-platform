# ADR 003 — Resolve a fixed Java extension candidate before compilation

Status: FND-02 engineering experiment; product baseline, license and runtime
approval remain pending. This extends ADR 002 without accepting its unresolved
printing or configuration choices.

The exact owned GeoTools 34.5 / GeoWebCache 1.28.5 / GeoServer 2.28.5 source
archives remain unchanged. A disposable aggregate Maven reactor also includes
retained MapFish 2.4.1 (`da1f37cfc0d7a235cb2c0ec5677010495d9f664b`) and
GeoFence 3.8.3 (`132a1d16901b7039f974c8c30d7e7df042d8af4c`). These Class B
sources are evaluation candidates, not approved additional product roots.

Resolution selects `org.geoserver.web:gs-web-app` and GeoFence's
`org.geoserver.geofence:geofence-persistence-pg-test` with Maven `-am`.
Profiles are `importer,oauth2-geonode,geofence-server,geofence-server-postgres,printing,postgis`.
Importer preserves GeoNode's import client path; both GeoFence profiles are
necessary for the server and PostgreSQL WAR dependencies. The `postgis` profile
includes the GeoFence PostgreSQL test module in input resolution. It does not
run those tests or prove database compatibility.

The printing candidate uses the explicit command-line override
`mf.version=2.4.1`, replacing the unresolved `2.4-SNAPSHOT` for this experiment
only. `gt.version=34.5` aligns MapFish's declared 34.4; the distinct
`gt-version=34.5` aligns GeoFence's declared 33.1. Successful resolution cannot
establish API, cartographic, security or license compatibility. Compilation and
real affected tests remain prerequisites for adoption. No retained source POM
is patched and no snapshot binary is accepted.

WPS stays outside this bounded graph, matching GeoNode's application default.
Its disagreement with the donor image recipe remains tracked; this experiment
does not remove product capabilities or adopt that image's profile. Other donor
recipe extensions, vector-tile/style/driver inputs and optional GWC storage
modules require explicit later capability/profile decisions. The target selector
avoids GeoTools' release/documentation packaging as a dependency shortcut.
GeoTools schema-packaging modules perform live Ant downloads and are not activated
implicitly. Every missing selected input remains a reported failure.

The GeoNode extension-recipe bootstrap/assets remain unadopted because their
license provenance is unresolved. OAuth/GeoFence configuration, authorization,
printing, importer and rendering need real integration tests before acceptance.
No inherited data directory, workflow or deployment script is executed.

Maven receives fresh task-local repositories, explicit empty global settings and
a single loopback mirror that retains acquisition bytes and provenance before
serving them. Moving snapshots and external core donor binaries are rejected.
Parent/BOM and dependency metadata may be retained separately from executable
artifacts; none is represented as a source-built owned binary. A replay may use
only retained proxy inputs. That is not itself OS-level network denial or a
no-upstream product rebuild. Toolchain checksums, original sources/notices,
transitive source gaps and host dependencies remain separately recorded.

Only pinned effective-model and dependency-acquisition plugin goals run here.
A Maven `BUILD SUCCESS` message for either goal means that goal succeeded, not
that Java compilation, native tests, runtime checks or a product build passed.
