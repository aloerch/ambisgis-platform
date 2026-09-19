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

## Schema resource acquisition refinement

Actual resolution exposed nine `org.geotools.schemas` archives used by the
selected graph. Owned GeoTools documentation calls these independently released
schema-definition packages; the `gt-xml` test dependencies use them for offline
schema resolution. All nine retained artifact POMs have the same 73 resolved
Ant download source/destination pairs as their owned packaging recipes. Their
metadata/authorship/SCM serialization differs and none declares a license. Five
required XML basenames are absent from the owned source archive, so existing
fixtures cannot silently substitute for these inputs.

The third dependency pass exposed ten additional transitive archives. Their
104 source/destination pairs and dependency lists also match the unchanged owned
recipes, including two exact GML ReadMe text files. See the [additional comparison](../verification/java-additional-schema-recipes.json).
The combined evaluation set is 19 exact coordinates / 177 resources; no POM in
either set declares a license.

Retain only these 19 exact reviewed GAVs as **Class B XML/XSD source-resource
candidates**, subject to inspection of the actual ZIP bytes before serving them.
The narrowly scoped validator requires the exact declared resource paths, refuses
compiled/native/script/nested-archive payloads and unsafe or duplicate ZIP paths,
and retains member hashes, XML annotations, notices and matching Maven metadata.
This does not permit other donor-built core artifacts, other schema versions,
or an unvalidated namespace exception. Checksums alone are not the resource
content check. The resource archive itself contains the candidate XML/XSD source;
a Java `sources` classifier is not assumed to exist for these data packages.

Owned offline repackaging, schema resolver tests, upstream XML references and
file-level rights remain unresolved until actually exercised/reviewed. No Ant
network download, lifecycle build or schema runtime test is authorized by a
successful resource acquisition check.

### Exact XML namespace documentation instruction

The additional evaluation accepted nine archives and quarantined `xml-1.0:1.0.0-3`
because its W3C schema contains a documentation `xml-stylesheet` instruction.
Inspection of the original archive found one such instruction, no DTD/entities,
no schema imports/includes/redefines and no executable archive members. For
inert source-data retention only, allow this exact tuple:

- GAV: `org.geotools.schemas:xml-1.0:1.0.0-3`.
- Member: `org/w3/www/2001/xml.xsd`.
- Member SHA256: `61960fb3131e38022caad5360e2f33a3382578ab3c80cd58bd74320ede61b20c`.
- Instruction: `<?xml-stylesheet href="../2008/09/xsd.xsl" type="text/xsl"?>`.

The original JAR SHA256 is
`203543257c4fce6dd844c8606dd77fc2bddde647807d97feaab7bc224cc734a9`.
The validator records the instruction but never requests or executes its
stylesheet. Every other processing instruction, altered member/hash, DTD/entity
and executable payload remains refused. Preserve the initial quarantine and its
failure report. This narrow acquisition decision is not safe browser/XSLT/runtime
handling evidence, license clearance, or human security-gate approval. Later
schema consumers must be explicitly offline and resource-aware, with real tests.

The final retained-file dependency goal succeeded after adding the exact SLF4J
API 2.0.17 JAR/source bytes exposed by a failed network-denied run. Identical POMs
and the acquisition plugin's unordered dependency sets mean goal success must
not be represented as a resolved-version lock. [The diagnosis](../verification/java-resolution-slf4j-mediation.json)
records the observed competing versions and distinguishes evidence from the
mediation-order inference. Reconcile and test actual logging bindings before build
or runtime acceptance.
