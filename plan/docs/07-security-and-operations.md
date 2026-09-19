# 07 — Installation, security and operations

## 1. Deployment profiles

**Developer:** loopback-bound services, synthetic fixtures, fast reload, isolated disposable databases and a clearly marked single-user notebook profile. No development default password may survive into a remotely reachable deployment.

**Single-node organizational installation:** Linux host, a tested Compose runtime, persistent volumes, TLS, one organization, generated identities/configuration, private internal network, product-managed backups and a secure optional notebook profile. This is the initial supported production topology after hardening gates. Windows developers use an explicitly tested Linux development environment/VM or WSL path; native Windows production server installation is not initially promised.

**Air-gapped organizational installation:** signed/exported images, dependency and source bundles, transformation grids/fonts, offline docs, verified checksums and an update process. No unexpected package/model/telemetry/basemap downloads at first use. It is a tested profile, not merely a statement that Docker works offline.

**High-availability/multi-node:** future Helm/operator/spawner profile after state placement and recovery are proven. One database, worker queue, shared storage and singleton configuration writer remain potential failure domains until their own HA plans are tested. Restart policies do not constitute high availability.

For reproducible initial benchmark planning, use a recorded 8-vCPU/32-GiB Linux test host with SSD storage, plus explicit notebook quotas. This is a proposed test fixture, **not a validated minimum or production sizing recommendation**. Measure actual component RAM, raster workload, branch snapshot amplification, tile cache and concurrent notebooks before publishing sizing guidance.

## 2. Installer product

The planned CLI commands are `ambisgis init`, `ambisgis up`, `ambisgis status`, `ambisgis doctor`, `ambisgis backup`, `ambisgis restore` and `ambisgis upgrade`. These commands are **requirements to implement**, not tools included in this design package. The only implemented repository command in the package is `tools/bootstrap_repositories.py`.

`init` collects deployment hostname, external HTTPS/proxy mode, storage root, admin identity enrollment and optional notebook domain. Generate internal service credentials, database roles, OIDC clients/callbacks, trusted proxy configuration, GeoNode-to-GeoServer integration, renderer settings and catalog/policy adapters. Use templates under version control; store secrets in restricted runtime files or a supported secrets service, never commit them.

A preflight checks ports, disk, file ownership, hostnames, DNS/TLS, clock, supported architecture/runtime, database extensions, available image digests and notebook isolation prerequisites. The diagnostic output gives remediation steps without printing secrets. Require only decisions a GIS administrator understands; automatically supply safe defaults for internal URLs and advanced engine settings.

A first-run wizard validates setup with a private synthetic layer, a map request, a feature query, a metadata update and a deny-access test from a second account. Success means a useful workflow works, not merely that all containers are green.

## 3. Authorization enforcement

Use an OIDC authentication provider and catalog-owned authorization policy. Authentication identifies a principal; it does not grant every dataset operation. Policies distinguish metadata discovery, feature reads, raster source download, publication, data editing, branch management, post, schema changes, notebook execution and infrastructure administration.

The public gateway resolves item/data/branch/operation policy before dispatch. A private request fails closed on unavailable policy. Policy caching uses explicit revision IDs, bounded lifetimes, invalidation events and strict handling of revocation. Engine ACL projections are defense in depth; asynchronous propagation must never be the sole gate protecting data.

The gateway strips untrusted identity/role/internal headers, validates forwarded-host/proto only from configured proxies, and uses scoped service-to-service authentication internally. GeoServer REST/admin, QGIS raw project access, databases, worker broker and identity admin ports are not publicly reachable. Do not protect them only by an obscure path.

All output paths are covered: feature query/count/extent/statistics, map/legend/identify, tiles, print/export, source/attachment downloads, metadata thumbnails, search facets, cached apps, notebook outputs and job logs. V1 can disable unsupported row-filtered rendering/tiling rather than expose it insecurely. A public service is deliberately anonymous-read where policy says so; blanket authentication is not a substitute for correct policy.

## 4. Data-plane security

Queries use an allow-listed typed filter grammar, parameterized SQL and validated schema references. Reject raw SQL, arbitrary engine parameters and arbitrary filesystem paths. Use row/field policy before any aggregation. Bound expression nesting, feature count, geometry vertices, output bytes, map dimensions, time ranges, CPU/time and connection concurrency.

Database roles are least-privilege: catalog application, geodatabase service writer, rendering reader, schema migrator, backup role and optional analyst reader. Normal application roles are not table owners and do not have `BYPASSRLS`. Set transaction-local authorization context safely and test connection-pool reuse. No notebook or desktop user receives the writer/migrator password.

Remote-source registration requires administrator approval, network allowlists, TLS validation and source-specific credentials. Defend against SSRF through redirects, DNS rebinding, private/metadata IP ranges and arbitrary GDAL/QGIS virtual filesystems. Apply checks at every resolved destination; an initial URL string check is insufficient. Restrict external SLD graphic URLs and remote fonts as well as data URLs.

Uploads are staged outside executable web roots. Validate true file type, compression ratio, path traversal, symlinks, uncompressed size, nested archives, raster dimensions and parser resource budgets. Run geospatial parsing in a constrained worker with no privileged credentials. Large/malformed vector geometries and rasters can exhaust memory even when the upload file is small.

## 5. Browser/application security

Use authorization-code with PKCE for browser/desktop public clients or a supported device flow; avoid collecting the user's OIDC password in the QGIS plugin. Validate issuer, audience, expiry, nonce/state and redirect URIs. Store refresh tokens in supported OS credential storage or a secure server session, not project files. [S34]

