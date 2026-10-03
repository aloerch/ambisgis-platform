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
