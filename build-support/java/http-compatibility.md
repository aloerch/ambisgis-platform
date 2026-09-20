# Controlled Java HTTP compatibility probes

This is an FND-02 development recipe, not a product deployment or release gate.
Start from the merged Phase A tree and use a fresh output directory for every
attempt. Original archives and unsuccessful attempts are never overwritten.

The XML and MapFish suites already contain deterministic HTTP/WMS/WMTS fixtures
and response data. `http_fixtures.py` verifies their exact source/resource hashes,
then changes only disposable fixture copies: XML WireMock binds 127.0.0.1;
MapFish's embedded server uses an ephemeral loopback port, bounded HTTP readiness
and lifecycle evidence. Original MapFish assertions and response data stay unchanged. Test-only Config
helpers set Commons HttpClient 3.1 to a loopback local address: its default
wildcard pre-bind is correctly rejected by the broker. A retained JVM hosts file supplies localhost and the original negative
hostname check using a reserved nonlocal address; it does not permit external DNS.

`--runtime-http` first runs the selected package lifecycle with tests skipped
under the existing all-Internet-socket denial filter. Then it explicitly stages
verified retained runtime providers into the fresh local Maven repository. Maven
normalizes checksum cache files, so original publisher checksum/signature sidecars
remain custody evidence, not copied runtime artifacts. JAR/POM conflicts fail
closed. The second lifecycle invocation uses Maven offline mode, the same sources
and inputs, and the retained `loopback_exec.py` copy. Execution uses retained
network wrapper snapshots, with final hash verification. Some lifecycle goals repeat; no network
acquisition is permitted in either stage. Acquisition is a separate retained step.

The loopback supervisor creates each TCP socket already bound to device `lo`,
then injects it through seccomp notification. It copies and validates addresses
before performing loopback bind/connect itself; it never resumes a pointer-based
network syscall after checking mutable child memory. IPv4, IPv6 and mapped IPv6
are checked. Alternative transport, descriptor-import and network syscall paths
are restricted. Mandatory real parent and exec-child probes precede the command;
missing/changed evidence or failed process/socket cleanup prevents success.
The 79 parent and 79 exec-child probes verify the exact ioctl-only datagram
policy, including zero packets at task-owned UDP sentinels. It does not grant UDP
network traffic. Original Mockito instrumentation is loaded from the verified
retained Byte Buddy 1.15.11 startup agent to avoid Unix-socket self-attachment.

This restriction is for inspected, trusted fixtures. Host filesystem/process
access and existing loopback services are not a hostile-code sandbox. Use only
disposable credentials and the task's synthetic fixtures. No host firewall,
privileged service, global security setting or public listener is configured.
Namespace creation was inspected once and refused; Landlock port rules alone
were not adopted as destination isolation. The implementation follows local Linux
UAPI headers and the [kernel seccomp API](https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html).

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
python3 build-support/java/compatibility.py \
  --audit-custody "$TASK_ROOT/source-archives/java-audit" \
  --custody "$TASK_ROOT/source-archives/java-http-auth/maven" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --tools "$TASK_ROOT/build-worktrees/java-resolution/toolchain" \
  --output "$TASK_ROOT/build-worktrees/java-http/new-xml-run" \
  --target xml --stage package --tests target --runtime-http --timeout 600
```

For MapFish use `--target mapfish --repair xmlcodegen-emf` and a different output.
For actual GeoNode OAuth token-service tests use `--target oauth`; the optional
`--oauth-redaction` applies the exact diagnostic-only candidate repair, preserving
authentication behavior. Adding `--oauth-principal` also applies the separately
guarded nonblank String principal check; it requires `--oauth-redaction` and
human security review before acceptance. The fixtures use the selected opaque-token verification
protocol, not assumptions about JWT claims. Baseline and repaired runs are separate.

For the combined packaged candidate use `--target webapp --stage package --tests
compile-only --repair xmlcodegen-emf` without HTTP mode. Exact disposable POM
repairs in `combined_logging-repairs.json` attach the owned GeoFence model sources
in the package phase and constrain its EMF ranges to retained 2.15.0 inputs.
`combined_logging_probe.py --help` describes the separate full-WAR classpath test.
It verifies library origins, binding selection and native logger/bridge emissions;
it does not launch the inherited application or bootstrap data.

`native_case_evidence.py` maps the original XML class-rule error to its five
source-verified methods and all 17 historical MapFish error identities to current
outcomes. Repeated setup/teardown reports stay distinct from unique cases. Missing
cases, new skips, native errors, malformed counters and retry/flake records cannot
be counted as passing. Receipt parsing is also strict for the other native suites.

```sh
python3 -m unittest discover -s build-support/java -p 'test_*.py' -v
cd plan
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

Use the verified schema-validation environment. These tooling/package checks are
separate from actual Java, database, notebook, browser or release acceptance.
See the [Phase B handoff](../../plan/docs/java-http-auth-handoff.md) for actual
runs, retained failures, current source gaps and bounded resume actions.
