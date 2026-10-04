# PLT-01 developer installation implementation

This implements the first persistent, loopback-only installation slice under
chapter 07 sections 2–6 and 9, with chapter 11 source custody. At this source
checkpoint, configuration guards and Java compilation/parser tests have run.
**Actual container installation acceptance is pending** the reviewed runtime,
owned image assembly and the native journey below. No image or container is
included in these files. A successful unit suite is not an installed product.

The supported initial interface is documented in
[`installer/bundle-format.md`](../../installer/bundle-format.md). The reviewed
bundle must provide an `ambisgis` launcher using its retained Python interpreter.
For repository development, the equivalent module commands are:

```text
python3 -m installer init --directory /absolute/private/install --bundle /absolute/bundle/bundle.json --bundle-sha256 REVIEWED_SHA256
python3 -m installer up --directory /absolute/private/install
python3 -m installer status --directory /absolute/private/install
python3 -m installer doctor --directory /absolute/private/install
```

The root directory is owner-only. `product.json` is the configuration authority;
`secrets/product.json` contains generated credentials. Commands report the
credentials file path without printing credentials. Compose and role-specific
service JSON are derived. Repeating `init` preserves identity, credentials and
data. A conflicting bundle, principal or port fails without resetting state.
An interrupted initial write without a final product configuration fails closed;
automatic adoption, reset, upgrades and destructive recovery are not implemented.

Only the gateway is published, on `127.0.0.1`. The database superuser uses its
container-local Unix socket. Catalog migrations/enrollment and native GeoFence
schema initialization run in separate one-shot containers. Normal catalog and
transport roles own no tables and have no elevated PostgreSQL role flags.
Catalog serving does not run migrations. Data and credentials remain across
restarts; raw engine administrative endpoints are denied even inside the private
network. The runtime selects local image identities with no implicit pull/build.

The first useful journey uses `fixture:private_points`, two deliberately
synthetic unmanaged points with stable native feature IDs, a simple SLD and one
native catalog ResourceBase. It does not enter DB-01 managed branch tables.
GeoNode's owned native OAuth authorization-code/PKCE endpoints, ResourceBase,
guardian permissions and access tokens are authoritative. The two enrolled
users are ordinary active users, not infrastructure superusers. A separate
noninteractive native health identity can read only this diagnostic item.

The gateway exposes the bounded WFS/WMS requests already used by the accepted
foundation, native authentication endpoints, and a metadata title GET/PATCH at
`/api/v1/installation/sample`. The latter requires native read policy; mutation
also requires write scope and `change_resourcebase`. The Java engine gate
independently reauthorizes the same item, checks selected asset bytes and fails
closed on missing policy. It does not cache positive decisions. Unsupported
engine/admin/transaction routes fail closed. `/health/live` means the gateway
process responds; `/health/ready` requires native catalog/database health and
an authorized real map and feature query. Full image/geometry semantics are
checked independently during installation acceptance.

Native GeoNode catalog hooks run synchronously with `ASYNC_SIGNALS=False`.
Unused task result storage is disabled. This is not a durable job queue, a
publication saga or a complete portal. Those routes are unavailable here.
Organizational OIDC enrollment, TLS, notebooks, managed branch editing,
publication, backup/restore and upgrades remain their explicit full-MVP tasks.
This developer slice neither claims their completion nor changes their scope.

Before PLT-01 acceptance, retain evidence for all of these actual checks:

1. Build/load the reviewed owned images; verify archive SHA, local image ID,
   source manifests, runtime/helper/config closure and host prerequisites.
   Reject checkpoint/restore image inputs before runtime use. Test the selected
   rootless UID/GID/passwd mapping, read-only roots, writable private data/tmp,
   cgroups, internal DNS/network and absence of public DB/admin ports.
2. Initialize a fresh private installation and repeat initialization/startup.
   Use native authorization-code/PKCE grants to perform an owner map, query and
   metadata mutation, and deny an outsider and anonymous reads. Independently
   inspect the two coordinates/IDs and nonblank 512×512 PNG pixels.
3. Test direct engine bypass, forged internal headers, malformed/duplicate
   request parameters, duplicate Authorization, admin routes and writes. Revoke
   native permission/token and verify the next gateway and engine requests deny.
4. Restart actual services and confirm the same credentials, issuer key,
   identities, native permissions and changed metadata survive. Concurrent
   initialization must not duplicate or reset native state. Serving roles must
   fail migration/owner/transport-policy writes, and serving containers must
   have no migration secret mounts or files.
5. Stop a named installation dependency and show the gateway process remains
   live while useful readiness fails. Restore it and repeat the private journey.
   Inspect actual requests/logs for credential leakage and unexpected network
   resolution or image acquisition. Preserve failed attempts as evidence.

Configuration/adversarial tests use inert image/runtime inputs and explicit
mocks only to exercise rejection and lifecycle ordering; they make no container
or GIS acceptance claim. Java parser checks execute the actual compiled finite
request guard under socket denial. Parent-controlled runtime evidence and an
independent review must bind the final source checkpoint before integration.

First-party code follows the existing proposed GPL-3.0-or-later policy. Retained
dependencies keep their own notices, corresponding sources and restrictions.
Waitress 3.0.2 requires both its exact source LICENSE/COPYRIGHT and the complete
vendored wasyncore notice beside software and supporting documentation. No
product distribution, signing or organizational deployment approval is implied.


The owned native health-timer bundle declares optional
`runtime.path_profile: "owned-health-timer-ascii-v1"` in its immutable bundle
manifest. That capability requires clean absolute selected bundle and
installation paths containing only ASCII letters, digits, slash, dot, underscore
and hyphen. Root `/`, parent components, spaces, non-ASCII, colon, dollar,
percent, backslash and control bytes are unsupported. Existing `Path` lexical
normalization of equivalent raw spellings, such as repeated separators and
single-dot components, remains unchanged; validation applies to the resulting
selected paths. The pure validator itself requires a clean spelling. The
restriction prevents ambiguous loader PATH components and systemd interpolation;
it is checked before first-init directories, reinit writes, runtime directories,
command-lock creation or native calls. `doctor` reports the same specific path
error before inspecting services. No filesystem relocation or state rewrite is
performed, and existing credentials/data are preserved on rejection.

The shared pure `validate_runtime_paths(selected_bundle, install_root,
bundle_root=...)` receives the verified bundle and its explicit location. Bundle
load validates its own root; init and Runtime additionally validate the actual
installation root. Public runtime commands perform a read-only preflight before
the command lock, then repeat validation under the lock. The owned producer also
checks its computed physical bundle root in the shell launcher before loading
retained Python/libraries; that producer guard is maintained separately.

The field is optional: bundles without it retain their existing path behavior.
Unknown or non-string profile values are rejected, including null. Version1
and all other bundle/configuration contracts remain unchanged. Choose supported
paths before creating a new installation; this capability does not authorize an
automatic relocation or upgrade of existing state. Filesystem/inert tests of
these checks do not qualify an actual installation or replace native acceptance.
