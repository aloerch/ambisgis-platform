# Independent Phase B runner review

Reviewed 2026-09-20 by the Phase A/readback agent, separately from the runner integrator. This is an engineering review, not the required owner/security acceptance. Scope: `build-support/java/compatibility.py`, `native_reports.py`, retained runtime-repository staging, original Byte Buddy startup-agent integration, fail-closed receipts, and the bounded OAuth source/fixture candidate. The loopback broker has its own independent review.

## Finding resolved

The initial runner copied tooling into the output but launched the network wrappers from the mutable working checkout. A retained snapshot could therefore differ from the executed enforcement code. The integrator repaired both subprocess paths: the compilation wrapper is `output/tooling/postgis/offline_exec.py`, and the HTTP wrapper is `output/tooling/java/loopback_exec.py`. Finalization rehashes every retained tooling file, requires the imported loopback receipt verifier to match the retained wrapper, and requires the wrapper receipt's executed-runner hash to match it as well.

The independent follow-up added two meaningful orchestration regressions: change the retained wrapper after simulated Maven success, and return an otherwise accepted receipt naming a different executed wrapper. Both persist `status=failed` and `result_exit_code=1` despite Maven exit zero. Existing tests also assert the actual subprocess snapshot paths. Reviewed runner SHA-256: `ef6a3ed51fb9ad1440184d8269296ca0fd5d82158c824ef3028b458676d18e88`; loopback wrapper: `6f0757b16be7188f564ad070a4e17382d96a7b9ef1dac3ab34fbf897d18108fc`.

## Receipt and execution assessment

The first stage compiles/packages prerequisites with all Internet sockets denied; its successful exit and denial receipt are required before HTTP execution. The second stage uses Maven offline, the retained dependency inventory and the loopback wrapper. The wrapper's timeout leaves a 15-second cleanup margin before the outer timeout. Native failure, absent executed target cases, source/configuration drift, missing network proof, malformed XML, fixture finalization failure and database cleanup failure cannot produce a successful final receipt. Failed build stops before runtime. Existing result directories are refused.

Runtime-provider staging verifies retained bytes and refuses conflicting cache bytes and symlinked ancestors. Publisher checksum sidecars remain recorded but do not replace Maven's normalized cache sidecars. The original pinned Byte Buddy 1.15.11 agent is loaded at JVM startup from the retained repository; its exact artifact hash and installer manifest are checked. This preserves inline Mockito behavior without substituting a mock maker. It is not host toolchain or complete Java dependency/source closure.

`native_reports.py` reuses `audit.parse_xml`, including its encoding-aware DTD/entity guard. It also bounds input size, requires suite/case identities and integer counts, compares reported totals with actual case outcomes, and rejects unsupported suite outcomes, nested suites, retry/flake markers and contradictory outcomes. A real testcase failure cannot be disguised by zero suite counters. `audit.py` and `source_closure.py` remain byte-for-byte unchanged relative to integration `a9ec191658be027b40118fd35e145729202fe55d`.

## OAuth follow-up

The final OAuth helper reads exact original sources without symlink traversal, refuses existing overlays, and preflights each repair group's exact input, unique replacements and predicted output before writing. Diagnostic changes remove response-map, reflected-error and access-token values from the selected service's diagnostics. They do not independently alter authentication decisions.

The separate principal candidate requires the diagnostic repair, then rejects successful GeoNode validation responses whose `issued_to` value is missing, non-string, empty or blank. It preserves a valid principal string unchanged. The original positive mock gains the owned protocol's principal field and additional authenticated/name assertions while retaining its original client assertion. No original assertion was removed. The real HTTP fixture exercises the selected owned GeoNode `verify_token` protocol and selected Spring authorization classes; it does not establish deployed servlet/browser or canonical product-policy acceptance. Diagnostic capture uses memory-only appenders and verifies capture controls before creating sensitive fixture markers; marker contents are not assertion messages.

No further material issue was identified in this bounded review. The final native principal candidate was subsequently verified as recorded below. Owner security review remains required and is not granted by this agent review.

## Independent validation

