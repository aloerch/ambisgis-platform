# Selected Java application logging and OAuth evidence

The selected application candidate now packages from the retained source reactor,
and its **complete 368-library WAR classpath emits through the actual component
logger fields and every inspected logging bridge**. The separately repaired OAuth
source passes **687 native tests with one inherited skip**, including all
17 local HTTP scenarios and three diagnostic regressions. This is FND-02 exploratory
compatibility evidence. No application was deployed, inherited data directory
activated, or product/security/source-closure acceptance granted.

All run paths below are relative to
`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-http/`. Source archives
remain unchanged. Build copies, local repositories, recipe snapshots, output
artifacts and failed attempts remain retained separately.

## Aggregate source package and actual logging graph

`webapp-baseline-04/result.json` records a successful, Internet-socket-denied
`package` of **156 selected reactor modules**, with test execution deliberately
skipped. The selected profiles still include importer, OAuth GeoNode, GeoFence
server/PostgreSQL, printing and PostGIS. Its WAR is:

- Path: `work/source/geoserver/src/web/app/target/geoserver.war` within that run.
- SHA256: `bfc104892843c17c6c5b9aa8ab19609cb1f9e4fb8e971e6b3b845fe40f8288ac`.
- Selected libraries: **368**; their complete names, sizes and SHA256 values are
  in `combined-logging-final-03/classpath.json`, SHA256
  `a78768e62b04aede96c930346af9dd61e86500ca61b9061a05f891463bbd2788`.
- Final logging receipt SHA256:
  `80975f012e2be2b2ba6a8315c08763d0871d79d7d83a44d28ecd1c65d15d9977`.
- Actual logging output SHA256:
  `0e816f9eb1e6dc83f6bfbde41cd86a61241f341b2f3c59f4acb8aab4439ba88f`.

Each library's bytes match either the successful run's source-built artifact
inventory or its verified retained Maven input inventory. The runner extracts
only `WEB-INF/lib` libraries; inherited WAR configuration/data remains inert.
Required importer, printing/MapFish, GeoFence, OAuth and GeoServer artifacts must
all be present. Artifact filenames must match their recorded digests. Duplicate/unsafe archive
paths, unrecorded or renamed libraries, and any unaccounted `WEB-INF/classes`
files fail. The actual selected WAR has no `WEB-INF/classes` files.

The actual packaged logging tuple is **SLF4J API 2.0.16; Log4j API/core/SLF4J2
provider/JCL/JUL/1.2-API bridges 2.25.3; Commons Logging 1.3.5**. It has exactly
one SLF4J API definition, one SLF4J2 provider descriptor and no legacy 1.x binder.
The inspected Commons Logging, Log4j 1.x API and Log4j 2 API/core classes also have
one definition each. This observed tuple differs from the earlier isolated
SLF4J 2.0.17 witness; that isolated witness was not a product graph lock. No
additional logging version substitution was needed for this WAR.

`combined-logging-final-03/result.json` records successful compilation and
execution with IPv4/IPv6 sockets denied. Its seven markers each appear exactly
once, with actual loaded logger implementations and source JAR locations:

| Actual logger/API exercised | Observed backend |
|---|---|
| GeoServer `GeoServerExtensions.LOGGER` | GeoTools `Log4J2Logger` facade |
| GeoFence `DefaultUserResolver.LOGGER` | Log4j 2 core logger |
| MapFish `PDFUtils.LOGGER` | Log4j 2 core logger |
| OAuth `GeoServerOAuthRemoteTokenServices.LOGGER` | Log4j SLF4J logger |
| MapFish `Watchdog.LOGGER` | Log4j Commons Logging adapter |
| Plain JUL logger | Log4j JUL manager |
| Log4j 1.x API logger | Log4j 2 compatibility bridge |

The final witness retains its complete Python/Java/manifest recipes, executes
the copied offline wrapper, and verifies that retained tooling stayed unchanged.
The earlier successful baseline/reviewed logging runs remain preserved.

