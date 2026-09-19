# 05 — Integrated spatial notebooks

JupyterHub and JupyterLab are AmbisGIS-owned source forks built for the product. The notebook environment dependency graph, native spatial libraries and spawn/auth adapters are retained and controlled as part of the product release. Source ownership does not weaken runtime isolation. Upstream-only notebook images or automatic notebook extension updates do not satisfy the supported release contract.

## 1. Product contract

Use JupyterHub for user-server lifecycle and JupyterLab for editing. Build a curated spatial image and AmbisGIS SDK so a user can open a portal notebook, access authorized data, run analysis and publish outputs without copying portal URLs/tokens into cells. Jupyter alone does not provide the desired catalog, administration, permission, environment, and publishing integration. [S18–S19]

A notebook is a catalog item with owner, sharing, source file revision, environment image digest, parameters schema where applicable, input/output references and run history. Sharing the notebook source or a rendered result does not grant access to every input dataset. The editor launches through SSO and presents a product extension with catalog search, dataset insertion, environment information and publication status.

## 2. Security boundary

Treat notebook code as arbitrary code execution by a user, not trusted server configuration. Each user server runs in an isolated container/pod with its own persistent home/workspace, quotas, non-root identity, restricted capabilities, no host mounts beyond its assigned storage, no Docker socket, no database-admin credentials, and no cluster-admin or automatically mounted Kubernetes service-account token.

Use per-user hostnames and an isolated notebook domain/cookie boundary. Do not serve arbitrary notebook HTML/JavaScript on the portal's origin. JupyterHub documents that robust browser isolation needs per-user domains; a path prefix alone is not equivalent. [S18] Local single-user development may use a clearly marked simplified profile bound to loopback; it must never be marketed as a secure multi-user deployment.

Enforce network policy so kernels cannot reach GeoServer administration, identity administration, infrastructure metadata endpoints, control-plane databases or other users' servers. Permit only required API gateway, approved package/data destinations and user-specific storage access. Restrict arbitrary outbound access in sensitive deployments. Runtime sandboxing/containers are not a proof against every kernel exploit; patch base images and support a stronger VM/pod isolation profile where trust demands it.

Resource controls include CPU/memory/process limits, storage quota, maximum concurrent servers/jobs, idle culling, long-job policy and administrator termination. A crashed or memory-exhausted notebook cannot take down the GIS gateway. Kernel processes may install allowed user packages, but the notebook server environment and hub image remain immutable and separately maintained.

## 3. Environments and package strategy

Resolve a compatible core environment from a consistent binary package channel/build strategy, then lock exact packages and hashes. Do not freely mix binary GDAL/PROJ/GEOS installations from operating-system packages, pip and conda in the same environment. Build images in CI and test actual imports, coordinate transformations and file round trips. [S19, S27]

Proposed profiles:

| Profile | Intended packages / functions | Boundary |
|---|---|---|
| Core spatial Python | JupyterLab, ipykernel, numpy, pandas, scipy, matplotlib, geopandas, shapely, pyproj, pyogrio/GDAL, rasterio, psycopg, SQLAlchemy, HTTP client, AmbisGIS SDK | Default for vector analysis and common raster reads; versions selected by lock task. |
| Raster/array | Core plus xarray, rioxarray, dask, netCDF/Zarr support, pystac-client and selected raster tooling | Opt-in heavier image; validate codecs, chunking and storage permissions. |
| PyQGIS processing | QGIS-compatible Python/Qt/GDAL runtime with tested processing providers | Separate image; do not force incompatible PyQGIS ABI into the default environment. |
| Advanced optional | Selected spatial statistics, machine-learning or specialized packages | Package request/catalog process; no blanket “all spatial packages” claim. |

Package availability does not imply ArcPy compatibility. QGIS processing and other packages are different APIs and algorithms; migration requires task-level tests. GDAL driver availability/license restrictions must be inventoried. Fonts, CRS databases and required transformation grids are packaged reproducibly for offline deployments.

Every run records the image digest, package lock ID, AmbisGIS SDK version, input item/revision IDs, declared parameters and execution timestamps. Scientific results are reproducible only within clearly stated data and environment assumptions.

## 4. Authentication and SDK

The hub authenticates through OIDC and maps the stable subject to the catalog user. The user runtime obtains short-lived, audience-restricted access through an approved runtime credential broker or delegated OAuth flow. Store runtime credentials outside notebook files/outputs and avoid environment variables in support dumps. Refresh/revocation cannot silently widen scopes.

