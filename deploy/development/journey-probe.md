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

Direct engine requests run a fixed Python HTTP client inside only this
installation's gateway container. Credentials enter over standard input rather
than process arguments or environment variables. The client uses the fixed
private engine host and port; the host publishes no engine port. Evidence keeps
selected response facts/hashes, never response bodies, cookies or tokens.

This helper has **not yet run against the new persistent container profile**.
Its five oracle tests pass using explicitly synthetic feature/PNG inputs; they
are not GIS integration evidence. The helper always records
`full_installation_acceptance: false`. Clean CLI installation, retained-bundle
relocation, restart/reinitialization preservation, dependency failures, real
UID/cgroup/mount/SELinux behavior and IPv4/IPv6/egress isolation remain separate
mandatory installation gates. Container execution also requires the reviewed
runtime repair and input assembly; this helper does not authorize adoption.
