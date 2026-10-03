# Development bundle interface, version 1

This is a local, reviewed Linux x86_64 development bundle interface. Schema
validation is supplemented by the semantic and filesystem checks in `bundle.py`.
An operator supplies the exact bundle manifest SHA256; the installer never
discovers or downloads a manifest, image, package or updated revision.

`bundle.schema.json` describes the entry document. Every `path` and `archive`
is relative to that document's directory. Paths must stay inside that directory
and cannot traverse symlinks. Image references use `localhost/ambisgis/NAME:TAG`
with immutable selected tags; `latest` is rejected. The archive SHA256, actual
loaded image ID, and common source-manifest SHA256 are separate identities.
The assembler must embed `org.ambisgis.source-manifest-sha256` and
`org.opencontainers.image.revision` labels matching the bundle selection.

Archives are uncompressed OCI image-layout tar files containing one Linux amd64
image. The index descriptor's `org.opencontainers.image.ref.name` annotation is
the complete local image reference. The guard validates the selected manifest,
config and every layer descriptor/digest, plus uncompressed rootfs diff IDs.
Layers may be uncompressed or gzip. There are no descriptor URLs, foreign
layers, artifact subjects, alternate platform manifests or hidden unused blobs.
Outer tar members may only be canonical regular files and the two optional
blob directories; links, special files, duplicates, sparse/PAX metadata and
nonzero trailing payloads are rejected. Limits are 1,024 members, 64 layers,
8 MiB per JSON document, and 64 GiB each for archive and expanded layer totals.
Checkpoint/restore metadata is forbidden, including empty or Unicode-escaped
keys. Loaded image inspection repeats this rejection and verifies both config
ID and manifest digest. Compose runs the verified immutable image ID with pull
disabled. No checkpoint/restore operation is part of this installer.

`runtime.files_manifest` references an exact JSON document containing
`schema_version: 1`, `roots: ["runtime", "python", "configuration"]`,
`files: [{path, sha256}]` and optionally `symlinks: [{path, target}]` and
`directories: ["runtime/required-empty-directory"]`. Select the actual assembler
layout; roots must be nonoverlapping contained directories. Every recursive
file and link under each root must be declared; directory membership is exactly
the parents implied by files/links plus explicitly declared directories. Extra
files (including startup modules, `.pth` files, helpers and libraries), links,
empty directories and special files cause pre-execution rejection. Root and
intermediate bundle directories require trusted ownership and cannot be group
or publicly writable. Symlinks must be relative and resolve to declared,
verified regular files within the bundle. Include runtime executables, helper
binaries, libraries, Python modules, policy/configuration files and required
runtime assets. Every wrapper-referenced executable/helper/configuration root
must be in this complete closure. Image archive content has its own image and
source inventories outside these execution roots.

`runtime.prerequisites` references the document described by
`host-prerequisites.schema.json`. Host helper hashes, owners, modes and exact
file-capability bytes are enforced. The kernel selection, subordinate ID ranges,
cgroup-v2 controllers and required FUSE access are checked before execution.
These observations do not substitute for actual mapping, cgroup, storage and
network tests. This initial bundle is qualified for its recorded kernel; it does
not claim compatibility with every Linux installation.

`runtime.environment` accepts only `PATH`, `LD_LIBRARY_PATH` and `PYTHONPATH`.
Values are lists of relative bundle directories within complete closure roots.
Python user-site and unsafe current-directory imports are disabled. The installer creates a clean
child environment, selects its Compose provider explicitly and supplies
installation-specific configuration/storage/runtime paths. Neither inherited
connection/provider variables nor host container hooks/registries are accepted.
The runtime wrapper must bind its retained configuration and every helper path;
it must accept the explicit local root/runroot/network/hooks/tmp paths passed by
the installer without adding a remote connection or implicit pull.

Each image supplies `/opt/ambisgis/bin/service ROLE` and
`/opt/ambisgis/bin/health ROLE`. Its read-only inputs are
`/run/ambisgis/product.json` and `/run/ambisgis/secrets.json`. The latter is scoped
to that role. Persistent application data is mounted at `/var/lib/ambisgis`;
catalog and renderer also receive `/var/lib/ambisgis-blobs` (renderer read-only).
Services run with the mapped host UID/GID, a read-only root and dropped
capabilities. Actual selected Compose support and writable-directory semantics
must pass native tests before this profile is accepted.
The initial network is explicitly IPv4-only (`enable_ipv6: false` plus container
IPv6-disable sysctls). The selected backend's actual configuration and IPv6
negative/egress tests are required; `internal: true` alone is not an isolation
proof. This guard/profile does not approve an affected container runtime.

`catalog-init` reuses the catalog image and `geoserver-init` reuses the engine
image. Both are one-shot services in the `bootstrap` profile. Only these roles
receive their respective migration credentials. Serving starts after the
database's native health probe and both initialization jobs complete. Catalog
initialization uses a PostgreSQL advisory lock; engine initialization uses the
installation volume's exclusive file lock. Repeated initialization validates
existing objects and retains passwords, metadata, permissions and identities.

The native GeoServer data directory is a private per-container projection under
`/tmp/ambisgis-engine/data`. It is regenerated from versioned code and product
configuration. It contains the container's own scoped datasource credential;
migration credentials never enter the shared engine volume. Persistent engine
assets and markers live under `/var/lib/ambisgis`. The native GeoFence transport
schema/rules live in the separate `ambisgis_transport` PostgreSQL database.
Serving uses a non-owner SELECT-only database role and validates the schema;
only the initialization job enables native schema creation/update. Two fixed
transport rules cover the diagnostic WMS map and WFS feature query. They are
not user permission records: the mandatory Java filter consults the native
catalog on each request, and native REST/admin routes are unreachable.
Database bootstrap refuses dangerous role attributes, any role membership
(including a route through `SET ROLE` or predefined roles), and serving-role
ownership of database objects. It rejects these existing states before schema
changes instead of silently revoking privileges. Real role/ownership, DML/DDL
and membership adversarial checks remain native installation acceptance gates.

Package `deploy/development/{service,health}` as the fixed image entrypoints,
with the retained interpreter at `/opt/ambisgis/python/bin/python3`. Install the
`ambisgis_development`, `ambisgis_policy` and `ambisgis_render` module roots into
that interpreter's controlled import path. Database binaries, extensions and
share files use `/opt/ambisgis/postgres`. Java uses `/opt/ambisgis/java/bin/java`.
The engine image contains `application.war`, `runtime-profile.json`, compiled
`launcher/` classes, retained `servlet/*.jar` and the three profile-selected
members under `/opt/ambisgis/geoserver/lib`. The profile binds the exact WAR and
Marlin/ImageIO/JSON bytes; paths must be relocated and actually tested. The
host-facing bundle launcher must similarly use a retained exact interpreter.

`product.json` inside the private installation directory is the sole mutable
product configuration. Generated Compose and service JSON are projections.
Reinitialization preserves installation identity, credentials and data. The
installer rejects incompatible bundle/enrollment changes instead of treating
them as an upgrade or resetting an existing installation.
Every named persistent bind directory and its storage root must remain private,
owned by the installing user and free of symlink ancestors. Reinitialization
and runtime construction revalidate these paths before rendering or executing
the engine; they do not follow replacement links or repair permissions silently.

First-party installer code follows the plan's GPL-3.0-or-later policy; this does
not relicense bundled dependencies. The complete product distribution, sources,
notices, signing and supported-profile gates remain separate.
