# Retained development-runtime inputs

These tools select and inspect supporting Linux packages for PLT-01. They do
not install packages, enable services, execute package scripts, or constitute
an installer. PostgreSQL/PostGIS, GeoNode and GeoServer product images still
require the existing source-owned AmbisGIS outputs and actual integration tests.

`retained-inputs.lock.json` records 219 exact signed binary archives and 148
matching complete OBS source groups (archives, specifications and patches).
It also binds the large private inspection receipts by SHA256. It is an input
custody checkpoint, **not an approved runtime or distributed artifact**.

## Current security hold

Selected Podman 6.0.2 is affected by [CVE-2026-94603 / GHSA-2cvf-wqm6-wr9g](https://github.com/podman-container-tools/podman/security/advisories/GHSA-2cvf-wqm6-wr9g),
published 29 September 2026. A checkpoint image annotation can cause `run` to
ignore requested sandbox restrictions. Runtime execution is held while a source
repair is prepared and independently reviewed. The original archive/source lock
remains historical evidence; any repaired binary needs its own actual build,
source, dependency, tests and output identity. Archive/image rejection guards
and native sandbox checks remain necessary. No unaffected-version claim is made.

## Selection and provenance

`selection.py` consumes one already retained, hash-pinned publisher primary XML
snapshot: `https://download.opensuse.org/history/20260916/tumbleweed/repo/oss`.
It retains multiple identities, uses actual librpm version comparison and fails
on ambiguous or unsupported requirements. Existing host identities can only
choose among exact snapshot providers; they cannot replace missing archive bytes.
The eight explicit roots were `podman`, `python313-podman-compose`,
`shadow-pw-mgmt`, `libcontainers-default-policy`, `registries-conf-default`,
`libz1`, `libncurses6`, and `cracklib-dict-full`.

The selected graph has 1,622 publisher requirement edges and ten evaluated
conditional requirements, including kernel/SELinux/boot-related packages. This
is deliberately conservative custody, not an installation solver or a decision
to apply their scripts/configuration. A runnable prefix needs a separate file,
linkage, configuration, host-prerequisite and license selection.

`custody.py binaries` retains exact archive size/digest bytes, checks signatures
and binds signed package identities and source-build DISTURLs. `sources` verifies
every selected binary before grouping by its complete signed source identity.
OBS source listings and every entry must reproduce the signed source-set digest;
new SHA256 hashes are retained for each file. The OBS MD5 linkage is recorded
honestly as original build provenance, not described as a new cryptographic
signature. Retrieval/replay never overwrites differing bytes.

`audit.py` repeats verification in a private RPM database containing only the
[published openSUSE Factory key](https://build.opensuse.org/projects/openSUSE:Factory/signing_keys),
fingerprint `AD485664E901B867051AB15F35A2F86E29B700A4`. The exact retained key has
SHA256 `b5745739ebfb95b25b8e810f9bcb847fe750ccda598bd85f02f0e974599a6d7e`.
The snapshot repository metadata's detached signature was also verified with
that isolated key. Neither operation changes the host keyring.

Publisher metadata prunes some redundant requirements. The audit requires all
publisher entries in signed headers, and proves every additional signed-header
requirement against exact selected archive providers using librpm. All 1,689
additional requirements passed; none was merely assumed redundant. Other
dependency groups must match. Package-format `rpmlib` requirements are checked
against the existing inspection tool. Full signed file membership, modes,
capabilities, license declarations, scripts and triggers are retained for review.

`payload.py` checks exact signed membership, types, sizes and SHA256 file digests.
It places regular files in separate package directories with mode `0600`.
Symlinks remain JSON data; devices, privileged modes and capabilities are never
created. No script, executable or package interpreter is run. This inert store
contains 219 verified package payloads and is not a runnable filesystem.

## Actual checks and limits

The final static pass ran 33 selection/custody/audit guards, including actual
signed RPM/header checks and native librpm semantics. Five further payload
guards cover traversal, byte/membership changes, devices, symlinks, privileged
modes and existing-file protection. All 38 passed with zero skips. The plan's
503 package tests and ten schema/example pairs also passed; they are not GIS
product or installer acceptance.

Earlier attempts are preserved: legitimate `~` snapshot filenames, binary RPM
SOURCEPACKAGE `(none)`, omitted signed requirements, `@` source patch names and
literal systemd `\xHH` filenames initially failed conservative checks. The narrow
repairs retain traversal, digest, source-set and provider checks. Initial wrong
native unversioned-provider expectations were corrected against actual librpm.

Commands accept explicit input/output paths; see each tool's `--help`. Run the
helper guards with the existing host RPM bindings and retained actual evidence:

```sh
CONTAINER_TEST_SELECTION=/absolute/selection.json \
CONTAINER_TEST_REUSE=/absolute/retained \
python3 -m unittest test_selection test_custody test_audit test_payload -v
```

Run from this directory. Missing actual signed archives fail rather than skip.
Every acquisition/audit attempt uses a fresh receipt directory and preserves
failures. Source snapshots and actual command/log/result hashes are recorded in
the locked evidence references. Full source toolchain bootstrap, runtime
relocation, namespaces, storage, networking, persistent install/restart, clean
supported-host installation, distribution notices and release gates remain open.
