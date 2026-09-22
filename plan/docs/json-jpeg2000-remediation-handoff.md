# FND-02 JSON / JPEG2000 remediation handoff

**Decision-ready proposed successor; FND-02 remains In progress.** Both remaining
variant adoption findings are remediated by independent JSON implementation and
tested optional JPEG2000 exclusion. Explicit owner selection, four-criterion and
maintenance acceptance remain ungranted. This is a plan/candidate checkpoint,
not a completed GIS distribution or release.

Repository: `aloerch/ambisgis-platform` (verified ID `1376927351`), owner `aloerch`
(ID `15285626`). Branch: `fnd-02/json-jpeg2000-remediation` in
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-json-jpeg2000`.
Base: owner-merged #67/main `8f66b1e2a421d93e0c8d9714df76ad2dd62269a3`.
Review [PR #68](https://github.com/aloerch/ambisgis-platform/pull/68), tested
implementation head `fc56b119b56d68e9b4cc650d6c0665659f3e706c`.
[Publication](../verification/json-jpeg2000-remediation/publication.json) records
the separate Project item and successful preservation readback (80 → 81 items).
The following publication documentation changes no tested code, manifest or
artifact; final pushed review head is pinned in issue #3. No merge, source-fork/default/workflow/secret changes,
upstream contact, binary distribution, deployment or release are authorized.

## Exact selection

| Identity | SHA256 |
|---|---|
| Active revision 4/schema 1 manifest | `0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99` |
| Preserved parent revision 3 manifest | `8083a10deee529363e15925941c28e5a1e1f3030716f0cac7154c39466efbb90` |
| Selected `aggregate-04` WAR | `90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1` |
| Preserved parent WAR | `e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044` |
| Six-input local replacement map | `194139a86bb3640d991b4c23bc55b02d66526127bdea6c3d6f025216d41f87f5` |
| Unchanged QGIS manifest | `a2152edc50a7fdb34401e148c1eec238dfdf5dad6600faf73e92a063a4c47baa` |

| Selected local artifact (Maven filename is only a resolver key) | SHA256 |
|---|---|
| aspectjrt-1.5.4.jar | `5bf41bf5474d618423d2a6d8042468cf4e7e57db8895604f205d75fe61d5090b` |
| aspectjweaver-1.5.4.jar | `e35095ad483cc38a2cf17777f74f9a59abafed1fcabc7cf951b1fbf8153370d6` |
| xmlpull-1.1.3.1.jar | `fb4f2393e1cdf1c078a7800312eac6d1392ebd27c3015d06c25401d3bd705573` |
| json-lib-2.4.2-geoserver.jar | `de50a9896c9576c905c0dddfac562f431edebbb12ba0d30f2a8819a88e1f0744` |
| marlin-0.9.4.8.jar | `14633f73fed7e30553927201309bcaf407a9f5462fce87692f196859f33d074a` |
| jai_imageio-1.1.jar | `a7084cfbb419bd158464638454939d25e1fef1a990ee00bf6145b28956218007` |

All eleven core roots, ten profiles, seven combinations, 58 finding IDs and 56
unaffected findings remain. JSON's exact closing-condition string is unchanged.
JAI's new condition records the explicitly authorized removal alternative and
preserves its mandatory-JPEG2000 predecessor as history. The original 48
structural / 12 unresolved / four partial Java source ledger is not relabeled as
48 source-built components.

## Why removal is selected

The owner's stated priority permits losing optional JPEG2000 when ordinary
required functions remain intact. The [dated comparison](jpeg2000-exclusion-handoff.md)
records the official OpenJPEG maintenance notice and specific security/maintenance
inputs. Source-owned OpenJPEG would add native decoder/encoder, wrapper, ABI,
compiler, fuzz/regression and security-backport responsibilities. Current tests
support removal without those additional dependencies. This does not assert
industry-wide rarity or that every JPEG2000 dataset is unimportant.

Lost in this Java/server profile: JP2/raw J2K inputs, JPEG2000 output requests,
JPX-compressed PDF inputs and affected provider/SPI options. JPEG remains
supported. Ordinary JPEG/PNG/TIFF/GeoTIFF/georeferencing, real PDF/PNG/TIFF
printing, PostGIS vector and mosaic indexing/rendering, WMS/WFS, provider
startup, authorization and fresh persistent cache/browser restart pass. Explicit
unsupported requests receive controlled responses, leave catalog/task state
unchanged and permit subsequent valid requests. Real downloaded hostile-format
fixtures verify content handling, not merely filename rejection or HTTP 200.

This is not project-wide JPEG2000 removal. The unchanged QGIS profile uses its
own GDAL prefix; Exiv2 retains JP2 metadata handling. Database/QGIS selected
GDAL evidence has no OpenJPEG codec; notebook selection is unchanged. The
[cross-profile inventory](../verification/json-jpeg2000-remediation/imaging-cross-profile-inventory.json)
states precisely which paths were inspected.

## Source and rights evidence

[JSON evidence](../verification/json-jpeg2000-remediation/json-evidence.json)
accounts for seven original JSON.org-derived files, other derived portions and
the removed production layer. Eleven newly authored compatibility sources use
exact retained Jackson 2.21.0. Its shaded FastDoubleParser 2.0.1 source/revision
correspondence and four supplemental notices are retained; Jackson is unchanged,
not newly source-built here. No formal legal clean-room claim is made.

[Imaging source/terms](../verification/json-jpeg2000-remediation/imaging-selected-source-terms.json)
accounts for removed JJ2000 and dependent JPEG2000 providers. The selected
non-JPEG2000 source build retains notices and 323 ordinary classes unchanged.
Original sources, notices, historical positive JPEG2000 tests and all prior
artifacts remain custody evidence with their original rights. Their unresolved
permission is not cured by the new implementation. Engineering/source review
is not legal clearance; distribution and source/notice obligations remain.

## Fresh execution and historical reuse

The [final evidence index](../verification/json-jpeg2000-remediation/evidence.json)
binds every receipt below to the exact selected WAR or expressly named unchanged
component. Package assembly compiles test sources but skips test execution.

| Check | Retained receipt relative to build-worktrees/json-jpeg2000-remediation | SHA256 |
|---|---|---|
| source-probe | `source-war-probe-02/result.json` | `7fec066b076480453f6cd9ac50d510d099eb283e7e3975240f63559efc34ff1c` |
| json-probe | `json/war-probe-02/result.json` | `616f4cd96b4a7cce3539b4db9dd6f7cd2618ea1b28d7e7b0dbee5e0bdbe575be` |
| image-probe | `imaging/final-war-probe-02/result.json` | `76ca1812e9645657ba5aaa4f5152b1683c284e99f82eabf7301564f8e46a7a94` |
| war-geofence | `source-war-geofence-probe-02/result.json` | `ce319cbd1e45cdc2315b45e8f40ee4e2f5ecb3fec0218c89d72fe595b3ca433d` |
| logging | `logging-04/result.json` | `bee031106186153a89dbbf578edcea9d18f4dd74db475cc38aef24decaa48f33` |
| geonode | `geonode-02/result.json` | `99eddabe7725ad09cb1a752d58a9c57131cc972bd4d19af485a0de9e7d4ed2ad` |
| geonode-journey | `geonode-02/journey-result.json` | `1655a2cfaa7f36ab82a597e07eea717308e10df23053665d84eccec79400c4fe` |
| browser | `frontend-02/result.json` | `612e52c509cc95aa8203c7c9debaffa3a1b53788b059281e9d9e2bf8ca4e53bb` |
| gwc | `gwc-05/result.json` | `c1828b8261dbad53cd9084f21122e4a8195c0888f7a46f3b7cec5aaed50c33c7` |
| gwc-backend | `gwc-05/backend-result.json` | `709fe8c1b88f8e594ae6e77537c09cfe589138af0a17155b9a2e31dd998c205f` |
| mapfish-native | `mapfish-native-03/result.json` | `5a0117209863176710c063c7e006849bb3fd7c3dd166923fd3bd2f59480f8133` |

Fresh JSON evidence includes 213 retained contract comparisons, 64 common and
110 safety assertions, eight native writer methods, 41 native GeoJSONBuilder
tests and 94 real source consumers compiled. The broader old 359-test API is not
claimed. Six real importer converters were compiled and exercised with native
Catalog/Importer/DAO: parent/candidate original 50 assertions each and repaired
74, followed by actual final-WAR HTTP malformed/recovery checks. The inherited
transform-chain converter used the wrong existing reader method; its narrow
repair restores valid vector/raster chains.

Fresh exact-WAR XML/Spring/Java5 weaving and GeoFence 27 DAO tests plus actual
proxy commit/rollback pass. Native selected MapFish has 71 passes/six inherited
skips. Actual codec/printing probes, recursive full-library/class/native/source
accounting, loaded origins and intentional old JSON/JJ2000 fallback controls
pass. Strict GeoNode token/role/admin/denial/cache/restart, real PostGIS vector/two
mosaic indexes, cold MISS→HIT→persistent restart HIT with protected denials, and
unchanged frontend replay-02 content/zoom/reload/restart pass.

Database/Jupyter/QGIS and frontend compilation/native/IFC evidence is reused
with integrity verification. No QGIS rebuild or unrelated full native rerun is
claimed. [Validation](../verification/json-jpeg2000-remediation/validation.json)
records actual package/guard counts and exact recipes. Package tests are not GIS
product tests. Inventory/report exit 0, while eligibility correctly exits 2 for
ungranted owner/distribution gates; no fictional approval was added.

## Failed attempts and limits

Raw failures remain in the compact indexes: wrong earlier Maven custody,
raw-Map JSON generic mismatch found by the actual importer compile, bounded
numeric/UUID interoperability corrections, guard metadata-name/Servlet API
repairs, MapFish finalization/error propagation repairs, and two incorrect
aggregate-inspection method-marker assertions. Later diagnostic HTTP runs found
an inherited malformed-JSON 500, remote fixture routing denied by containment,
an arbitrary PDF size assertion and an unsuitable remote PDF tile fixture.
They remain failures; repaired assertions require parsed/rendered known content.
Successful intermediate WAR execution is historical once the final converter
source changes the aggregate. No failed receipt is overwritten or renamed pass.

Historical JSON 357/359 failures remain unsafe JavaBean class-property
expectations, tested separately for intended safe suppression. Marlin 46/48
publisher-equivalent degenerate-path failures and Java7-target LTW VerifyError
remain; no -noverify, bytecode-header surgery or weakened rendering tolerance.
Five inherited frontend lint failures, webpack warnings and six MapFish skips
remain. TIFF JPEG2000 compressions 34712/33003/33005 and the selected missing
remote mosaic URL source are recorded pre-existing unsupported paths.

ZIP preflight limits compressed staging to 1 GiB and 10,000 members, inspecting
bounded member prefixes and returning 413 with cleanup at limits. Inherited
multipart parsing may stage before that guard. New MapFish loaders/byte-array
validation use 64 MiB; inherited HTTP paths may buffer before validation.
URL loaders use per-read timeouts and elapsed checks, not a strict wall-clock
deadline. These are explicit bounded-profile limits, not comprehensive generic
upload/HTTP hardening or full raster/cartographic/API parity.

## Containment and exact commands

Builds use retained exact inputs with network/socket denial. Runtime fixtures use
existing trusted-loopback controls, Chromium sandbox and the explicit pre-existing
PostgreSQL-only supervision exception. No host firewall/security changes, public
listeners, system native installation or new containment exception. Task-owned
services stop, temporary import staging is checked, PostGIS fixture schemas are
dropped and synthetic credentials are invalidated/scrubbed. Unrelated processes,
source worktrees, the prior branch and the user's initial STATUS edit remain intact.

The exact aggregate invocation was:

```sh
/usr/bin/python3 /home/revelberry/Projects/AmbisGIS/ambisgis-platform-json-jpeg2000/build-support/java/compatibility.py --audit-custody /home/revelberry/Projects/AmbisGIS/source-archives/java-audit --custody /home/revelberry/Projects/AmbisGIS/source-archives/java-http-auth/maven --toolchain-custody /home/revelberry/Projects/AmbisGIS/source-archives/java-resolution/toolchain --tools /home/revelberry/Projects/AmbisGIS/build-worktrees/java-resolution/toolchain --output /home/revelberry/Projects/AmbisGIS/build-worktrees/json-jpeg2000-remediation/aggregate-04 --target webapp --stage package --tests compile-only --repair xmlcodegen-emf --oauth-redaction --oauth-principal --configured-auth-diagnostics --configured-auth-stateless --role-service --role-service-repair --no-oracle --variant-inputs /home/revelberry/Projects/AmbisGIS/ambisgis-platform-json-jpeg2000/build-support/java/json-nojpeg2000-variant-inputs.json --no-jpeg2000 --timeout 1800
```

Run directories are immutable evidence; a repetition must choose fresh output
names. Native/component and HTTP commands are retained verbatim in their receipt
`commands`/invocation records and frozen tooling. The coordinated final root
runtime invocation record is `/home/revelberry/Projects/AmbisGIS/build-worktrees/json-jpeg2000-remediation/root-runtime-invocations-02.json`.
The original source/component recipes and standalone recheck CLIs are linked
from [JSON](json-compat-handoff.md) and [imaging](jpeg2000-exclusion-handoff.md)
component handoffs. Use the retained host namespace for Java/Maven/runtime Python;
IDE `/tmp` and host `/tmp` are different.

From `plan/`, the exact supported package operations (executed with the recorded
validation interpreter) are:

```sh
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --eligibility
python3 tools/validate_candidate.py --workspace-root /home/revelberry/Projects/AmbisGIS --report
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```

## Remaining owner decision

Review the exact PR/head and select or reject this manifest, expressly accepting
NO-ORACLE/headless/NO-JPEG2000 and bounded-profile limits if selected. Accept the
[C1–C4 report and F02-07 maintenance binding](fnd-02-json-nojpeg2000-acceptance.md)
separately. Retained source/notices, License/Brand, security, signing and deployment
remain their existing later gates. F02-06 is decision-ready; F02-07 is documented;
F02-08 has its criterion report. None is silently owner-accepted, and issue #3
stays In progress. The next ready action is this concrete owner review; no new
unspecified smoke milestone or full-product prerequisite is introduced.
