# FND-02 source-owned GeoNode identity fixture

This directory acquires and restores the selected GeoNode backend, runs its full
Django application and migrations against the retained PostgreSQL/PostGIS build,
and exercises the unchanged GeoServer OAuth consumer over real loopback HTTP.
It is a bounded engineering fixture. Product release, general browser SSO,
frontend builds and consolidated authorization policy remain outside its acceptance.

The controlling findings and run outcomes are in
[the handoff](../../plan/docs/geonode-identity-handoff.md). The compact dependency
record is [dependencies.json](../../plan/verification/geonode-identity/dependencies.json).
Full inventories, source archives, downloaded artifacts and logs remain in the
local custody and attempt directories identified below; private fixture files
must not be copied into Git or published.

## Authoritative membership continuation

The strict role candidate is implemented by `roles_repair.py`, rebuilt with
`build.py --strict-verifier --strict-roles`, and exercised by the same real
issuance journey with `run.py --integration --strict-verifier --strict-roles
--build <fresh-aggregate> --war-sha256 <verified-digest>`.
The explicit build/digest are required for this candidate. See the
[declared matrix](role-matrix.md), [ADR 008](../../plan/adrs/008-authoritative-geonode-role-service.md)
and [handoff](../../plan/docs/geonode-role-propagation-handoff.md).

Its role-service ApiKey belongs to a dedicated active read-only service identity
and is separate from tokeninfo client credentials. Local GeoServer user records
are identity-only; XML role grants are empty. Group changes use the native
GeoNode ORM and authenticated actual role HTTP, then real packaged GeoServer and
GeoFence enforcement. The historical comparison below remains reproducible
without `--strict-roles`. It does not establish this new candidate's result.

## Source and dependency custody

The owned GeoNode repository is `aloerch/ambisgis-geonode`, ID `1376927978`,
at `a1db97e81dfc26c16bb4ee1a5d2b408877af66c9` (candidate tag `5.1.0`, package
version `5.1.0.post1`). The owned MapStore client repository is
`aloerch/ambisgis-mapstore-client`, ID `1376928013`, at
`7ca4822125b67999c97cb4aa1faa84b8a28eee9b` (package `5.1.0`). Acquisition uses
`git archive` of those exact commits after checking owned remotes. It does not
use the current donor branch or a publisher package as backend source authority.

`source-archives/geonode-identity-v2` is the immutable corrected custody set.
It contains 211 installation wheels, 199 published third-party source archives,
552 extracted notice/license/metadata files, exact owned source archives,
release metadata and a manifest covering 1,391 files. Of the 211 installed
distributions, two are built from owned source and 209 are third-party inventory
entries. Ten third-party releases have no sdist in the retained release metadata:

| Distribution | Version |
| --- | --- |
| geonode-announcements | 2.0.2.2 |
| geonode-django-dynamic-model | 0.4.0 |
| geonode-dynamic-rest | 2.3.0.2 |
| geonode-oauth-toolkit | 2.2.3.1 |
| geonode-pinax-notifications | 6.0.0.4 |
| geonode-pycsw | 3.0.0b1 |
| geoserver-restconfig | 2.0.16 |
| gn-arcrest | 10.5.6 |
| gn-gsimporter | 2.0.4 |
| ua-parser-builtins | 202606 |

Python files within retained wheels do not establish complete corresponding
source or build provenance. Third-party wheels are restored from custody; a
complete third-party source rebuild has not been demonstrated. License
metadata and notices are evidence for human review, not license approval.

The original custody and run attempts remain retained. Native startup with the
initial wheel preference selected `django-tastypie==0.14.0`, whose removed
Django API import failed. Corrected custody explicitly resolves `0.14.7`, within
the candidate's `<0.15.0` constraint, and retains that published source. It does
not overwrite the failed acquisition or conceal the resolution change.

## Headless compatibility profile

The guarded `pyproject.toml` transformation records before/after hashes and:

- Changes `GDAL==3.8.4` to `GDAL==3.10.3` to match the retained source-built native
  GDAL. This remains a compatibility candidate, not an accepted product pin.
