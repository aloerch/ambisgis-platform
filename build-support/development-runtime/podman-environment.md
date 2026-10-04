# Ordinary OCI child environment repair

This successor repairs the owned developer runtime's direct Podman-to-runc
environment. It copies the exact retained `build-002/source`, verifies its full
9,960-member preparation manifest, and preserves the three prior repairs and
complete vendor tree. It adds an Apache-2.0 helper and pure unit, and replaces
only the environment construction in `StartContainer`, `UpdateContainer`,
`killContainer`, `DeleteContainer`, `PauseContainer`, and `UnpauseContainer`.
The public `KillContainer` caller and its signal/argument behavior are unchanged.

Each caller supplies the existing calculated `XDG_RUNTIME_DIR`,
`rootless.IsRootless()`, and `os.LookupEnv`. The helper copies only `PATH` and
`LD_LIBRARY_PATH`, plus `DBUS_SESSION_BUS_ADDRESS` when rootless. These values
come from the independently reviewed owned launcher. The rootful session-bus
exclusion matches the existing conmon boundary. Missing values stay absent;
present empty values retain their original representation. No whole environment
is inherited. No container environment, conmon/init boundary, checkpoint/restore
path, UID detection, cgroup manager, host policy, or namespace setting changes.

`podman_env_build.py --prepare-only --output NEW_DIRECTORY` performs only inert
hash verification, copies, source repair, and compiler staging. It reuses the
pinned prior staging/compiler-wrapper functions and socket-denial helper;
it never calls the prior recipe's build dispatcher. The retained Go/GCC/native
closure and source archives are rehashed, with fresh caches and no package fetch.
All original source and vendor notices remain in the complete source tree. The
generated `MODIFICATIONS.txt` dates and describes this change. Source revision
metadata is not overridden; custody identifies the derived source by hashes.

After independent pre-execution review, a separate explicit command may run:

```sh
python3 podman_env_build.py --execute-prepared --output PREPARED_DIRECTORY --invocation-sha256 REVIEWED_INVOCATION_SHA256
```

The command plan compiles and executes only a standalone file-pair test. It
does not import the libpod package or execute inherited `TestMain`, package init,
native integration suites, security probes, Podman, rootlessport, or containers.
An extracted pre-repair `StartContainer` environment block (only the OS lookup
dependency is injected) must fail the same four pure environment subcases.
The actual new production helper must pass them. Podman and rootlessport are
then compiled from the full owned source; neither binary is executed. The
negative baseline is a faithful extracted environment calculation, not an
execution of the original container method. Native results remain pending until
this separately reviewed command actually runs.

The production helper unit tests explicit values, absent and empty values,
rootful exclusion, and unrelated environment rejection. Inert Python guards
prove the six exact callsite substitutions and unchanged remaining source,
reject wrong source/reapplication, restrict the compile/test command plan, and
reject escaping source links/special files. These are source/build guards, not
installation or full native suite acceptance. Busctl bundle mapping and later
ordinary installation validation are separately owned by the integrator.
