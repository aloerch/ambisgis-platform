# FND-02 Java HTTP/authentication Phase B handoff

This is a tested development candidate in `aloerch/ambisgis-platform`, branch
`fnd-02/java-http-auth-compatibility`, based on
`a9ec191658be027b40118fd35e145729202fe55d`. It does not complete FND-02 or accept a
GIS release. Exact publication identity will be recorded in the PR and publication
receipt after the final checks.

## Prerequisites and workspace

All four prerequisite PRs are owner-merged and verified in integration ancestry:
#54 `8393fc46b9b979b05faa416f5998e0159ecd1e33`,
#55 `bb3680802d7f7d5c500180ec12e66d32d81d0aa0`,
#57 `8bf1217c8c078c26558da4b3318feda07a9c4ce1`, and
#56 `a9ec191658be027b40118fd35e145729202fe55d`. The #56 merge has the exact reviewed
tree `c792696b68a235dc1d21260858b81fe6e4beb5f6`; no Phase A work remained.

The fresh worktree is
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-http`. Repository ID
1376927351, node `R_kgDOUhI-dw`, authenticated owner `aloerch` ID 15285626 and
remote `https://github.com/aloerch/ambisgis-platform.git` were verified before
writes. Existing worktrees, archives and the original plan's modified STATUS
were preserved. The live task was read and claimed in
[issue #3](https://github.com/aloerch/ambisgis-platform/issues/3#issuecomment-5752979174).
[Start receipt](../verification/java-http/start.json) and
[complete Project readback](../verification/java-http/project/README.md) retain
actual identities, pagination and the accepted human column-order change.

## What changed and actually ran

The [recipe](../../build-support/java/http-compatibility.md) and
[ADR 005](../adrs/005-controlled-java-http-and-auth-probes.md) describe the bounded
runner. Every native attempt gets fresh extracted sources and local Maven state.
Builds deny IPv4/IPv6 sockets. HTTP tests run offline with verified retained inputs
under an unprivileged Linux seccomp broker: actual parent and exec-child probes
verify allowed loopback TCP and rejected external/alternate egress before tests.
All 158 mandatory probes passed on the successful runtime evidence; UDP sentinels
received zero packets, broker descriptors closed and owned process groups stopped.
Host namespace creation was refused once; no host security setting was changed.
This is a trusted-test egress restriction, not filesystem/process isolation or
production hardening. Other existing loopback services remain reachable.

XML uses the inherited WireMock fixture with an explicit loopback listener.
MapFish retains its HTTP/WMS/WMTS bodies and assertions while fixture helpers use
ephemeral loopback ports, bounded readiness and an explicit client local address.
Mockito uses the exact retained Byte Buddy 1.15.11 startup agent, avoiding blocked
Unix-socket self-attachment without replacing any mock or assertion.

The broader XML run `xml-http-04` passed **298 of 302 cases**, with **four inherited
skips**, zero failures/errors. The old class-rule setup error concealed five
SchemaCache methods; all five now execute and pass. The
[case mapping](../verification/java-http/xml-native-case-mapping.json) binds the
historical reports/source and every current case by hash.

The final OAuth candidate `oauth-http-principal-01` passed **687 of 688 native
records**, with one inherited `AuthenticationFilterTest.testSSL` skip, no failures
or errors. The selected GeoNode module executed 11 tests: seven original tests,
three diagnostic checks and one HTTP test method containing 17 scenarios. All 17
HTTP scenarios passed; they are not counted as 17 additional JUnit tests. Valid
and role-injection responses both passed authenticated-access/administrator-denial
checks. The original positive mock gained the actual protocol's principal and
stronger assertions. The selected native baseline `oauth-native-01` passed
683 of 684 records with one skip before new fixture/regression tests.

MapFish `mapfish-http-05` passed **71 of 77 cases**, with **six inherited skips**,
zero failures/errors. Its completed responses include `/500` twice (HTTP 500),
`/notImage` four times (HTTP 200), capabilities and WMTS once each, and five WMS
fixture responses. All task-owned servers stopped. The
[MapFish case mapping](../verification/java-http/mapfish-native-case-mapping.json)
compares 84 historical report records / 77 unique identities against 77 current
records: all 17 historically errored identities now pass; seven repeated
setup/teardown records are not counted as additional cases. All original test
assertions and fixture response data remain unchanged.

The combined candidate WAR built **156 reactor modules** offline with tests
explicitly skipped; this is packaging evidence only. Its SHA-256 is
`bfc104892843c17c6c5b9aa8ab19609cb1f9e4fb8e971e6b3b845fe40f8288ac`.
The reviewed combined logging witness verified **368 packaged libraries** against
source-built or retained filename/hash identities, one SLF4J provider, and seven
actual owned logger/bridge emissions exactly once. The packaged graph selects
SLF4J 2.0.16 with Log4j 2.25.3; the prior isolated 2.0.17 witness was not assumed to
represent this graph. No logging-version replacement was needed. The WAR/logging
witness predates the OAuth Java repairs; the repaired modules were separately
compiled and native-tested. This is not a patched aggregate WAR or deployment.

The actual selected OAuth service uses GeoNode's opaque-token verification: POST
form token, Basic client credentials, `client_id`, `issued_to`, `expires_in`, and
HTTP 403 for invalid/expired tokens. It does not use JWT issuer/audience claims.
Selected Spring authorization classes exercise authenticated access and denied
administrator access. This does not exercise a deployed protected servlet/filter,
browser authorization-code/state flow or canonical product policy. The baseline
revealed sensitive DEBUG diagnostics and authenticated results with a missing
principal; separate guarded source candidates and native regressions are retained.
[Detailed logging/OAuth evidence](java-http-logging-oauth-evidence.md) records
protocol, exact coverage, repair scope and the required human security review.

## Preserved failures and interpretations

No unsuccessful run was overwritten or converted to a skip. Attempts 01 lacked
retained Surefire runtime providers in the fresh offline repository; 02 exposed
Maven's checksum-text normalization. Explicit hash-checked runtime staging fixed
these setup failures without network acquisition. XML03's 16 errors and six
MapFish03 errors came from blocked Mockito dynamic attachment. The startup agent
resolved that environment issue. Five MapFish03 HTTP failures came from Commons
HttpClient 3.1's wildcard local pre-bind; an independent real-client before/after
witness confirms explicit loopback binding. MapFish04 narrowed this to three
PDFUtils-specific helper failures, with all mock errors resolved. Its Legends
test also accepted an exception from socket denial before receiving the intended
HTTP response. Final helper-local loopback configuration and completed-response
telemetry remove that false confidence; the final PDF/Legends expectations pass
against real fixture responses.

The webapp's first three unsuccessful attempts exposed source-JAR attachment
phase, EMF ranges and missing exact Spring LDAP inputs. Hash-guarded packaging
repairs and separate retained acquisition preceded the successful fourth attempt.
OAuth03 did not reach its HTTP target because prerequisite mocks could not attach.
OAuth04 reached it: 688 records, 683 passed, four failures and one skip; three
failures were intentional diagnostic regressions and one HTTP method contained
14 scenarios, of which missing principal failed. Scenario counts are not added to
JUnit counts. The diagnostic-only `oauth-http-redaction-01` passed 686 of 688 native records,
with one skip and one failing HTTP method: all three diagnostic checks passed,
but absent/empty/blank/non-string principals remained accepted. The separate
principal candidate resolved all four malformed-principal scenarios. All runs
and exact outcomes are indexed separately.

All actual sources, logs, settings, inputs, native XML reports, outputs, network
proof and tool snapshots remain under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-http/`. The checked-in
[compact run index](../verification/java-http/run-index.json) hashes those retained receipts/files; it does not duplicate
large source trees or reinterpret old native evidence as newly executed.

## Source custody and remaining acceptance

The original Maven custody is unchanged. New custody is
`/home/revelberry/Projects/AmbisGIS/source-archives/java-http-auth/maven` with eight
explicit Spring LDAP 2.3.2.RELEASE binary/source/POM/checksum/signature acquisitions.
[Acquisition evidence](../verification/java-http/inputs/ldap-acquisition.json)
retains exact inputs and publisher material. The frozen custody snapshot records
30,971 files / 1,123,830,406 bytes, SHA-256
`1aceac6b1a24a4327b43754de9f88d12619057d6b498079f88dfe5b71f3fe18b`.
Temurin 17.0.20.1+1 / Maven 3.9.16 are the verified retained toolchain; Python
3.13.15 and jsonschema 4.26 in `/tmp/ambisgis-validation-venv` provide plan checks.

The 64-gap supplement remains **48 structurally accounted / 12 unresolved /
four partial**, with no reproducible-source acceptance. Relevant remaining gaps
include Commons Codec 1.2's source/binary mismatch, JAI ImageIO 1.1 source/native
rights, and WireMock standalone's shaded dependency/assembly correspondence. Its
own source classifier does not cover 8,876 relocated classes. The
[HTTP source observations](../verification/java-http/http-source-observations.json)
bind actual selected inputs and preserve rejected substitutions. Source retention
and notices are not legal clearance. No capability was removed to hide a gap.

Full Java tuple/source/host-toolchain closure, canonical source-fork baselines,
security/licenses/brand, deployed authorization, FND-07/FND-08, P1/P6 and releases
remain separate gates. Database/Jupyter native suites were not repeated here.
FND-02 stays In progress and GOV-02 stays Merged.

## Checks and resumption

Fresh package validation passed **176 tests** without failures/errors/skips and
all **four schema/example checks**. The final integrated Java tooling run passed **300 tests** without failures/errors/skips.
[Exact commands, directories and log hashes](../verification/java-http/checks.json)
and [independent network-proof verification](../verification/java-http/runtime-proof-verification.json)
retain the actual evidence. The earlier 297-test run remains history. Independent review records
are in [the scoped review directory](../verification/java-http/reviews/).

From this worktree use the [documented recipe](../../build-support/java/http-compatibility.md)
with a new output directory. Never reuse an output path or rerun the Project
importer. The next bounded FND-02 action is a configured GeoServer servlet/filter and
protected HTTP resource test using the repaired modules and a synthetic identity
store, followed by a patched aggregate packaging check. Preserve inherited skips
and source gaps; do not claim the fixture IDP as actual GeoNode server acceptance. The owner reviews this one development PR and its
security-sensitive changes; no merge, auto-merge, deployment or release is
performed by this session.
