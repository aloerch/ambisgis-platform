# Concurrent development installation commands

`concurrent_installation.py` covers the command-concurrency part of
PLT01-GAP-05. It is a finite, foreground helper for one fresh synthetic
installation. It runs exactly two concurrent `init` invocations and then
exactly two concurrent `up` invocations with the selected bundle launcher.
It accepts no command, resource, principal, SQL or engine argument from its
caller. There is no retry, background scheduler, daemon or reset.

After independent source review, the integrator can run the helper with the
retained reviewed Python interpreter and an independently reviewed exact
bundle:

```sh
python deploy/development/concurrent_installation.py \
  --bundle /absolute/reviewed-bundle/bundle.json \
  --bundle-sha256 EXACT_REVIEWED_MANIFEST_SHA256 \
  --directory /absolute/new-private-installation \
  --output /absolute/new-private-evidence
```

Both destination paths must be absent, absolute and nonnested; symlink
components are rejected. The helper reuses the lifecycle relocation/verification
code, including the selected launcher, full runtime closure and image archives.
It creates the installation as a private empty directory and binds its device,
inode, owner and exact bundle in `installation-marker.json` in the private
evidence directory. The marker is outside the installation because a file
inside a fresh root would correctly be treated as unmarked input by `init`.
The marker never authorizes adoption of an existing installation.

The installer deliberately takes a nonblocking filesystem lock. The helper
therefore accepts one successful peer plus only the exact existing
`Another installation command is already running.` rejection from the other
peer. Two successful results are also allowed if both CLI lifetimes overlap.
The receipt distinguishes observed launch overlap from an observed busy result;
launch overlap alone does not prove that both workers reached the critical
section simultaneously. It fails if the first child finishes before overlap
can be observed and never retries to manufacture a passing result.

The init pair must report exactly one newly created identity. Any successful
second call must report that same existing identity. A racing
`Installation directory is not empty and has no product configuration.`
rejection is a failure, not an accepted busy response. Such a failure remains
evidence for a separate installer repair. The up pair must include a successful
usefully ready result with the exact installation, four service roles, internal
network and four readiness checks. Both-busy, generic error, malformed JSON,
unexpected output fields, numerical stand-ins for booleans, identity drift and
nonready results fail closed.

Configuration and credential files are validated through the installer and
their exact bytes are compared after successful command completions, after
each pair and around shutdown. Receipts contain the installation UUID and file
SHA256s, never credential values. The first observed identity is retained, not
a reconstruction from regenerated state. A final reused native inspection
checks only the six named owned roles, their image/configuration/security
bindings, the four running services, stopped/absent initializer roles and the
installation's network. The existing runtime remains the authority for these
checks.

Each pair starts both children before draining/waiting. It uses a clean child
environment, no shell, and new process sessions. stdout and stderr are read
with a combined streaming limit of 4 MiB per child; raw CLI bodies are never
written to evidence. The pair deadline is 1,200 seconds. An exception, EOF,
output violation, timeout or interrupt enters bounded child cleanup. TERM
and then KILL are sent only to a process group whose original Popen leader is
still alive and unreaped; each grace/wait bound is five seconds. After reaping,
read-only `/proc` observations must show no remaining members of those CLI
groups. A leftover group or uncertain inspection is recorded as incomplete;
the helper never kills a process discovered by scanning the host.

Only after CLI cleanup is established can the finally block reuse the existing
lifecycle `stop_owned` method. This revalidates the marked installation and
bundle, inspects the exact owned roles, stops only their running containers and
requires zero running containers on readback. Identity drift or uncertain
workers prevent automatic engine cleanup and require integrator reconciliation.
No configuration, data, image storage, volume, container or evidence is deleted.
The helper retains failures and records cleanup failure independently from the
operation failure. Receipt-write failure itself fails the helper. SIGTERM and
KeyboardInterrupt receive the same finally handling; SIGKILL or host loss
cannot promise finalization.

A command-concurrency pass is **not** completion of GAP-05 or PLT-01. This
helper always records `full_installation_acceptance: false`,
`native_uniqueness_acceptance: false`,
`installed_sql_role_acceptance: false` and
`health_helper_cleanup_verified: false`. CLI UUID/configuration preservation
does not prove preservation or uniqueness of native principals, items,
permissions, migration state or effective installed serving-role privileges.
Those require their separate actual before/after native identity and SQL
checks. Detached health units, conmon and other helpers that leave the CLI
process group require separate owned-state reconciliation. No targeted
container vulnerability probe is invoked or replaced.

The focused tests use inert in-process pipe peers and synthetic archive/state
fixtures. Popen and signal delivery are replaced; no installer CLI, engine,
native compiler, container or HTTP request runs. Their failure/cleanup results
are helper evidence only. The initial missing-module baseline and subsequent
test corrections are retained outside the repository. Actual command
concurrency remains pending until the reviewed helper is run on a reviewed
bundle and its source, results and cleanup are independently verified.
