# Protected installation journey probe

`journey_probe.py` is a bounded acceptance component for an already running
developer installation. Execute it with the reviewed retained Python interpreter:

```sh
python deploy/development/journey_probe.py \
  --directory /absolute/path/to/private-installation \
  --output /absolute/path/to/new-private-evidence
```

It reads installation credentials in memory, performs the real native PKCE and
consent flow for both enrolled users, and requests the private unmanaged
diagnostic map, features and metadata. Feature IDs, attributes and coordinates
and the two rendered point positions/colors have independent expected values.
Anonymous and second-user reads, forged internal headers and duplicate query
parameters must fail. An authorized metadata title change remains persisted on
the diagnostic resource for subsequent restart/reinitialization checks. The
owner's access token is then revoked through the native endpoint, and its next
map/query request must fail through both gateway and direct engine paths.

The helper retains both returned token sets in memory. Its `finally` cleanup
revokes all refresh and access tokens created by this invocation, including
partial login and subsequent assertion failures. It attempts the remaining
revocations after an individual failure and requires complete cleanup for a
passing result. Installation principals and passwords remain intact. A lost or
malformed issuance response can leave an unknown grant; that condition fails
the journey and is explicitly recorded as incomplete cleanup. The receipt
contains only safe cleanup outcomes, and its secret scan includes browser
cookies, authorization values and tokens as well as installation secrets.

Direct engine requests run a fixed Python HTTP client inside only this
installation's gateway container. Credentials enter over standard input rather
than process arguments or environment variables. The client uses the fixed
private engine host and port; the host publishes no engine port. Evidence keeps
selected response facts/hashes, never response bodies, cookies or tokens.

This helper has **not yet run against the new persistent container profile**.
Its fifteen pure tests cover synthetic feature/PNG inputs and token cleanup on
success and failure; they are not GIS integration evidence. The helper always records
`full_installation_acceptance: false`. Clean CLI installation, retained-bundle
relocation, restart/reinitialization preservation, dependency failures, real
UID/cgroup/mount/SELinux behavior and IPv4/IPv6/egress isolation remain separate
mandatory installation gates. Container execution also requires the reviewed
runtime repair and input assembly; this helper does not authorize adoption.
