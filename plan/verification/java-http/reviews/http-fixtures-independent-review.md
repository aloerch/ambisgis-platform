# Independent controlled runtime review

Reviewed `build-support/java/loopback_exec.py` SHA256
`9ab362782f445bcce961b2a799120c57e434b028354c883cfddc4882540b56b4`
and its 14 focused tests after the primary reviewer completed the implementation.
This was an independent source review; it did not rerun Java/native suites or
repeat the primary reviewer's real wrapper tests.

No additional material defect was found in the bounded trusted-fixture use.
This finding is not human security approval or a production sandbox assessment.

- Internet socket creation is brokered for IPv4/IPv6 TCP only. The parent binds
  each socket to `lo` before injecting its descriptor; child attempts to remove
  or change either device binding option are denied. UDP/raw/other families and
  externally addressable Unix socket creation are refused. Anonymous Unix stream
  socket pairs remain available for process IPC.
- The parent copies each complete bind/connect sockaddr, checks loopback identity,
  and performs that operation itself. IPv4-mapped IPv6 uses its effective IPv4
  address for this check. Wildcard and mapped-wildcard addresses fail it. No
  pointed-to bind/connect arguments are resumed with seccomp CONTINUE.
- Alternate implicit TCP connection attempts with MSG_FASTOPEN are denied for
  sendto, sendmsg and sendmmsg. io_uring, socket import with pidfd_getfd, tracing,
  namespace creation and changes, and installing replacement filters are denied.
  Normal connected stream sends remain allowed.
- Scalar close notification releases the broker's extra description when the
  task no longer references it; sweeps also account for process exit, exec and
  descriptor replacement. The positive probes cover EOF after the final close,
  duplicate descriptors, listener port reuse, and fork inheritance. Accepted
  sockets inherit their already-established loopback connection.
- The command gets a new process group. Group/session escape is denied, and the
  parent uses subreaper status, kills only the owned group, reaps descendants and
  verifies disappearance. Timeout, termination, missing probe evidence and
  cleanup errors produce failed receipts even after command exit zero.
- Receipt verification requires exact completion/exit agreement, successful group
  and broker cleanup, and the hashed complete set of 42 parent plus 42 exec-child
  probe identities. Missing/duplicate/false probe entries cannot be success.

The original Surefire attribute-trust finding was separately corrected with
`native_reports.parse_report`: every count must be present and agree with actual
case records, identities must exist, and contradictory/flaky/retry outcomes are
rejected. The HTTP orchestration mock now contains actual case records.

The wrapper explicitly permits access to existing loopback services and does not
provide hostile-code/filesystem/process isolation. Trusted retained fixtures,
disposable credentials, offline Maven inputs, and the separately network-denied
compilation remain necessary. UDP-based interface discovery is still refused;
any affected native LocalHostMatcher failure must remain visible instead of
weakening enforcement or removing its assertion.

## Final wrapper revision reviewed independently

The implementation above was superseded before the final native probes. A second
independent source review covers SHA256
`6f0757b16be7188f564ad070a4e17382d96a7b9ef1dac3ab34fbf897d18108fc`.
The first review is retained as historical evidence and does not certify this
new implementation by implication.

The final version closes the supervisor's original socket immediately after
atomic injection. Each bind/connect/setsockopt operation duplicates the actual
notifying thread's descriptor using PIDFD_THREAD plus pidfd_getfd, checks its
socket type/device, copies user memory, validates the notification identity,
performs the operation, and closes the duplicate. It uses no CONTINUE action and
no retained socket map, removing the descriptor-lifetime emulation reviewed above.
Accepted TCP sockets and worker-thread options have explicit positive coverage.
Device changes remain denied and destination checks still reject nonloopback,
wildcard and mapped-nonloopback addresses. Group/timeout/failure cleanup remains.

The final wrapper permits IPv4/IPv6 datagram *descriptors* for interface ioctls,
shutting down both directions before injection. Their bind, connect and every
setsockopt operation (including multicast membership) are denied by socket-type
checks. Required probes exercise sendto/sendmsg/sendmmsg, send/write/writev before
and after denied endpoint changes, plus fork inheritance. Separate supervisor
IPv4/IPv6 UDP receivers must observe zero packets. This is a narrower change than
allowing UDP transport; failed shutdown enforcement or packet reception prevents
a successful receipt. Platform behavior is demonstrated on this host and is
required again on every invocation.

No additional material defect was identified in this final bounded design.
Read-only verification of the retained JDK witness confirmed the final runner
hash, 79 parent plus 79 exec-child probes, zero UDP packets, complete group/socket
cleanup, and `interfaces=2 loopbacks=1 addresses=4`. The JDK receipt SHA256 is
`7212236505290dd63ba9e15bb93496db8d2cf34ddeafc523bc0c8201aba84dd2`, under
`source-archives/java-http-auth/ioctl-datagram-investigation/final-runner`.
The primary reviewer ran 15 focused real-wrapper tests. This independent review
did not rerun those tests or Java; it checked their final source and the actual
retained JDK/probe evidence. Hostile-code, existing-loopback-service and human
security-approval limitations continue to apply.

