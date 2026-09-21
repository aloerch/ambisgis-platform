# Configured GeoServer authorization fixture

Expected matrix recorded before the first application test. This is a disposable
inherited-component test, not the permanent AmbisGIS catalog/policy authority.
The identity endpoint implements the retained GeoNode opaque `verify_token`
protocol (POST form token and client Basic authentication). It is synthetic;
actual GeoNode acceptance and browser SSO are outside this fixture.

| Identity | Public WFS feature | Private WFS feature | REST workspace create/delete |
|---|---|---|---|
| Anonymous / absent or empty bearer | PUBLIC_WITNESS | deny without PRIVATE_WITNESS | deny, state unchanged |
| Invalid/expired bearer | explicit anonymous policy only | deny | deny, state unchanged |
| fixture-reader / ROLE_FIXTURE_READER | PUBLIC_WITNESS | PRIVATE_WITNESS and real geometry | deny, state unchanged |
| fixture-outsider / no read permission | PUBLIC_WITNESS | deny | deny, state unchanged |
| fixture-admin / separately provisioned admin role | PUBLIC_WITNESS | PRIVATE_WITNESS | create/read/delete disposable workspace |
| Outsider with misleading response roles | PUBLIC_WITNESS | deny | deny, state unchanged |
| Missing/empty/blank/non-string principal; malformed/failing verifier | anonymous policy only | deny after fresh verification | no privilege |

Success requires actual response content and expected state; an arbitrary 500,
redirect, login form, missing endpoint or empty image is failure. GeoServer can
express denial as 401/403/non-disclosing 404; each protected route has an authorized
positive control. Routes include /wfs, /ows, workspace WFS/OWS, POST form requests
and REST extensionless/XML/JSON collection and item forms. GeoFence is retained
and explicit disposable rules are provisioned through real administrator REST.

The real configured XML user/group/role service owns fixture role assignments.
Identity response roles are never the fixture's authority. An external Spring
fixture context shortens the actual inherited authentication cache's nonzero TTL
for a bounded expiry check. Fresh tokens separate verifier rejection from cache
behavior. Immediate cached authorization, if observed, is recorded, not labeled
immediate revocation. Repeated requests reuse HTTP connections and servlet workers.
The legacy candidate created cookies and failed identity-carryover checks. The
explicit `statelessBearerAuthentication` opt-in must create no session and must
ignore browser identity/cookie cache keys. Native tests with the actual Spring
persistence wrapper cover existing browser sessions and early response commits.
Browser login/logout and SSO acceptance remain outside this service fixture.

Each attempt is retained separately. The exact WAR is passed to retained Jetty
10.0.25 with an external synthetic data directory and task-owned loopback listener.
No production/bootstrap directory is activated. Existing seccomp loopback parent
and exec-child proof runs before the application, and fails the receipt if proof,
runtime checks, integrity or cleanup fail. This trusted fixture control does not
isolate host files/processes or other loopback services. Fixture tokens, Basic
credentials and response markers are checked in memory; persisted diagnostics
redact their values. A positive actual OAuth logger marker controls log capture.

Packaging with tests skipped remains packaging evidence. Repaired development
candidate configured tests precede a fresh final aggregate package and replay.
Full source, security/license, browser, rendering, publishing, FND-07/FND-08,
P1/P6 and release acceptance remain separate.

## Reproduction

Use the retained host toolchain and a new output path for each attempt. The
runtime is assembled from `runtime-inputs.json`: ten exact artifacts, each with
retained binary/source/POM custody; no acquisition occurs. The inherited Maven
profiles remain `importer,oauth2-geonode,geofence-server,geofence-server-postgres,printing,postgis`.

From the platform worktree, on the verified host (this environment uses
`flatpak-spawn --host /usr/bin/python3` in place of `python3`):

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
python3 build-support/java/compatibility.py \
  --audit-custody "$TASK_ROOT/source-archives/java-audit" \
  --custody "$TASK_ROOT/source-archives/java-http-auth/maven" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --tools "$TASK_ROOT/build-worktrees/java-resolution/toolchain" \
  --output "$TASK_ROOT/build-worktrees/geoserver-auth/new-aggregate" \
  --target webapp --stage package --tests compile-only \
  --repair xmlcodegen-emf --oauth-redaction --oauth-principal \
  --configured-auth-diagnostics --configured-auth-stateless
python3 build-support/java/configured_auth_probe.py \
  --build "$TASK_ROOT/build-worktrees/geoserver-auth/new-aggregate" \
  --custody "$TASK_ROOT/source-archives/java-http-auth/maven" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --java-home "$TASK_ROOT/build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1" \
  --output "$TASK_ROOT/build-worktrees/geoserver-auth/new-runtime" --stateless
```

The affected native target is
`oauth`, with `--runtime-http --configured-auth-diagnostic-tests
--configured-auth-stateless-tests --tests target`; native injection is forbidden
for aggregate packaging. Aggregate evidence and combined logging have independent
commands/results; see the handoff's retained final invocation records.

The disposable GeoFence database uses verified owned PostgreSQL/PostGIS binaries
from `postgis-slice/run-003`, with a new authenticated loopback-only cluster. Native
backends require `setsid`, denied by the unchanged supervisor; the database runs
outside it. Application and synthetic identity requests stay under the supervisor.
This explicit limitation is not hostile-code or complete host/egress isolation.
Runtime cleanup stops task-owned processes and scrubs fixture credentials; scrubbed
configuration hashes differ from the retained pre-execution hashes by design.
