# Direct DNS observation for the development installation

This library observes one already verified installation. It does not start, stop,
signal or enter anything, and has no command-line interface. The lifecycle driver
must construct it from its verified product configuration and bundle file manifest:

    expected = dns_observation.from_verified(
        directory, runtime.config, runtime.bundle_root, runtime_files_manifest, os.getuid())
    running = dns_observation.observe_running(expected)
    stopped = dns_observation.observe_stopped(expected, running)

There is no second configuration or policy authority. The caller must have verified
the installation marker, selected bundle and manifest before supplying these inputs.
Use the successful running observation from the same installation and execution,
not arbitrary user-supplied evidence. An injected reader supports inert fixture tests;
production callers omit it. No environment variables, raw command line, DNS entry
contents, arbitrary exception text or unrelated process information are returned.

The fixed source-derived paths are:

* RunRoot runtime/run, from the owned adapter's global_arguments.
* Network run directory runtime/run/networks, from owned common
  libnetwork/network/interface.go (store.RunRoot() plus networks).
* DNS directory runtime/run/networks/aardvark-dns, from netavark
  src/commands/setup.rs; PID file aardvark.pid, from src/dns/aardvark.rs.
* DNS network entry ambisgis-<installation UUID without hyphens>_internal%int.
  Product installer/config.py determines the network name; netavark
  src/network/bridge.rs passes that name, and src/dns/aardvark.rs appends
  %int for an internal network. This is a network name, not a network ID.
* Network namespace bind path
  runtime/run/networks/rootless-netns/rootless-netns, from owned common
  libnetwork/internal/rootlessnetns/netns_linux.go, getOrCreateNetns.

Running verification requires the sole expected DNS entry and PID file beneath
the private installation, bounded regular-file reads, the manifest-pinned
runtime/helpers/aardvark-dns inode/path/content hash, and the exact native argv:
<that executable> --config <that DNS directory> -p 53 run.
Port 53 is the native default; another port or extra argument fails this profile.
PID/start time, process-group/session IDs, host-visible UIDs, rootless UID mapping, net/user/mount namespace
identities and cgroup are read from that single anchored /proc/PID directory.
The observer never enumerates /proc, reads process environments or follows an
arbitrary PID. Identity fields are reread to detect changes; variable status
counters are deliberately excluded. Session IDs are recorded without assuming setsid
succeeded or requiring SID to equal PID. Cgroup membership is evidence, not a claim
of a dedicated cgroup, resource limit or survival after the owning cgroup ends.

A matching host-visible namespace bind device/inode verifies the binding. A
different inode on the namespace device fails. An inaccessible or absent bind,
or a host view of the backing filesystem placeholder instead of the namespace
mount, is unsupported / namespace_binding_unavailable, preserving the separately
verified process identity. No namespace entry or host mount adjustment is attempted.

Receipts contain phase, status, classification, binding and cleanup_verified.
A successful process observation also contains identity, identity_verified,
namespace_binding_verified, cmdline_match and the private DNS entry's SHA-256
(not its contents). Status verified for running requires all checks, including
the namespace binding. Unsupported binding is never full acceptance.

Cleanup requires a prior running receipt with this exact expectation binding.
It reads only that prior PID/start identity, so a zombie or removed executable
cannot become a false cleanup pass. TRANSIENT_CLEANUP contains exactly
live_retained, pidfile_retained and config_retained; a caller may poll these with
its own finite deadline. PID reuse, a changed PID file, unknown config entry,
identity mismatch, missing prior proof or an unsupported read must not be treated
as transient success. Only gone means the prior process and both native files
are absent. Empty native directories may remain. The library never deletes them.

For a prior observation with unsupported namespace binding, cleanup can still
record daemon_cleanup_verified=true after the process and files disappear, but
classification is namespace_binding_unavailable, status is unsupported,
namespace_binding_verified=false and
cleanup_verified=false. This allows collecting unaffected evidence without
claiming full lifecycle acceptance. Conclusive retained-process/file and PID-reuse
outcomes always remain failed, even when namespace binding was unavailable.
The normal owned-container shutdown check
and pause/health-helper accounting remain separate.

These are bounded point-in-time observations, not atomic guarantees against later
changes. Aardvark's native readiness pipe is sent before first-bind proof; neither
a live daemon nor an entry hash demonstrates a DNS response. The existing catalog
health client calls localhost HTTP; its server checks the database using Django.
The fixed database hostname is database, but that alone does not distinguish
DNS transport from hosts-file resolution. Actual DNS service after CLI exit and
full lifecycle acceptance remain separate evidence requirements.

Only fixture tests have been run for this increment. They redirect process reads
to inert temporary files and do not inspect live /proc, invoke an engine or
native binary, connect to sockets, or exercise the held targeted probe.
