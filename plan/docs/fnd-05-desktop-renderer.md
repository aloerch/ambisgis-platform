# FND-05 desktop publication and renderer comparison

This companion implements the server half of
[FND-05](https://github.com/aloerch/ambisgis-qgis-plugin/issues/1), the original
P0 comparison spike. The plugin repository owns the desktop analyzer, bounded
copy package, synthetic fixture, capability profile and G3W/Lizmap ADR. The
platform owns permanent engine enforcement and native integration orchestration.
Neither repository claims a completed publishing wizard, durable publication
saga, Windows validation, full T-CARTO-01 acceptance or released GIS product.

The plugin branch starts at `2d6eb508d9a6b6c149b07dfa721a1d57f05af48f`;
the companion starts at the accepted FND-03 merge
`0876999d7535d792d0024586981c762b2f9bf513`. The integrator must bind both final
repository heads and review their dependency order. This worker makes no
remote writes or shared ledger/status changes.

## Original criteria and evidence

| Original criterion/deliverable | Implemented evidence | Bounds |
|---|---|---|
| Representative style packaging/rendering and authorization work | Native PyQGIS exports categorized/simple points, a line, polygon, expression labels and grayscale raster; the clean copied project reopens with equal data and identical individual rendered PNGs. Real GeoServer and QGIS Server HTTP images pass spatial/color/label/raster probes and a measured comparison against those authoring renders. | Synthetic EPSG:4326 extent 0–4; Linux offscreen; fixed WMS map profile. |
| Record unsupported style/provider behavior and chosen extension hooks | Actual native analyzer negative cases, supported/unsupported matrix, native SLD expression rejection and explicit QGIS Server selection; source-owned hooks documented in the plugin ADR. | Wider providers, expressions, fonts, CRSs, output types and asset licensing need later reviewed profiles. |
| QGIS/GeoServer/QGIS Server fixture; G3W/Lizmap comparison and ADR | Executable two-repository fixture and retained runtime receipts; plugin `docs/decisions/0001-renderer-comparison.md` cites primary documentation. | G3W/Lizmap comparison is documentation/interface research, not an installation or benchmark claim. |

The fixture compares each actual HTTP PNG with independently known feature
positions/colors and raster values, then enforces mean absolute pixel error
at most 3.0 against the native authoring image. A blank-image negative control
must fail. Hash equality alone and an HTTP 200/PNG signature are insufficient.
Rich labels require visible dark text near all three known points. The native
package roundtrip also compares vector attributes/geometry and raster samples.
Shapefile import explicitly records one-part multipart promotion and clockwise
polygon ring conversion; every original attribute/coordinate and polygon
topology is checked. Retained 255→254 field-width warnings do not imply fixture
value truncation; wider values are diagnosed instead of silently accepted.

## One authority and explicit map boundaries

`ambisgis_policy.catalog.allowed()` and `/internal/policy/read` remain unchanged.
Native OAuth tokens, ResourceBase approval/publication, guardian sharing and
group memberships are the only decision authority. New map adapters send the
exact parsed resource and bearer credential to that existing authority. They
store no second user/grant/token table and keep no positive decision cache.

`ambisgis_render.boundary` enforces a fixed `/map` request profile and a
provisioner-selected renderer/asset binding. `CatalogMapPolicyFilter.java`
enforces the same finite profile before GeoServer servlet dispatch, including
all dispatcher types. `ambisgis_render.qgis_server` invokes owned `QgsServer`
and `QgsAccessControlFilter.layerPermissions` for the installed clean project;
insert/update/delete and `allowToEdit` deny. Native QGIS dispatch is sequential.
The Java launcher accepts only the two named owned catalog filters, preserving
the existing WFS filter as its default. Existing FND-03 WFS parsing is unchanged.

Only WMS 1.1.1 GetMap, one exact layer, empty packaged default style,
EPSG:4326, 0/0/4/4, 512×512 PNG and opaque background are in this profile.
Additional/duplicate parameters, `MAP`, remote `SLD`, unsupported widths,
capabilities, writes, raw admin/UI, WFS/OWS/cache paths and caller resource
headers cannot broaden it. Both native engines and gateway recheck approved
data/style/project asset hashes. The test mutates only its disposable copies
to prove subsequent denial. An administrator token cannot reach raw engine
administration through this profile.

The native journey checks public/private/group sharing, committed share/group/
token revocation, concurrent owner/revoked requests, catalog failure, catalog
restart, both engine restarts, malformed authorization and asset tampering.
Denials carry no map body; responses use `no-store` and return no cookies.
This establishes the named new-request cases, not cancellation of a request
already rendering during a concurrent policy change.

## Exact runtime provenance and execution

Final source and raw-receipt hashes, actual commands, counts and cleanup results
are in [the safe verification report](../verification/fnd-05/runtime.json).
The full private attempts remain under
`/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd05-runtime/`; previous receipts
are immutable, including failed engineering attempts.

Independent review found nonfinite GeoJSON property values were accepted.
The final guard rejects NaN/±Infinity and overflowing numeric properties;
12 stdlib tests and the complete actual PyQGIS `pyqgis-014` rerun pass,
including 13 native analyzer negatives. `maps-005` remains explicitly bound
to the earlier `pyqgis-013` fixture. All six positive source datasets and
rendered layer images hash-match between those runs; server/harness source
is unchanged. The receipt records both source sets and does not claim a new
HTTP run after this input-only guard correction.

The selected QGIS stage is the newly compiled owned successor
`86af40542b219b0da6df1a43914413443330c0c0`, tree
`84ea1b18fdf5721819fee34fe06cdef7ea82afdc`. Its manifest SHA-256 is
`8711c8dafa12fceb3ace2c8d9c148e43c1dcd845f49c5c85bb7c72f9f80703f7`.
The renderer harness validates all 8,110 staged files/links before and after;
native process mapping checks include the actual QGIS Server library, core,
Python/Qt bindings and providers. The font is retained QGIS Vera, declared as
a runtime dependency rather than embedded or relicensed by the package.

The selected new owned GeoServer WAR SHA-256 is
`9b56b1f65fe267162d9e5035f60f7e6a5e2204bbbc95ce2c77ae62c2b3ac8552`, using
`fnd08-java/run-002/runtime-profile.json` SHA-256
`0748a443611b85709d90d693a7ac22afebdf32cf5bd5adaabfb4d02ca705eae0`.
The additive `successor_runtime_inputs.py` verifies the new producer schema,
exact owned GT/GS/GWC identities, successful build/network receipt, current
source bytes, built artifacts and every packaged library origin. The old
recipe verifier is unchanged and there is no hidden fallback. This is honest
reuse of newly produced bytes for affected renderer tests, not FND-08 closure.

Native GeoNode, PostgreSQL/PostGIS, OAuth and existing disposable database
fixtures are reused explicitly from FND-03. Java/Python adapters compile/run
from the recorded source snapshots. The existing loopback supervisor checks
network restrictions and process cleanup. PostgreSQL alone retains its
documented supervisor exception; no production services are contacted.
This trusted synthetic fixture is not a hostile-code or uploaded-file sandbox.

## Reproduction and remaining acceptance

Run the exact command arrays in the safe report with fresh output directories.
First execute `build-support/renderer/qgis_probe.py` with the explicit QGIS
config and plugin script/root. Feed its `fixtures` output into
`build-support/geonode/run.py --integration --strict-verifier --strict-roles
--catalog-policy --renderer-fixture … --qgis-config … --source-successor-build`
with the exact new WAR/build/profile arguments. No runtime input is inferred
from a floating tag or downloaded implicitly. Input paths must identify the
retained source-owned artifacts; a different runtime needs a new receipt.

Package/schema tests and pure harness tests are separate from the actual GIS
and HTTP assertions. The task retains original broader requirements for
Windows, physical-display UX, sign-in/publishing UI, registered data references,
durable private staging/activation/idempotency/compensation, managed branch
editing and every other output/cache path. Security/source/rights review and
two-head acceptance remain with the integrator; this document does not mark
the task Verified, Merged or Released.