- Omits `pylibmc==1.6.3` for the explicitly configured local-memory cache.
- Omits `uWSGI==2.0.30` for the disposable loopback Python WSGI process.

The retained native prefix is
`build-worktrees/postgis-slice/run-003/prefix`. The fixture reuses owned
PostgreSQL 15.19, PostGIS 3.5.7 and GDAL 3.10.3. Python GDAL and psycopg2 bindings
were compiled with retained source inputs against this prefix. CPython 3.12.14
source was retained to configure missing extension headers, but the host
interpreter and compiler are prerequisites rather than rebuilt toolchain outputs.
Native dependencies are not all rebuilt by this Python slice.

`--strict-verifier` applies the opt-in repair from `verifier_repair.py` to a fresh
source restoration before building the owned wheel. Exact baseline hashes and
the complete source file set are checked before and after the five-file change.
The recipe hash and all before/after file hashes are recorded in the build
receipt. The source setting `OAUTH2_BACKEND_TOKENINFO_STRICT` defaults to false;
the strict fixture enables it explicitly. The repair checks the real native
OAuth application binding, token expiry and active owner, and returns the native
scope value to the consumer. It does not establish a consolidated scope policy. Its narrow middleware
exception applies only to the resolved strict tokeninfo view. The native test
suite also exercises unrelated middleware behavior. See
[ADR 007](../../plan/adrs/007-geonode-backend-token-verification.md) for the
contract and review boundary.

## Recorded commands

These commands were executed from this worktree. Acquisition, build and runner
outputs must be fresh directories. Repeating a recorded command against an
existing output fails intentionally; use new names for another attempt and
preserve the original receipts.

```sh
ambisgis_base=/home/revelberry/Projects/AmbisGIS
ambisgis_slice="$ambisgis_base/ambisgis-platform-geonode-identity/build-support/geonode"
ambisgis_native="$ambisgis_base/build-worktrees/postgis-slice/run-003/prefix"

flatpak-spawn --host python3.12 "$ambisgis_slice/acquire.py" \
  --base "$ambisgis_base" \
  --reuse-custody "$ambisgis_base/source-archives/geonode-identity" \
  --custody "$ambisgis_base/source-archives/geonode-identity-v2" \
  --work "$ambisgis_base/build-worktrees/geonode-identity/acquisition-v2" \
  --native-prefix "$ambisgis_native"

flatpak-spawn --host unshare --user --map-root-user --net python3.12 \
  "$ambisgis_slice/build.py" --strict-verifier \
  --custody "$ambisgis_base/source-archives/geonode-identity-v2" \
  --work "$ambisgis_base/build-worktrees/geonode-identity/run-004" \
  --native-prefix "$ambisgis_native"

flatpak-spawn --host /usr/bin/python3 "$ambisgis_slice/run.py" \
  --python "$ambisgis_base/build-worktrees/geonode-identity/run-004/venv/bin/python" \
  --output "$ambisgis_base/build-worktrees/geonode-identity/integration-repaired-01" \
  --integration --strict-verifier
```

The recorded runner parent uses host `/usr/bin/python3` (3.13.14); native
GeoNode commands use the explicitly supplied run-004 Python 3.12.14 venv.
Acquisition and backend wheel builds use host Python 3.12.

Acquisition is explicitly online and retains downloaded inputs. It is not the
reproduction step: a future fresh resolution may differ. `build.py` verifies the
existing complete custody manifest, restores dependencies with `--no-index`,
rebuilds exactly the two owned wheels and checks installed dependency metadata.
The executed run-004 build used a new network namespace without a configured
network interface, in addition to pip's offline controls. The result passed
`pip check` and native imports. This proves the recorded owned backend rebuild
and dependency-wheel restoration, not a full source/toolchain rebuild.

