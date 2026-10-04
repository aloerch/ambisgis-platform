# Selected development health timers through the native manager connection

Lifecycle006 reached the native private systemd connection, then the retained
`systemd-run` wrapper returned its generic validation error. The reconstructed
command passes the exact timer grammar. Pure metadata checks reproduce a
separate source-level incompatibility: Podman invokes the wrapper from its
rootless user namespace, while host ownership and user-manager paths are
validated as host identities. Actual rejected argv/UID maps were not captured;
this remains a source-supported diagnosis, not an observed first-guard trace.

This producer preserves the complete `podman-systemd-build-001` source and five
prior repairs. It adds one selected branch in `createTimer`, one pure planning
and completion helper, and its exact-file Go test. Native behavior with an empty
`AMBISGIS_HEALTH_TIMER_PROFILE` remains unchanged. The owning launcher must set
the constant `development-v1` itself after its existing complete validation;
it must never forward a caller-selected marker. That launcher change is outside
this producer. Unknown markers, rootful mode, startup checks, non-15s intervals,
or drifted paths/arguments fail before connecting to the manager.

The finite profile requires clean absolute installation/bundle paths composed
of ASCII letters, digits, underscore, dot, slash and hyphen. Spaces, colon,
quotes, backslashes, percent, dollar and controls are rejected. This keeps the
two-component PATH unambiguous and excludes systemd expansion/specifier inputs.
For this alphabet the retained systemd261.2 description quoting is identity;
the helper preserves `[systemd-run] ` plus the exact fixed launcher argv.
No such restriction is imposed on the unselected native path.

The selected path uses the existing verified private `ConnectToDBUS` connection
and retained `StartTransientUnitAux` API. One timer-plus-auxiliary-service request
uses the existing CID/random suffix, mode `fail`, exact timer15s/accuracy1s and
`RemainAfterElapse=false`. The service keeps LogLevelMax notice, zero start-limit
interval, the exact installation working directory, the single fixed PATH and
the fixed host-context `healthcheck-timer` launcher. No generic unit, property,
resource, executable, environment or command API is exposed. The user manager
starts that launcher as its host user, so complete host/bundle/config checks
remain intact; no overflow-owner mapping, inherited UID trust or host check
bypass is introduced. Private engine XDG, cgroups, SELinux and healthchecks stay.

Timer properties use the actual retained wire types: `TimersMonotonic` a(st)
with OnUnitInactiveSec=15000000, `AccuracyUSec` uint64(1000000), and boolean
RemainAfterElapse. Service LogLevelMax is int32(5), StartLimitIntervalUSec is
uint64(0), and ExecStart uses a(sasb) with its final ignore-failure bit false.
Type, User/Group, Slice, CollectMode and other unrequested properties are absent.
Direct private connections do not need broker-only AddRef.

The job channel has capacity one, and both submission and job completion use a
30-second context. A completed `done` job is required before HCUnitName is saved.
This is a bounded wait refinement of the selected developer profile; existing
unselected behavior is untouched. Original `startTimer`, timer-before-service
stop, ResetFailedUnit and all other source remain byte-identical.

One D-Bus request is **not atomic rollback**. Retained systemd creates/configures
the main unit, then its auxiliary unit, then queues the job, returning directly
on intermediate errors. A failed/lost reply, non-done job, timeout or save failure
may leave either or both units. Errors preserve the exact attempted CID/suffix
and explicitly require reconciliation of its `.timer` and `.service` before
retry. There is no automatic removal: a mode=fail collision may refer to a
pre-existing unit whose ownership is not established. No clean rollback is
claimed. The external installer must retain the safe attempted identity for
root-owned reconciliation. Native original cleanup is unchanged.

Preparation is inert: exact predecessor/source/vendor/toolchain/source-custody
and host-bootstrap hashes are checked, fresh copies and empty caches are made,
and a complete invocation is recorded. Existing producer/failed lifecycle
records are never replaced. The same Python source-contract oracle fails on the
original source and passes after the bounded patch. These are inert source
guards, not native product tests. Four commands are planned, but require separate
independent pre-execution review:

1. Compile exactly the new pure helper and its test files, not the libpod package.
2. Run only TestAmbisGISHealthTimer: fourteen finite property, rejection,
   completion, cancellation, late-send and failure-preservation subcases.
3. Compile Podman from the preserved full owned source and retained vendor.
4. Compile rootlessport from those same inputs.

No old native suite, libpod TestMain, D-Bus connection, engine, namespace, timer,
service or held vulnerability probe is executed by preparation/inert tests.
Future execution retains the existing socket-denial build guard, explicit
compiler/bootstrap closure and exact logs. The Go test has no live manager:
injected callbacks prove request/job/save ordering. Native compile/test results
are unperformed until authorized and independently reviewed. The original source
revision is retained without overrides; new exact patch/source/build hashes
identify the derived artifact, with a dated Apache-2.0 modification notice and
all original source/vendor notices preserved.

This source increment does not complete installation, timer cleanup, security,
redistribution, OS/port/concurrency/log matrices, PLT01 or the full scoped MVP.

The behavior reference is exact retained systemd261.2 source archive SHA256
`cc84192fe4c7bc1373df650e6cbb81109d4fff268f9afac12edd3856fde95fef`.
Its `src/run/run.c` (SHA256
`e03b9538f8316fe59b6495c508954aca284940e0a9618486fff080515b3b802b`)
constructs the request; `src/shared/bus-unit-util.c` encodes the property types;
`src/core/dbus-manager.c` establishes the possible intermediate effects.
`src/basic/escape.c` and `escape.h` establish the finite description alphabet.
The archive is an additional pinned behavioral reference, not a new compiled
runtime dependency or code executed during preparation.
