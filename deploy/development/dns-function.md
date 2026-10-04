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
container, resolver or native engine. A separately reviewed bundle and actual
ordinary lifecycle run are still required for functional evidence. Single-query
success would not establish the full port, nonloopback, IPv6, egress, OS,
concurrency, log or cleanup matrix, security qualification or PLT01/MVP
acceptance. The existing held targeted engine probe remains untouched.
