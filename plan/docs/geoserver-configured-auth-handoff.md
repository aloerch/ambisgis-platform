# FND-02 configured GeoServer authorization handoff

Repository `aloerch/ambisgis-platform`; branch `fnd-02/geoserver-configured-auth`;
worktree `/home/revelberry/Projects/AmbisGIS/ambisgis-platform-geoserver-auth`.
Parent issue [FND-02 #3](https://github.com/aloerch/ambisgis-platform/issues/3)
remains **In progress**. This slice starts from the verified owner merge of
[PR #58](https://github.com/aloerch/ambisgis-platform/pull/58),
`b68e3d59bafb4bbf7b2007c76e5e59a25b4139e7`; reviewed source
`c2d7f10a11c001cccb8679af71a94128265816ab` is its ancestor. The prior branch,
worktrees and retained archives remain intact. New PR publication is recorded
below after creation; no merge or release is authorized.

## Frozen implementation and actual results

Final tested implementation: `38ef3560a42af230fe75e20cc02578b12d8fcd2f`;
`build-support/java` tree `da58e1ee80e151fe1494acded0b6b3f9a85a32c0`.
Subsequent edits are documentation/evidence only. The compact
[evidence index](../verification/geoserver-auth/evidence.json) binds retained
receipts, native suites, patch inputs/outputs, executed tooling and runtime artifacts.
Large immutable exports are referenced by exact path/hash, not recopied into Git.

| Fresh verification | Observed result |
|---|---|
| Final affected native security/OAuth suite | 708 JUnit cases: **707 passed**, one inherited `AuthenticationFilterTest.testSSL` skip; zero failures/errors. Includes six diagnostic and fourteen stateless regressions, all passed without skips. |
| Exact aggregate HTTP and restart | **177 actual HTTP requests passed**, plus one non-request session-policy assertion (178 records total). Initial run: 172 requests + assertion; restart: five requests. |
| Full-profile fresh aggregate | 156-module packaging succeeded; **tests explicitly skipped**. |
| Full aggregate logging | Seven logger/bridge emissions, each exactly once. |
| Current Java tooling | **366 tests passed**, no failures/errors/skips. |
| Required plan checks | **176 tests passed**, no failures/errors/skips; four strict JSON schema/example checks passed. |

Final WAR SHA-256:
`8a79a2cf7647be2f28591d7f04f975dc84cb00baaaea35cb3d5f2f293ea8f39f`.
It contains 368 libraries, 405 WAR files, 83,374 JAR entries and 77,900 class
entries representing 77,691 names. All six repaired bytecode definitions match
compiler outputs, including the new transient security context. The inventory
retains 144 duplicate names (141 byte-identical; three differing inherited names:
`module-info.class`, `META-INF/versions/9/module-info.class`,
`javax/annotation/Resource$AuthenticationType.class`). No security class duplicates
were found; this is not a globally duplicate-free distribution.

Packaging preserved all six profiles: `importer,oauth2-geonode,geofence-server,
geofence-server-postgres,printing,postgis`. Ordered guarded repairs include the
existing EMF, aggregate lifecycle/logging repairs, #58 OAuth diagnostics/principal
repairs, configured cache/filter diagnostics, and the new explicit stateless mode.
Original archives remain immutable. The development configured run passed before
the final fresh aggregate; final native and exact-WAR runs also cover the later
response-commit correction.

## What the configured application proves

The fixture uses real GeoServer servlet/security chains, token services, XML
user/group/role services, Shapefile catalog resources and GeoFence PostgreSQL
policy. Its synthetic endpoint implements the selected GeoNode opaque-token
protocol: form POST token, Basic client credentials, `client_id`, `issued_to`,
`expires_in`, invalid/expired 403. It is not actual GeoNode server acceptance.

The [pretest matrix and recipe](../../build-support/java/configured-auth.md) cover
intentional public WFS reads, protected point geometry/content, anonymous/reader/
outsider/admin identities, malformed or failing fresh verification, disabled/
unknown/root users, misleading response roles, WFS root/workspace GET/POST routes,
and REST extensionless/XML/JSON create/delete plus authorized state readbacks.
Denied creates/deletes leave disposable resources unchanged. Reader and outsider
permissions come from the real local role service. Native GeoFence MIXED/EXCLUDE
policy produces real denials; a proxy does not manufacture status codes.

Thirty-two sequential requests reuse servlet workers and a persistent HTTP
connection; thirty-two concurrent requests mix identities. Passive request records
prove the same workers return both allowed and denied results. Global verification
counter deltas are exact for isolated sequential cases; concurrent row windows
overlap and are not per-request attribution. Safe `/rest/imports` and `/pdf/info.json`
smokes prove bounded initialization only, not full importer/rendering acceptance.

The explicit `statelessBearerAuthentication` option defaults to false. In opted-in
service chains it isolates bearer identity, bypasses the session-scoped OAuth
template, requires a provisioned enabled user for the configured UserGroupService,
and restores the surrounding browser context. A supported native Spring
`@Transient` request context prevents early response commits from persisting or
removing browser state. Existing browser-session cases use the actual native
persistence wrapper; browser SSO/login/logout remain outside this fixture.

The real nonzero cache was exercised: prime 200 with verification, immediate
cached 200 after verifier-side revocation without verification, then 403 after
expiry with fresh verification. **Immediate revocation is not guaranteed.**
All HTTP response headers, including duplicates, are scanned; every stateless
response must emit no cookie. Logs/response/exception diagnostics showed zero
fixture-secret leaks, with each OAuth and cache positive logger control observed
once in each startup. No secret values are retained in evidence.

## Runtime, retained failures and limits

Jetty 10.0.25, Servlet 4 API and SLF4J API comprise ten newly selected runtime
artifacts, already retained with binary/source/POM/notices. No network acquisition
occurred. The launcher stages a byte-identical WAR in its own directory, verifies
real application library/class origins against original WAR entries, then starts
and restarts that exact artifact with the same disposable configuration/database.
It never substitutes Maven's adjacent exploded directory. Active REST/default
filter-chain order, real role-service/config class and loaded origins are retained
in each runtime `ready.json` and result receipt. Random configuration credentials
are scrubbed after shutdown; pre-run file hashes are retained rather than falsely
claiming the scrubbed bytes are identical.

The unchanged loopback supervisor passed 79 parent and 79 executed-child probes
for both final native and final application runs, with zero UDP packets and stopped
task-owned process groups. It controls inspected trusted fixtures, not hostile
code, filesystem/process access or other existing loopback services. The owned
PostgreSQL 15.19/PostGIS 3.5.7 fixture runs **outside** that supervisor: a retained
attempt proved PostgreSQL backend `setsid` is denied. Its new task-owned cluster
uses SCRAM, 127.0.0.1-only TCP, no Unix listener, verified owned artifacts and
explicit shutdown. The application and synthetic identity endpoint stay supervised.
This additional host/egress limitation requires review; no supervisor restriction
was relaxed. No production/default bootstrap credentials or managed branch tables
are used.

Retained failures are part of the evidence: missing prerequisite/build flag;
initial H2 geometry setup; unsupported REST method configuration; detected adjacent
exploded-WAR reuse; initially missing logger capture; GeoFence HIDE producing WFS
errors; real legacy cookie identity carryover and DEBUG credential exposure; and
two early-response persistence failures against the first stateless candidate.
The six final standalone diagnostic regressions fail on unrepaired classes and
pass after repair. Two real Spring response-commit regressions fail before the
transient guard and pass after it. Failed attempts retain failed receipts; source,
network, assertion, capture, integrity, scrub or cleanup errors cannot turn into a
success because Maven returned zero. Review records explain each material fix.

Source dispositions remain **48 structurally accounted / 12 unresolved / four
partial**. Runtime publisher sources/notices are retained inputs, not independently
rebuilt source correspondence or legal approval. Shaded-source, schema-rights,
host/toolchain, license/brand, release signing and security/deployment gates remain.
FND-07/FND-08 and P1/P6 are separate. This package remains a plan and bounded
engineering candidate, not an accepted GIS distribution or canonical product policy.

XML/MapFish native suites were not repeated: their sources/profiles/repairs were
unchanged; the new servlet printing-info smoke and aggregate logging were run.
Prior database/Jupyter suites are historical, not fresh results here. No full
rendering, browser SSO, publishing saga, restore or product-authorization acceptance
is claimed.

## Evidence and exact resumption

Retained root: `/home/revelberry/Projects/AmbisGIS/build-worktrees/geoserver-auth`.
Final directories: `oauth-configured-final-02`, `aggregate-03`,
`aggregate-03-inventory`, `aggregate-03-logging`, `configured-final-02`,
`validation-final-03` (Java), and `validation-final-02` (plan/schema).
The first final-validation host-path check failed before tests: the existing
`/tmp/ambisgis-validation-venv` is in the agent environment, not host `/tmp`.
Actual plan validation used its verified Python 3.13.15/jsonschema 4.26.0.
Native/runtime commands used host Python 3.13.14 and retained Temurin17/Maven3.9.16.

Use the exact recipe linked above and new output directories. Native replay uses
`compatibility.py --target oauth --tests target --stage package --runtime-http` with
`--repair xmlcodegen-emf --oauth-redaction --oauth-principal
--configured-auth-diagnostics --configured-auth-stateless
--configured-auth-diagnostic-tests --configured-auth-stateless-tests`; aggregate replay
uses `--target webapp --tests compile-only --stage package` without test injection.
The actual result receipts retain full Maven commands and network wrappers.
Inventory and logging replay, after assigning `TASK_ROOT` as in the recipe:

```sh
python3 build-support/java/aggregate_evidence.py \
  --build "$TASK_ROOT/build-worktrees/geoserver-auth/new-aggregate" \
  --output "$TASK_ROOT/build-worktrees/geoserver-auth/new-inventory"
python3 build-support/java/combined_logging_probe.py \
  --build "$TASK_ROOT/build-worktrees/geoserver-auth/new-aggregate" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --tools "$TASK_ROOT/build-worktrees/java-resolution/toolchain" \
  --output "$TASK_ROOT/build-worktrees/geoserver-auth/new-logging"
```

Use the same host Python invocation for these commands. Their final receipts
preserve executed commands/manifests. Run plan checks from `plan` using the verified validation venv:

```sh
/tmp/ambisgis-validation-venv/bin/python3 -m unittest discover -s tests -v
/tmp/ambisgis-validation-venv/bin/python3 tools/validate_package.py --require-schemas
```

Next bounded engineering action: continue FND-02 Java tuple evidence against a
retained, source-owned GeoNode identity service and document native token/session
integration behavior, while preserving these configured-WAR regressions. Re-read
live issue #3/dependencies and current main first; use a new branch from the
accepted checkpoint, or continue independent unblocked source-custody work while
this PR awaits review. Actual GeoNode/browser integration and unified AmbisGIS
policy need their own acceptance. Do not promote Delivery or infer approval from
this passing fixture.

## Owner review

Fresh human review is required before merging the new security-sensitive PR.
Inspect diagnostic redaction, default-false bearer mode, configured role policy,
cache behavior, transient context/session preservation and explicit PostgreSQL
supervisor limitation in [ADR 006](../adrs/006-configured-geoserver-authorization.md).
Acceptance covers this bounded inherited-component engineering checkpoint only;
it does not approve release, production deployment or complete product security.
This review gates merging, not already-authorized engineering work.