## Client binding and expected-error fixture review

MapFish HTTP attempt 04 reached 77 case records: 68 passed, six retained skips,
and three PDFUtils assertion failures. The three failures expected the exact
non-image or HTTP-500 messages but received `Operation not permitted`.
The retained PDFUtils report SHA256 is
`a08376d53af9821c2547d3274aec6019785f98c05bbac6d711dad8a28594bbea`.
The same attempt's LegendsBlockTest passed its broader placeholder/error
assertions while logging socket denial instead of the intended `/notImage`
response; its report SHA256 is
`9fb05617229ea2e5bd07f958ca294b4e56833a93a76675852a4fd0a332dcde32`.
That pass alone was insufficient fixture evidence.

The retained commons-httpclient 3.1 source and separately isolated before/after
witness show its default null local address becomes a wildcard pre-bind before
connect. The runtime correctly denies that bind. MapTestBasic had already set
an explicit loopback local address, but PdfTestCase and LegendsBlockTest create
separate Config instances. The reviewed fixture overlay now applies the same
test-only Config.getHttpClient override to those two helpers: obtain the
unchanged production client from super, set its local address to loopback, and
return it. The owned production implementation, every test assertion, response
body/status, and retained skip remain unchanged. These three helper files are
adapted sources, not byte-identical retained files. Each original and modified
file is hash guarded; 56 other retained MapFish source/data files remain exact.

FakeHttpd additionally records a completed-response event only after the response
headers/body have been written and the stream closed. The event includes the
owned ephemeral port, one of five fixed reviewed paths, and its numeric status;
query strings, headers and payloads are excluded. Finalization validates the
schema, status/path pair and active ready-server lifecycle, and requires actual
`/notImage` 200 and `/500` 500 response events. This supplements the original
client assertions; it does not claim a client consumed a body merely because
the server wrote it. Unrelated expected JDK initialization denials are not a
blanket failure condition. Native PDF/Legends report review must confirm their
intended fixture paths and errors rather than relying on a global denial count.

The complete four-file overlay applies to fresh retained originals and verifies
all resulting hashes. Its patch SHA256 is
`f3da0b82d720efb178dd1db05078e14fb84ccb443db39cb450db12c98c003255`.
All 18 fixture-tooling tests pass, including missing HTTP response evidence,
unreviewed path/status/content fields, response lifecycle ordering, and source
input/output drift. These are tooling checks; native attempt 05 is still required
for the new Java helper/response adaptation and case-level closure.

## Final native case and response evidence

MapFish attempt 05 completes with 77 native case records: 71 passed, six unchanged
inherited skips, no errors and no failures. The historical comparison in
`mapfish-native-case-mapping.json` is verified and preserves all 84 historical
records: 54 passed, six skipped, and 24 setup/teardown error records representing
17 unique failed identities. All 17 identities now pass once; the seven extra
historical duplicate records remain in the mapping rather than being erased.
No prior passing case disappeared and no new skip was introduced. Mapping SHA256:
`9d54fd0f184165ff3b28ec1e4131febf54824c6e794119ee266a54160506be47`.

Independent review of the actual PDFUtils and LegendsBlock reports finds zero
`Operation not permitted` occurrences in either report. PDFUtils retains its
exact non-image and HTTP-500 exception-message assertions, all six cases pass,
and its reported endpoint ports match one `/notImage` 200 and two `/500` 500
completed server responses. LegendsBlock's passing case now reaches the intended
non-image fixture: its reported endpoint port matches three `/notImage` 200
responses and its diagnostic reports the non-image error. This correlation is
retained in `mapfish-response-evidence.json`, SHA256
`5559214379d14534e7363c7d227b688aa3308ff3bf44ac6753b01c3e0f4d4ffc`.
The review does not require zero unrelated JDK startup denials.

The fixture receipt records all 16 owned servers stopped, of which 15 required
and completed HTTP readiness (one URI-construction fixture never starts). It
also records `/testServer` 200 five times, `/capabilities` 200 once, and
`/e2egeoserver/gwc/service/wmts` 200 once. Hosts remain unchanged. Receipt SHA256:
`a0018cf76427c34d79a5e02b293ab210bc10c209259bc6251a111d1f45e31f3c`;
raw fixed-field event SHA256:
`9ee470450f03ec3fc006c17f183b94f19ce5c82f6354c24e0661e80ce428399e`.

XML attempt 04 independently maps the historical class-rule initialization error
to all five actual SchemaCache test methods. Its 302 records contain 298 passes,
four inherited skips, and no failures/errors, versus the historical 298 records
with 293 passes, four skips and one class-rule error hiding those five methods.
`xml-native-case-mapping.json` verifies source hashes and every prior case;
SHA256 `b39e8fb5f1c5685756153afddd1462b110861660c0315bf766d01d4b86892722`.
These are native exploratory fixture results, not source/dependency closure,
product acceptance, or human security approval.