A separate fresh `run-005` rebuild records an explicit disconnected-namespace
proof in `build-worktrees/geonode-identity/offline-replay-005-attempt-02`.
The retained wrapper, invocation, pre/post recipe and custody hashes, network
proof and result bind the proof to the actual build subprocess. It observed a
different namespace, only DOWN loopback, no IPv4 routes and IPv6 rejection
routes, then actual denied IPv4/IPv6 connections before rebuilding. The replay
passed with unchanged recipe/input bytes, dependency checks and imports.
`run-004` remains the integration runtime; `run-005` is separate reproduction
evidence. The first proof-only attempt rejected unexpected route formatting and
an unavailable-address IPv6 result before invoking any build, and is preserved
under `offline-replay-005`.

The successful proof-wrapper command was:

```sh
flatpak-spawn --host python3.12 \
  /home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-identity/offline-replay-005-attempt-02/replay.py
```

Like the underlying build, this retained one-attempt wrapper refuses to reuse its
work directory. It is evidence of the recorded execution, not a reusable path
that should overwrite it.

The recorded first repaired integration attempt is retained even where its
harness expectations failed. Subsequent attempt paths and final results are
listed in the handoff; the command above is history, not a claim that attempt 01
passed. Attempt 02 completed all 176 GeoServer resource scenarios and its cache,
expiry, role-change, transport-fault and restart gates, but remained unsuccessful
because the logout response cookie classifier rejected one native cookie. The
failed attempt is preserved. Final attempt04 passes 176 resource
requests, 48 protocol assertions, all cache/restart/logging/worker-reuse gates and
cleanup. Attempt03's sequential worker-coverage miss is retained; round rotation
corrects that fixture schedule without weakening the observed reuse requirement.
Omitting `--integration` runs startup, real
migrations and native tests.
Omitting both strict flags reproduces the selected-source baseline profile.

## Runtime evidence and limits

The runner generates private configuration and credentials, records a tooling
snapshot, checks installed source origins and hashes, and uses an isolated
loopback-only service supervisor. PostgreSQL alone uses the documented #59
exception to that supervisor; its generated roles, database and cluster remain
disposable. The runner preserves network receipts, checks cleanup and verifies
the unchanged GeoServer WAR digest. Never run the integration command inside
the fully disconnected build namespace: the service run requires its own
recorded loopback policy and access to its isolated PostgreSQL instance.

The native Django application uses its full installed apps, URLs and migrations.
Real browser-form HTTP, CSRF, session cookies, PKCE grants and native token
models produce the identity inputs consumed by GeoServer. Explicit transport
faults delay or truncate a response only after the real native verifier produced
200; they are labelled fault injection and do not fabricate identities.

GeoServer XML users/roles are an explicit manual projection. The role-change
exercise measures native GeoNode membership removal and both cached and fresh
GeoServer behavior, including continued authorization from that independent XML
mapping. This is a consolidation limitation, not a claim of unified policy or
automatic role synchronization.

Selected protocol responses and GeoServer resource responses are checked for
known fixture secrets with exact permitted token/cookie channels. Intermediate
login and consent responses retain status, digest and safe metadata; they are
not all raw-response leak scanned. Native WARNING-and-above message logging
records separate counters for known fixture secrets, credential fields, private
key blocks and conservative opaque candidates. The first three fail the run;
opaque candidates are reported separately because they may be identifiers.
This is not an exhaustive DEBUG or arbitrary-unknown-secret audit.

Owned Python wheels include inherited committed static assets. There is no npm
source build, frontend dependency closure, general browser/accessibility test,
full portal acceptance or production deployment in this slice.

## Local harness checks

```sh
flatpak-spawn --host /usr/bin/python3 -m unittest discover \
  -s build-support/geonode -p 'test_*.py' -v

# In the agent environment (not the Flatpak host), from the worktree's plan directory:
cd plan
/tmp/ambisgis-validation-venv/bin/python -m unittest discover -s tests -v
/tmp/ambisgis-validation-venv/bin/python tools/validate_package.py --require-schemas
```

The first command checks fixture integrity, response classification and source
transformation guards. The latter two are plan-package checks. Actual GIS
acceptance requires the retained real runtime receipts; these unit tests do not
substitute for them.
