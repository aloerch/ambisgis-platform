# Ordinary developer runtime bundle

This assembles the four reviewed owned development images and the retained
rootless runtime into a relocatable **candidate**, without executing an engine.
It does not run the held targeted vulnerability probe, qualify the patched
engine, approve distribution or complete PLT-01 installation acceptance.

The bundle contains `bin/ambisgis`, the exact installer Python sources, a
separate retained Python 3.13 interpreter/stdlib/Compose module tree, patched
Podman/rootlessport from build-002, retained runc/conmon/netavark/aardvark/pasta,
the seccomp profile and component notices. Image application Python remains
3.12. Image source labels/manifests retain their reviewed `5e5d38b` producer
identity; the separately hashed runtime custody/closure binds these later
installer and launcher source bytes. Older images/binaries are never relabeled.

`build_bundle.py --output ABSOLUTE_FRESH_DIRECTORY` copies only pinned retained
inputs and writes `bundle.json`, `runtime-files.json`, source/custody manifests
and `assembly-result.json`. It validates the complete closure and all four OCI
archives with the existing installer. No image pull, build, package script,
package install, service or engine is invoked. The selected package source
locks and patched-engine build records remain unchanged in the notice tree.
Source archives stay in the referenced retained custody; this is not a complete
redistribution source package. The output parent and input custody are trusted
operator-controlled directories; existing output is rejected.

The launcher uses the pinned existing `/usr/bin/bash` bootstrap, then the
retained `env -i` and Python with `-S -s -P`. Every searched runtime directory,
helper, module and configuration template is in an exact membership manifest.
The shell, loader and bundle bootstrap bytes must already be trusted before
launch: a dynamically linked shell cannot erase `LD_PRELOAD` or shell startup
effects that occurred before its first instruction. The adapter does not claim
protection before that boundary. Child engine and provider environments are
constructed from a strict allow-list; operator HOME/XDG, Python, loader,
registry, remote connection, module, hooks and provider overrides are discarded.
The private settings are deterministic derivatives of product.json and bundle
paths, with byte equality checked before reuse. They are not another mutable
product configuration authority.

The developer storage driver is explicitly `vfs`; disk amplification and
throughput are unmeasured. It requires no overlay/fuse helper execution. Native
runc capabilities, SELinux labels/enforcement, seccomp, rootless mappings,
cgroups, IPv4-only isolation/egress and relocation remain actual installation
tests. No host firewall or SELinux setting is disabled. The existing systemd
user bus is required, checked as a socket in its UID-owned private runtime
directory; no host service is installed. Mapping wrappers call the existing
root-owned 0755 capability-bearing newuidmap/newgidmap. Their exact bytes,
capability attributes, host loader and transitive ELF inputs are prerequisites.
The actual host ncurses 113.1 bootstrap dependency is bound separately to its
accepted FND08 signed correspondence and retained exact sources; the selected
PLT runtime still carries its original 112.1 library. The generated host loader
cache is pinned as an existing-host input, not represented as a signed payload.

The retained Compose 1.6.0 source requires explicit `--in-pod false` and `run -T`
for this product profile. Installer invocation now supplies both and explicit
fixed installation names for the two initializers. A timed-out bootstrap can
therefore be inspected and stopped through the same owned-name checks; random
one-shot names are rejected. Every
create/run argument is compared against the exact retained provider's pure
argument projection from verified product-generated Compose data, including
mounts, network, immutable image, entrypoint, credentials-file paths and labels.
The projection's inert network-exists callback constructs argv only; it is not
a permissions test or a substitute for actual engine network inspection.
Pull/build/restore/checkpoint/remote/API-service commands and unrelated
containers, networks, volumes or arbitrary exec programs are excluded.
Stop/start/restart and down can affect only this installation; persistent bind
data and image/volume deletion are excluded. The fixed HTTP diagnostic client
is bound to its source hash, not a general Python execution escape.