The witness explicitly selects GeoTools' Log4j 2 factory and the Log4j JUL
manager. It accesses actual component logger fields and emits synthetic
non-sensitive messages. It does not submit production service requests, start
GeoServer/Spring/GeoFence, or establish canonical authorization. Seven targeted
Python archive/classpath guard tests pass; those are tooling checks, separate
from the real packaged-classpath JVM execution.

The aggregate package exposed three concrete prerequisites, all preserved:

| Retained run | Result and disposition |
|---|---|
| `webapp-baseline-01` | Failed because GeoFence external-model generation requires internal-model source attachment before the parent's `verify` phase. |
| `webapp-baseline-02` | After source attachment was moved to `package`, failed on unmanaged transitive EMF ranges in GeoFence's own services parent. |
| `webapp-baseline-03` | After explicit EMF common/ecore 2.15.0 mediation matching retained GeoTools inputs, failed on missing exact Spring LDAP 2.3.2.RELEASE binary. |
| `webapp-baseline-04` | Passed using the guarded source changes and the separately retained LDAP binary/source/POM/sidecar supplement. |

`build-support/java/combined_logging-repairs.json` records exact before/after POM
hashes and bounded edits. No source revision changes or runtime Java source edits
occur in these two build repairs. The supplementary Maven custody is
`source-archives/java-http-auth/maven`; original Java compatibility custody stays
unchanged. Successful compilation does not settle source/binary correspondence,
license notices, security maintenance, or the complete product dependency lock.

## OAuth native tests and local HTTP fixture

`oauth-native-01/result.json` records **684 native tests: 683 passed, one skipped,
zero failures/errors**, with IPv4/IPv6 sockets denied. Seven tests execute in the
selected GeoNode module; the rest are executed prerequisite security tests.
`AuthenticationFilterTest.testSSL` is the one explicit inherited skip. Existing
GeoNode tests mock the HTTP transport and therefore do not establish actual
HTTP authentication behavior.

The added fixture uses the real selected `GeoNodeTokenServices` and its actual
`RestTemplate` over a task-local HTTP endpoint. Its protocol is grounded in the
retained owned GeoNode `geonode/api/views.py`: `verify_token` returns
`client_id`, `issued_to` and `expires_in`; invalid/expired tokens yield HTTP 403.
The local endpoint deliberately requires fixture Basic credentials to check
request construction and client denial behavior. No GeoNode Python server was
executed; its own credential enforcement and expiration implementation are not
tested here. The fixture does not assume JWT or RFC introspection `active`/`exp` semantics.
It checks form-body token transport, Basic client authentication and absence of
an access token in the URL. Seventeen scenarios include valid identity,
missing/empty token, wrong client ID/secret, invalid/expired responses,
unauthorized/server failures, malformed responses, missing client/principal,
empty/whitespace/non-string principal values, and attempted role injection. One
native JUnit method contains these scenarios; it must never be reported as
seventeen native JUnit test cases.

The actual selected Spring `AffirmativeBased`, `AuthenticatedVoter` and
`RoleVoter` additionally evaluate fixed fixture resource attributes using the
returned authentication: authenticated access and administrator denial are
separate checks. This is not a deployed GeoServer filter chain or the product's
canonical policy service. Browser login, authorization-code exchange, redirect
state, logout, role-service integration and actual protected GeoServer endpoints
remain acceptance work.

Three additional native tests exercise diagnostic handling with generated fixture
values held only in memory. A nonadditive memory appender first proves that the
actual logger reaches it, then tests redaction; exception diagnostics are checked
without printing their contents. `oauth-diagnostics-baseline-01` executes these
two tests against the unmodified selected source and records **two failures**.
No fixture token value appears in the retained report. Independent review added a third native regression for reflected endpoint-error
diagnostics, also captured entirely in memory. The diagnostic candidate in
`build-support/java/oauth-redaction.json` changes diagnostics only, with exact
source hashes; it changes no authentication decision. Final human security
review remains required.