Use secure/HttpOnly/SameSite cookies as appropriate, CSRF protection for cookie-authenticated mutations, a narrow CORS policy, strict content security policy and sanitized rich text. No wildcard credentialed CORS. Never place bearer tokens in service URLs or logs. Protect logout/revocation and permission changes consistently.

Notebook user code runs on isolated user domains and containers as defined in the notebook specification. Untrusted HTML previews and notebook outputs must not execute with portal-origin privileges. Administrator-installed widgets remain trusted code requiring review; ordinary app users cannot upload arbitrary executable bundles.

## 6. Threat model and mandatory abuse tests

| Threat | Required control / test |
|---|---|
| User guesses private item, branch or staging ID | Deny every metadata/data/job/download path; no existence/count leak beyond chosen policy. |
| GeoServer service bypass | Private network + service auth + approved projections; direct raw URL attempt fails. |
| Tile-cache cross-user leak | Policy-scoped cache or private no-store; revoked/new principal cannot fetch another scope's tile. |
| SQL/expression injection | AST validation and bound parameters; fuzz filter parser and sort/field identifiers. |
| Upload/parser exploit or resource bomb | Sandbox, limits, no sensitive mounts/network, timeouts and malformed-file tests. |
| Notebook privilege escalation | No socket/admin credentials; origin/network/filesystem isolation and resource tests. |
| Duplicate/replayed edit or publish | Idempotency payload hash, scope binding, audit and no duplicated effects. |
| Stale post or malicious resolution | Expected-head/approval checks, reauthorization and transactional constraint validation. |
| Secret exposure in public forks | Synthetic data only; secret scanning, sanitized fixtures, audit before push. |
| Dependency/AI-generated supply-chain defect | Pinned sources, reviewed updates, SBOM/signing, tests and no blind install scripts. |
| Operator deletes a live blob/snapshot | Reference-aware retention, dry-run collection, backup and restore tests. |

Create a data-flow threat model per deployment profile before beta. Security tests run through public entry points and direct internal attempts where relevant; mocked permission functions alone are insufficient.

## 7. Backup and recovery

A recovery set includes catalog and geodatabase backups with a documented consistency boundary, immutable asset manifests/content, GeoServer/QGIS published configuration revisions, notebook durable storage, identity configuration/state as required, migration/version lock, and a secure recovery procedure for encryption/signing secrets. A source-controlled YAML file is not a complete backup.

For an initial single-node profile, briefly pause mutating APIs/jobs during a coordinated backup checkpoint, capture committed heads/manifests, then take database/storage backups under the documented procedure. Later continuous/PITR recovery can replace the pause only after cross-store consistency is demonstrated. Assets are immutable, so manifests identify which hashes must be available; asynchronous unreferenced staging assets need not be included.

Restore into an isolated environment first. Validate hashes, schema/version compatibility, identities/permissions, branch histories, active service revisions and blob references. Rebuild disposable caches/search projections. Exercise query/edit/reconcile/post, map/tile serving and notebook launch. A green PostgreSQL restore log is not proof of GIS recovery.

Set recovery objectives only after measurement. Proposed pilot targets are recovery point at the last coordinated checkpoint and recovery time within a measured maintenance window; do not advertise an untested SLA. Document what happens to jobs that were running at backup: recover from durable steps and idempotency records, not queue memory.

## 8. Upgrades, rollbacks and upstream patches

The distribution lock identifies every upstream commit/release, image digest, extension version, language/runtime, database extension, schema migration and frontend package graph. GeoServer extensions must match its selected build. GeoNode/MapStore/geonode-mapstore-client must be tested as a tuple. Upstream main branches and floating `latest` image tags are not production dependencies.

Upgrade flow: preflight, backup/checkpoint, compatibility analyzer, migrate a restored staging copy, run release contract suite, enter maintenance as needed, apply ordered migrations, deploy pinned revisions, run smoke/deny tests, reopen writes. Keep expand/contract migrations separate where possible. Never claim an image rollback reverses an irreversible schema migration; use a forward fix or restore according to the documented plan.

Monitor vulnerability disclosures and external fixes as advisory inputs. AmbisGIS may cherry-pick, independently backport, implement a different correction, or replace a component; full upstream merges/rebases and upstream approval are never mandatory. Every correction needs a regression test, dependency review and signed product release. Refactors are evaluated for maintainability and product benefit rather than line-count minimization. A release with no supportable security correction path fails the gate. Operate the source-retention, offline rebuild and independent patch drills in chapter 11.

## 9. Observability and support

Correlate browser/desktop actions, API calls, job steps, engine requests and database commits with trace IDs. Monitor liveness separately from readiness and dependency health to avoid restart cascades. Track queue age, worker leases, database lock time, edit conflicts, post duration, raster/tiles CPU/storage, auth failures, error budgets and notebook resource use.

Expose user-oriented diagnostics: “source credentials expired,” “required font missing,” “target branch changed,” “metadata sync delayed,” and “tile job paused at quota.” The support bundle redacts tokens, passwords, private connection strings and sensitive query payloads. Audit events are append-only to ordinary roles; database administrators can still tamper with a database unless a separately secured external audit sink/signing design is deployed. Do not overclaim tamper-proofing.

## 10. Operational acceptance

A clean host installs through one supported procedure; a second run is idempotent. The product diagnoses missing TLS/DNS or source credentials. Host restart recovers services without losing jobs/data. A killed publish worker resumes safely. Permission revocation stops new private reads across all protocols. Backup restores a working branch and notebook. The supported upgrade path succeeds against retained fixtures. No upstream admin port or notebook runtime socket is publicly exposed.
