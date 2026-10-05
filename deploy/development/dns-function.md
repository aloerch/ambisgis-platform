# Fixed service DNS wire evidence

The ordinary lifecycle driver checks one `database.` A/IN UDP exchange from the
owned gateway after the initial CLI has returned and after restart,
reinitialization and dependency recovery. Existing metadata and credential
persistence assertions precede the repeated checks and protected journeys.
This complements the separate daemon identity, namespace and cleanup observer.

`dns_function.py` first uses the installed Runtime's exact image/source,
container security, mount, namespace and network checks. It then binds fresh
native IDs, the one owned private IPv4 subnet, database address and service alias,
and the gateway's generated resolver file. That file must be regular, safely
owned, within the installation's run/storage roots, and the source of the exact
OCI `/etc/resolv.conf` bind. Its sole nameserver must equal the network gateway.
Explicit container DNS overrides are rejected. The same identities and resolver
bytes must still match after the exchange.

The generated file belongs to the container's mapped root, which can differ
from both the observer's user and the service's configured non-root user. The
host-side observer reads only the fresh inspected gateway PID's `stat`,
`uid_map`, `gid_map` and user-namespace identity through one retained proc
directory descriptor. It requires different gateway and observer user
namespaces: in that case the maps expose IDs relative to the opener, matching
file-stat ownership semantics ([Linux user_namespaces(7)](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)).
Same-namespace or unavailable evidence fails closed. There is no namespace
entry, range-based owner allowance, process-user shortcut or fixed host ID.

Each bounded map must be unambiguous and contain root ID zero. Both file UID
and GID must equal those exact mapped root IDs. The regular-file, no-follow,
contained single OCI bind and non-writable-by-group/others checks remain. The
open file and its current path must retain identical inode, ownership, mode,
size and timestamps after the bounded read. PID/start time, namespace identities
and maps are rechecked around the read; a fresh owned-container security check
also rejects changed CID, PID, start time or resolver/OCI paths. These finite
identities join the resolver hash in the pre/post wire-exchange comparison.
Safe existing modes such as 0400, 0600 and 0644 remain supported.

Lifecycle017 retained only the exception class at the failed function boundary.
A separate post-stop read reproduced the predecessor's observer-UID rejection
on the actual generated resolver, and retained Podman source establishes its
mapped-root chown contract. This demonstrates a validator defect, without
identifying the original unrecorded exception frame. Synthetic regressions
cover the defect, unavailable evidence, map/process drift and file replacement;
they do not demonstrate a live resolver exchange.

The bundle binds the complete `dns_wire_probe.py` source hash and carries its
bytes in the verified runtime closure. The wrapper permits only that exact
program, the installed gateway and the fixed Python interpreter, without stdin
forwarding or additional arguments. It adds no generic execution interface.
The client itself rejects arguments and stdin, reads only `/etc/resolv.conf`,
and sends a literal absolute `database.` A/IN question. It uses a fresh UDP socket
and transaction ID, a three-second timeout and one send/receive. It does not use
NSS, `/etc/hosts`, HTTP connection pools, external resolvers, retries or TCP
fallback. The outer engine call is bounded to fifteen seconds.

The response must come from that numeric resolver on port53 and contain exactly
the matching successful, untruncated question and one A/IN answer. Bounds cover
packet sizes, counts, label lengths, compression traversal and trailing bytes.
Aliases, extra records and unsupported protocol features fail this deliberately
small check. The expected answer comes from the independently inspected owned
database container, never from the DNS response itself. The private lifecycle
receipt includes query/response hex, resolver-file hash, program hash and selected
native identities. No credentials, arbitrary file content or exception text are
projected. Error output uses fixed classifications.

The new tests use literal packet fixtures, fake sockets and synthetic inspection
and filesystem data. They demonstrate parser and execution-boundary behavior,
not a real DNS exchange. This source increment has not executed a service,
container, resolver or native engine. This ownership repair changes only this host-side helper, its tests and this
document. It leaves `dns_wire_probe.py`, the ordinary command pin, lifecycle
driver, installer and shipped runtime/image inputs unchanged. Existing audited
bundle022/images025 can therefore be reused by exact hash, retaining their
original source identities; the new helper source identity is recorded
separately. A fresh ordinary lifecycle018 is still required for functional
evidence. Single-query
success would not establish the full port, nonloopback, IPv6, egress, OS,
concurrency, log or cleanup matrix, security qualification or PLT01/MVP
acceptance. The existing held targeted engine probe remains untouched.