- Initial runner review: 34 focused unit tests passed; preserved in `runner-independent-tests.txt` and `.json`.
- Follow-up after the identity repair: 37 focused unit tests passed (13 compatibility, 7 native-report, 9 HTTP-orchestration, 5 runtime-repository, 3 startup-agent). Source hashes were unchanged during validation. Command, exact hashes and retained log hash are in `runner-independent-followup-tests.json`; output is in the matching `.txt`.
- Final OAuth helper: 7 guard tests passed; command, helper/manifests hashes and output are retained in `runner-independent-oauth-followup-tests.json` and `.txt`.

These are runner/fixture integrity tests, not additional native Java test executions or product acceptance. Earlier XML/MapFish runs made before the orchestration identity fix require independent equality checks between their retained wrapper, receipt runner hash and the reviewed wrapper; publication must preserve their actual historical runner hashes.


## Final native evidence and MapFish overlay review

Independent readback reparsed every recorded native XML report with the guarded parser, verified report hashes and counts, checked every retained tooling hash against each run manifest, and structurally verified each completed loopback receipt. The executed wrapper hash equals both the run snapshot and the reviewed wrapper. Selected fixture source/output and retained native test/data hashes also match. These are readbacks of completed runs; no extra Java invocation is represented.

| Final retained run | Native cases | Exact result SHA-256 |
|---|---|---|
| `xml-http-04` | 302 total, 298 pass, four inherited skips, no failure/error | `bf4578d2407a88609df765ffcdd02f90ce153a1415d857722405bb1df9bc930c` |
| `mapfish-http-05` | 77 total, 71 pass, six inherited skips, no failure/error | `291f825004a061c505e1046d2222d773abb38586fca3d254d6279159d349089e` |
| `oauth-http-principal-01` | 688 total, 687 pass, one inherited SSL skip, no failure/error | `fe9f1091fcf0266dd10abed4a6f07c138b0163729461b753a434f0abd8ec2862` |

MapFish's final patch extends the same explicit loopback client-source address to the independent `PdfTestCase` and `LegendsBlockTest` Config instances. Each calls the original `super.getHttpClient(uri)` then sets the local source address; no native assertion, service implementation, expected response or skip is changed. Before/after source hashes cover all three Config helpers and `FakeHttpd`. The final patch SHA-256 is `f3da0b82d720efb178dd1db05078e14fb84ccb443db39cb450db12c98c003255`.

The added fixture telemetry records only fixed reviewed paths, status and owned port after response headers/body have been written and the response stream closed. Finalization requires responses during the ready lifecycle and requires both actual `/500` and `/notImage` responses. Thus an expected exception caused by denied wildcard prebinding cannot stand in for the intended negative HTTP response. The final native run records `/500` twice, `/notImage` four times, capabilities once, WMTS once and `/testServer` five times. All 16 bound fixture servers stop; 15 reached readiness (one retained native fixture is constructed and stopped without being started). Native assertions remain authoritative for response semantics.

The OAuth final candidate's 17 distinct HTTP scenarios all pass, including all four malformed-principal cases. The two fixed Spring authorization decisions allow authenticated fixture access and deny administrator access. All 17 transport checks and three diagnostic regressions pass. The native HTTP scenarios remain one JUnit method, not 17 test cases. The exact principal output hashes match the guarded repair manifest.

Every final runtime verifies 79 parent and 79 exec-child probes, zero received datagrams, stopped task processes and closed broker sockets. The historical XML run predates the orchestration snapshot-path repair; its retained wrapper and executed receipt hash independently match the reviewed wrapper, and its historical orchestration hash is preserved in the readback JSON.

`runner-independent-http-native-review.json` and `runner-independent-oauth-native-review.json` retain these checks. The initial OAuth review-parser attempt is also retained separately: its too-narrow regex omitted the two hyphenated accepted labels; the corrected fixed-label parser finds all 17 without changing native evidence.

The logging WAR predates the OAuth diagnostic/principal source repairs. The repaired OAuth modules were freshly built/tested separately, and the logging provider/dependency tuple is unchanged. No repaired aggregate WAR, deployed application, full authentication flow, canonical policy acceptance, release or security approval is claimed. No unresolved material engineering finding remains in the bounded runner/fixture changes reviewed here.
