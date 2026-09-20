# ADR 005: controlled Java HTTP and authentication probes

- Status: implemented development candidate; human security/source/license acceptance pending
- Task: FND-02, issue #3
- Supersedes: no prior source or acceptance decision
- Builds on: ADR 004 and owner-merged PRs #54/#55/#57/#56

The all-Internet-socket-denied compatibility runner prevented the inherited XML
schema-cache and MapFish HTTP/WMS/WMTS fixtures from running. Unprivileged
namespace creation is refused in this environment. Offline Maven and local
listeners alone do not establish external-egress isolation.

The candidate separates the existing network-denied package build from an
offline native-test invocation under a Linux seccomp notification supervisor.
The supervisor creates TCP descriptors with SO_BINDTODEVICE=lo and performs
copied, validated loopback bind/connect operations on the notifying thread's
actual descriptor. It never continues an inspected pointer-based syscall.
Alternative transport/import paths are restricted; ioctl-only datagram sockets
support Java interface discovery while transmission remains disabled. Before
launch, 79 actual parent probes and 79 exec-child probes must pass. UDP sentinels,
receipt hashes and task-owned process/socket cleanup are checked at completion.
Failure in source verification, tests, network proof or evidence finalization
cannot produce a successful final compatibility receipt.

This is an egress restriction for trusted inspected tests. It deliberately does
not claim hostile-code isolation: host files/processes and other local services
remain accessible. It is not a production security boundary. Kernel behavior,
PIDFD_THREAD and pidfd_getfd support must be revalidated on another host. No host
firewall, privileged service, security policy or persistent account is changed.

Original fixture response data and test assertions remain authoritative. Exact
hash-guarded patches adapt disposable copies to explicit loopback endpoints,
ephemeral ports, readiness and lifecycle evidence. The legacy MapFish HTTP client
also needs an explicit loopback local address because its default is a wildcard
pre-bind; that environmental failure is reproduced independently. Mockito uses
its retained Byte Buddy startup agent to avoid Unix-socket self-attachment, with
no mock or assertion substitution. Maven runtime artifacts are explicitly
hash-checked and staged from retained custody; checksum sidecars remain original
custody evidence because Maven normalizes its cached checksum text.

The combined logging witness inspects every packaged WAR library's filename and
hash, verifies the actual selected provider and exercises owned module logger
fields plus bridges. Packaging repairs attach GeoFence model sources during
package and constrain its EMF dependency ranges to retained 2.15.0 inputs. These
are development recipe changes, not canonical source-fork baselines.

OAuth tests exercise the actual selected GeoNode opaque-token service with a
deterministic HTTP identity fixture and the selected Spring authorization
classes. Diagnostic redaction and malformed-principal rejection are separately
guarded source candidates justified by native failing evidence. Security review
is required before accepting these authentication changes. This does not accept
a deployed servlet filter, browser authorization-code/state behavior, canonical
AmbisGIS policy, full SSO or production resource protection.

The 64-artifact source supplement remains 48 structurally accounted, 12
unresolved and four partial. Additional retained inputs and shaded-library
observations do not establish complete or reproducible sources. Required GIS
capabilities, source custody, native API contracts and all release gates remain.

Actual results, preserved failures, exact artifacts, limitations and resumption
commands are in the [Phase B handoff](../docs/java-http-auth-handoff.md).
