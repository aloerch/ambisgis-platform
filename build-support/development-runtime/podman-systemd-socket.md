# Owned user-manager socket selection

The fifth ordinary lifecycle attempt failed while creating a health-check timer.
The retained error names the installation-private XDG runtime's missing
`systemd` directory. The exact Podman source selects
`XDG_RUNTIME_DIR/systemd/private`, resolves that path and dials the direct
systemd user-manager peer. Its native authentication uses
`AuthExternal(rootless.GetRootlessUID())`.

This successor changes one rootless path assignment and adds a pure selector.
A nonempty `AMBISGIS_SYSTEMD_USER_SOCKET` takes precedence; empty or absent
values preserve the original `filepath.Join(XDG_RUNTIME_DIR,"systemd","private")`
fallback. The owned launcher must construct this value from the actual caller's
`/run/user/<uid>/systemd/private` after validating the existing socket, ownership,
permissions and absence of symlinks. Caller environment values are not trusted.
The separate launcher change is outside this producer's file ownership.

Native `EvalSymlinks`, `Dial`, authentication, close/error behavior and the rootful
connection remain unchanged. The installation-private XDG and engine stores
remain private. No socket is created, symlinked, replaced or reconfigured.
No namespace, cgroup-manager, host-policy or health-check disabling change is
included. Other source call sites, including wrapper-excluded autoupdate/quadlet,
retain their command boundaries. This does not claim a successful connection
or timer lifecycle.

`podman_systemd_build.py` derives from exact completed `podman-env-build-002`.
Its preparation revalidates that producer's source, outputs, records and
preparation, then preserves the three earlier repairs plus the ordinary OCI
environment repair and all vendor source/notices. It carries the original
source revision, archive/obsinfo, four prior patch references, and a new patch
and dated modification notice. It does not invent or override Git metadata.

Only pinned predecessor inventory, staging and validation helpers are reused.
No predecessor child, execute or main function is invoked. Preparation copies
a fresh complete source and retained toolchain, records every file/link, compiler
command, host bootstrap and retained source input, and leaves all output/cache
directories empty. It does not compile or execute Go, Podman, a test ELF, a
container, D-Bus client or held test.

The exact six-command plan is separate from preparation and requires an
independent review before execution:

1. Compile the extracted original selector with the new test, by two exact files.
2. Run only `TestAmbisGISSystemdUserSocket`: both original fallback cases must
   pass and both explicit-socket cases must fail with the expected failing exit.
3. Compile the new production selector and its test by two exact files.
4. Run only that test: all four cases must pass.
5. Compile the owned Podman artifact.
6. Compile rootlessport from the same preserved source and toolchain.

Explicit test filenames avoid importing the systemd package, its initialization,
`TestMain`, inherited suites or socket/engine code. Python unit tests validate
the source delta, command plan and expected native-log shape; they are inert
guards, not native test evidence. Native baseline and new-unit results remain
unperformed until the separately reviewed execution occurs. The source repair
does not itself establish successful D-Bus authentication or installation.

Execution revalidates the complete preparation, prior custody, toolchain and
host bootstrap. Network evidence uses the already reviewed non-AF_UNIX socket
denial wrapper. AF_UNIX services and the host filesystem remain accessible;
this is a trusted retained-input build, not a hostile-code sandbox or a claim
that every compiler was bootstrapped from source. Existing held runtime-security
tests remain excluded. Build and static closure results do not complete PLT01,
source redistribution, runtime security, release or scoped-MVP acceptance.
