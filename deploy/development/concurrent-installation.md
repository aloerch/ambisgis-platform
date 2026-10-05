# Concurrent development installation commands

`concurrent_installation.py` covers the command-concurrency part of
PLT01-GAP-05. It is a finite, foreground helper for one fresh synthetic
installation. It runs a fresh pair of concurrent `init` invocations and a pair of concurrent
`up` invocations with the selected bundle launcher. After the first protected
journey edits the fixed synthetic item, it runs an existing-only `init` pair
and another `up` pair, then verifies the old metadata before the next protected
journey can edit it.
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

The fresh init pair must report exactly one newly created identity. The explicit
repeated-init phase requires at least one existing-identity success and permits
only existing successes or the exact lock-busy result; any creator fails. Any successful
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
a reconstruction from regenerated state. After the first up pair, a reused native inspection
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
and `health_helper_cleanup_verified: false`. Without the explicit database
option below, it also records `installed_sql_role_acceptance: false`.
The two unchanged protected journeys compare the fixed native resource and
owner/viewer IDs and restored object-policy fingerprints. The native policy
program requires exactly one selected sample alternate and exact principals.
The second journey reads the retained edited title before issuing new edits.
Only successful comparisons set `native_identity_and_policy_preserved: true`.
This does not establish general native cardinality, migration-state equality or
effective installed serving-role privileges; those retain separate checks. Detached health units, conmon and other helpers that leave the CLI
process group require separate owned-state reconciliation. No targeted
container vulnerability probe is invoked or replaced.

The focused tests use inert in-process pipe peers and synthetic archive/state
fixtures. Popen and signal delivery are replaced; no installer CLI, engine,
native compiler, container or HTTP request runs. Their failure/cleanup results
are helper evidence only. The initial missing-module baseline and subsequent
test corrections are retained outside the repository. Actual command
concurrency remains pending until the reviewed helper is run on a reviewed
bundle and its source, results and cleanup are independently verified.

The helper retains the lifecycle record arrays needed by the inherited journey,
metadata, permission restoration and token-cleanup methods. Any recorded
incomplete subcheck produces an `incomplete` result and exit1, never a pass.
Explicit incomplete shutdown likewise prevents a passing result. DNS namespace
and global helper cleanup remain unqualified; no new DNS or held qualification
operation is introduced. All overlap/deadline/output/session cleanup bounds
remain unchanged. The tests invoke the inherited metadata login/read/token-cleanup
and protected-journey methods using only synthetic clients, preserving their
record arrays and read-before-edit ordering. This source proposal has not run actual concurrent CLI calls.

## Optional installed database oracle

After independent source review, `--installed-database-oracle` adds fixed checks
to this same fresh invocation. It provides no existing-installation, SQL, role,
database or connection-target option. Omitting it preserves the default record
and behavior. The first observation follows the first protected journey. The
second follows the repeated init/up pairs, before the second journey can edit
metadata. Both observations must pass and have identical logical snapshots.

`installed_database_oracle.py` runs as fixed reviewed Python code in the
validated owned database container. It reads the already mounted database role
credentials privately. The admin socket is used only for read-only projections.
Serving tests use their actual passwords over container-local `127.0.0.1:5432`;
they never emulate authentication through a superuser `SET ROLE`. Each of 19
fixed denials first proves the session/current role, database, successful read
and read/write transaction mode. Only SQLSTATE `42501`, with an explicit
savepoint/outer rollback and no additional diagnostic, passes. Connection,
syntax, read-only-transaction and timeout errors cannot count as denials.

The cases cover public/schema/temporary DDL, migration-table DDL and native
resource ownership for the relevant serving roles; the render reader must also
fail catalog reads/deletes. The transport reader must fail native `gf_rule`
insert/update/delete and ownership changes. DML uses zero-row predicates so
even an unexpected grant cannot evaluate row defaults or advance a sequence.
An unexpected success is rolled back and fails the check. There is no
`CREATE DATABASE`, `nextval`, `setval`, grant/revoke, role change or persistent
DDL. Fixed psql calls receive SQL on stdin and a scoped credential environment.
Each call has a maximum ten-second deadline, SQL statement/lock limits of
four/1.5 seconds, and a complete combined output limit of 1 MiB. An observation
has a 120-second budget; the outer owned engine call has a 150-second deadline.
No raw query, native row, password/hash, SQL stderr or exception message is
written to a receipt. Unavailable/oversize/timeout results fail closed and leave
ordinary owned shutdown and independent effects reconciliation required.

The independently defined projections cover all native principal IDs and
selected credential/privilege flags, resource IDs/ownership/selected metadata, OAuth
application bindings, and applied migration IDs/names/timestamps. They require
one instance of each selected principal, resource UUID/alternate and application,
and no duplicate applied migration key. Sorted counts and SHA256 fingerprints,
plus the existing journey's exact principal/resource IDs, are compared across
commands. Two fixed transport rules and the Hibernate sequence's *read-only*
state, selected role memberships, database ACLs and application schema
definitions/ACLs are also fingerprinted before and after denial attempts. This
is logical-state preservation, not equality of WAL, statistics or storage bytes.

The fixed SQL identifiers come from the retained owned GeoNode revision
`2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4` (`people.Profile`,
`base.ResourceBase`), its selected `oauth2_provider.Application` model in
geonode-oauth-toolkit 2.2.3.1, and Django 5.2.15's explicit `django_migrations`
recorder/default model-table naming. `gf_rule` and its columns come from owned
GeoFence revision `132a1d16901b7039f974c8c30d7e7df042d8af4c`,
`services/core/model/.../model/Rule.java`; the two expected rule values are
the fixed `DevelopmentGeoServer.transport` projection. The unchanged product
database bootstrap supplies the three tested serving roles and authentication
boundary. Membership columns follow the selected owned PostgreSQL 15.19
`pg_auth_members` catalog, not a newer PostgreSQL schema. No product
health/auditor result substitutes for these observations.

Only actual successful native observations may set the opt-in receipt's
`installed_sql_role_acceptance` to true, scoped to these named cases. These
source-only tests provide no such credit. The oracle does not prove full
migration graph/upgrade correctness, general native uniqueness, managed
geodatabase isolation, serving-container migration-secret file visibility,
namespace/helper cleanup or overall installation acceptance. Those exclusions
remain explicit even if the oracle passes. Image and bundle payloads are
unchanged: this is host-side test code with a fixed transient program, and its
source bytes must be pinned separately when the integrator authorizes a run.
