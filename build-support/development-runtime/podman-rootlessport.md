# Owned rootlessport path and startup repair

The retained ordinary loopback-port startup constructed a named Unix socket under
its full private state directory. The selected installation produced a127-byte
socket path; retained Go/Linux permits107 pathname bytes. The helper log stopped
before its readiness handshake. The child driver also reported errors through an
unbuffered channel while its main goroutine waited for stdin, so an early failure
could remain unreported. The actual syscall frame was not captured. These facts
are separate from the retained, unexecuted vulnerability qualification.

`podman_rootlessport_build.py` derives from the exact independently reviewed **prepared** inspect-sysctl
producer, whose verifier binds the completed owned health-timer predecessor.
It does not assume an inspect build result. All six completed earlier patches,
the seventh prepared inspect patch, retained toolchain and vendor bytes remain. Four exact callsite edits in `cmd/rootlessport/main.go` add one owned
helper and its tests. The freshly created state directory is opened with
`O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`; the parent keeps that descriptor alive
and uses its `/proc/self/fd` path. The same directory is passed to the child as
extra descriptor3; only the two known built-in socket/FIFO paths are rewritten.
Port mappings, network namespace entry, credentials and native vendor driver
remain unchanged. No host short directory, symlink, filesystem relocation or
new dependency is introduced.

The child waits for either driver completion or parent stdin closure. Completion
channels are buffered; quit is closed once. Early driver error (including
unexpected early success) reaches main immediately. After parent EOF, driver
shutdown has a fixed three-second bound. A blocked stdin goroutine on an early
error lasts only until the existing helper main exits; no additional process is
created in production. These changes do not establish whole-product cleanup.

The prepared native plan compiles and runs only explicit helper files, then
builds the normal engine and rootlessport binaries. Three real long-path socket
cases retain a failing predecessor **path-construction witness**; this is not a
replay of the entire old engine. Fixed checks include actual extra-FD round trips in both directions,
including child listener/parent client and unlink before closing the directory, symlink/file/opaque negatives, early-error propagation, EOF ordering
and bounded shutdown. Both native helper invocations have a15second Go test
deadline. Each uses fresh test directories; no service, namespace,
container, bus or Internet connection is part of those tests. Root must review
and execute the exact native plan separately. The Python checks are inert
producer/custody guards and give no native socket or installation credit.

The native inspect projection source and its exact compile/unit guards are
preserved in the combined command plan before the rootlessport checks. Both
normal binaries are built once afterward. The Python created-state installer
change remains independently reviewed and integrated by root. The complete
combined source and command inventory requires separate review before execution.
All previous failing attempts, licenses and notices remain retained. Installation,
private journeys, authorization, persistence/recovery, DNS cleanup, OS/port and
concurrency matrices remain open until their actual acceptance runs pass.