The engine's native health timers invoke `systemd-run` with only PATH forwarded.
The narrow adapter validates the original 15s interval, unit/container ID,
program and private store arguments, then uses an exact health bootstrap and
WorkingDirectory. That bootstrap restores private config/loader/environment
before the native healthcheck. It adds only the transient health units already
created by Podman. Normal container stop removes them using the native
lifecycle; actual cleanup must be observed. The native conmon exit command is
different: retained engine `configureConmonEnv` forwards its strict environment
(except NOTIFY_SOCKET), and retained conmon `ctr_exit.c` uses `execv`, preserving
it. Its raw engine cleanup has absolute store arguments and private config
paths, so it does not require the ordinary wrapper's cwd.

The first ordinary lifecycle attempt passed relocation/init and loaded the
database image, then exposed a stream-handling defect: a native stderr warning
preceded valid image-inspect JSON in the merged capture. The startup repair
keeps stdout and stderr in separate private temporary files, checks their
combined 4 MiB result limit, and returns only stdout to JSON consumers. Neither
stream is included in failure exceptions. This limit is checked after process
completion; it is not a live disk-output quota. Private storage configuration
uses graphroot/runroot without the redundant deprecated rootless_storage_path.
The original failed installation and receipts remain unchanged; bundle-005
contains the repair for a separately reviewed fresh lifecycle attempt.

The second attempt validated all four image identities, then failed before
container/network creation because the pinned provider's version probe includes
an empty command slot: `Podman.output(['--version'], '', [])` produces
`['--version', '']`. Bundle-006 canonicalizes exactly this representation to
`['--version']`. It does not strip empty arguments from other commands or accept
additional version flags. The regression executes the exact retained provider
method in process while intercepting its subprocess boundary before child
creation. Its original failing result and the failed lifecycle remain retained;
passing argument tests do not establish installation acceptance.

The third lifecycle attempt created the owned database container but did not
start it. Its retained native error identified missing `libpathrs.so.0` during
runc startup, despite that library being present in the verified bundle. The
exact runc source constructs a fresh environment for its sealed init executable
without the relocated library search path. `runc_build.py` applies a narrow
source repair that carries only the wrapper-validated `LD_LIBRARY_PATH` beside
the existing `GOMAXPROCS`; the later native init `Clearenv` remains unchanged.
The offline build uses the retained runc 1.5.1 archive's own matching vendor
tree, existing Go/GCC/sysroot custody and fresh build/cache directories. Only
`TestAmbisGISInitEnvironment` runs, covering absence, the private library path
and exclusion of unrelated variables. No runc CLI or container is executed.

Build-001 is retained but excluded because its Git revision field contained a
descriptive label. Corrected build-002 leaves upstream revision metadata at its
default and binds the archive, patch and output hashes in external custody.
The candidate carries the exact source archive, patch, build records, original
Apache license, thirty vendor notice files and a dated modification notice.
Required static archives are absent from the selected toolchain, so static
linking is not claimed. Native library resolution after the repair remains an
ordinary installation acceptance test.

The same failed attempt revealed Podman's default `rprivate` tmpfs propagation
in both actual inspection and OCI data. Its selected, sanitized projection is
retained in `fixtures/native-tmpfs-003.json`. Inspection now accepts this
recursively private mode while rejecting shared/slave propagation, conflicting
modes and duplicate options. The original failing regression is preserved;
the rest of the ownership, image, network, mount and isolation checks remain
mandatory. The never-started original container and its data remain retained.

In-process tests run with the retained CI Python:

```sh
python -B -m unittest discover -s build-support/development-runtime -v
python -B -m unittest discover -s plan/tests -v
cd plan
python -B tools/validate_package.py --require-schemas
```

The provider argument test reads the already reviewed signed payload module at
SHA256 `14320ec9102f4aa9602426f2f4e549ca5c6536beb1ccc9de2931ad84e450b919`.
It fails if that input is missing or changed; it never installs a dependency or
starts a provider subprocess. No tests here assert GIS or runtime acceptance.
After independent source review, the separate lifecycle driver will relocate
the complete bundle before first init, exercise actual protected services,
preserve identity/credentials/edited metadata across restart and reinit, fault
and recover only the renderer, and retain all persistent data on shutdown.