Default scope is the user's current permission set constrained by the operation; jobs can use narrower tokens. A notebook never receives a superuser service account because it is “inside the network.” Access revocation is enforced by the gateway on new requests even if a kernel still holds a token whose cryptographic expiry has not passed.

The planned SDK exposes catalog search, item metadata, feature iteration/GeoDataFrame conversion, raster access, uploads, publication jobs, branch CRUD/reconcile/post, and application/notebook item management. Generated low-level clients derive from OpenAPI; ergonomic wrappers add pagination, progress and typed errors without bypassing policy.

Proposed usage, **not currently implemented executable API**:

```python
from ambisgis import Client

client = Client.from_runtime()
layer = client.layers.get("<authorized-layer-uuid>")
frame = layer.query(where={"op": "eq", "field": "status", "value": "open"}).to_geodataframe()
result = frame.to_crs(layer.crs).copy()
job = client.publish.geodataframe(result, title="Open features", sharing="private")
job.wait()  # Bounded timeout/cancellation is required in the implementation.
```

Database access through psycopg is not the default managed-data edit path. Offer read-only approved connections or per-user analytical scratch databases as a separate capability. All managed branch edits use the feature API. A QGIS processing result is uploaded/published through the same job API as a desktop publication.

## 5. Notebook item and file lifecycle

Separate editable source from executed artifacts. Opening a shared notebook creates a user copy or a read-only view unless the user has edit permission. Concurrent saves use file/item revisions and conflict detection. Executed outputs may contain sensitive rows, images or tokens, so store them privately by default and require an explicit share step.

Notebook downloads preserve `.ipynb` structure. Rendered HTML is sanitized or hosted on an isolated origin; source code is never executed during a thumbnail or preview request. Do not trust embedded notebook metadata as an authorization grant. Output size limits and artifact scanning prevent storage exhaustion.

Durable user files live outside ephemeral containers. Backups include user homes or notebook item storage according to the configured policy, not arbitrary live container filesystems. Restore tests validate notebook references and launch with the recorded environment or a clearly reported migration path.

## 6. Scheduled and parameterized execution

Implement scheduled notebooks as durable jobs using an execution tool such as a tested nbclient-based runner, with the exact tool/version selected in P0. A schedule records source revision, image digest, validated parameter schema, execution identity, scopes, time zone, concurrency policy, timeout and output retention. Daylight-saving transitions have defined duplicate/missed-run behavior.

A scheduled job does not reuse an indefinitely cached interactive administrator token. It uses an approved service identity or delegated execution grant that can be revoked. Revalidate grants at execution. No overlap by default; missed-run catch-up and retries are bounded and idempotent with respect to external publications.

Run records include cell progress, sanitized errors, correlation ID, resource use, output artifacts and publication references. A job failure does not overwrite the source notebook. A publication step follows the same staging/rollback semantics as desktop/portal publishing. Arbitrary notebook code is not automatically exposed as a public geoprocessing service.

## 7. Installation and operations

The installer offers notebooks as a product profile with explicit DNS/TLS/storage requirements. Generate the hub OIDC client, callback URLs, service integration settings and notebook domain routing. Administrators should not manually copy secrets among components. The portal shows per-user servers, jobs, quotas and environment versions with safe administrative actions.

Compose is acceptable for a single-node initial profile only after proving container isolation and the per-user-domain arrangement. A Kubernetes spawner profile can be introduced for stronger scheduling/isolation and scale; Kubernetes is not required merely to start developing the core product. Neither profile is safe if kernels can reach the container runtime socket.

Environment upgrades are separate from source-notebook edits. Support pinned old images for a bounded transition period, a compatibility report, and user choice to retest against the new environment. Security-critical image revocation overrides convenience with a clear migration error.

## 8. Acceptance tests

Launch two users and demonstrate no file/cookie/token/HTML access across their runtimes. Attempt access to an internal service and confirm network and service authorization deny it. Verify a revoked user cannot make new authorized data calls from a running notebook. Execute representative vector/raster/CRS operations in every advertised image. Restart the host and recover notebook files. Publish a result and find it in the portal with correct metadata/sharing. Run a scheduled notebook with scoped credentials and show its output does not become public automatically. Exhaust a user's memory/storage allocation without disrupting the API or another user.