Initial runtime attempts did not reach HTTP tests:

- `oauth-http-baseline-01`: source compilation passed; Maven offline runtime
  lacked the retained Surefire provider in its fresh cache.
- `oauth-http-baseline-02`: source compilation passed; strict runtime priming
  stopped on Maven-normalized checksum sidecars. No native HTTP cases executed.

- `oauth-http-baseline-03`: source compilation passed; 132 inherited security
  tests ran (94 passed, 13 failures, 25 errors), but Mockito self-attachment
  required a socket family deliberately denied by the fixture environment.
  The selected HTTP cases were not reached. A verified retained startup test
  agent subsequently supplied the same instrumentation without relaxing sockets.
- `oauth-http-baseline-04`: **688 native tests: 683 passed, four failures, one
  skip, zero errors**. The three diagnostic regressions fail against original
  source. The HTTP method executed all **14 scenarios: 13 passed, one failed**.
  A success-shaped response missing its principal returned an authenticated
  object. Missing/empty tokens, incorrect client credentials, invalid/expired
  responses and other malformed-response cases were denied. Both fixed Spring
  authorization checks passed for each accepted fixture identity, including the
  attempted role injection. All 14 requests satisfied the expected transport
  assertions. The loopback receipt independently verifies 79 parent +79 exec
  probes, zero datagram packets, and stopped task processes.

- `oauth-http-redaction-01`: **688 native tests: 686 passed, one failure, one
  skip, zero errors**. All three diagnostic regressions pass. The expanded HTTP
  method exercises **17 scenarios: 13 passed, four failed**: absent, empty,
  whitespace-only and non-string principal values still returned authenticated
  objects. Correct transport is observed for all 17 requests. This isolates the
  diagnostic repair from authentication behavior.

The separately guarded candidate in `build-support/java/oauth-principal.json`
requires `issued_to` to be a nonblank string; it preserves valid principal values
without normalization. The existing positive native mock gains the principal
that the actual owned GeoNode endpoint returns, plus principal/authenticated
assertions; its original client-ID assertion remains. The repair is a deliberate
authentication decision change, justified by the retained failing runtime
cases, and still requires human security review before acceptance or merge.
`oauth-http-principal-01/result.json` records the final fresh candidate:
**688 native tests: 687 passed, one inherited SSL skip, zero failures/errors**.
The selected GeoNode module executes 11 native tests: its seven original tests,
three diagnostic regressions and the HTTP method. All **17 HTTP scenarios pass**,
including the four previously accepted malformed-principal cases, and all
17 requests satisfy transport checks. The three diagnostic regressions and
both fixed Spring authorization checks pass. The result receipt SHA256 is
`fe9f1091fcf0266dd10abed4a6f07c138b0163729461b753a434f0abd8ec2862`.

The network-denied build passes first; controlled runtime verifies 79 parent
plus 79 exec probes, zero datagram packets, stopped task processes and closed
broker sockets. Executed tooling snapshots remain unchanged.
Seven targeted OAuth tooling tests
verify wrong-source refusal, symlink protection of retained originals, invalid
repair pairing, existing-fixture preservation, predicted-output and multi-input
preflight rejection, and actual fixture-scope receipts. They do not replace the
native tests.

All failures remain retained; none is waived, renamed a skip, or represented
as acceptance.

The logging WAR predates the OAuth diagnostic/principal source repairs. The
repaired OAuth modules were compiled and tested in a separate fresh reactor;
they were not silently substituted into that WAR. The provider/dependency tuple
is unaffected by these Java-source repairs, but a final reviewed aggregate
service build and configured end-to-end authentication remain separate gates.
Neither artifact establishes browser SSO, canonical policy, source/notice
closure, a release, or deployment acceptance.
