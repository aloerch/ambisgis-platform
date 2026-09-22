# Current matrix — independent JSON / NO-JPEG2000 revision 4

Exact current WAR: `90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1`. All seven combinations remain scoped in the
[manifest](../candidates/fnd-02-candidate.json) and
[immutable receipt index](../verification/json-jpeg2000-remediation/evidence.json).

| Combination | Current evidence | Reuse and limits |
|---|---|---|
| Database | Original selected archive/tools/tree hashes verified | Historical native/upgrade tests; no new complete database suite |
| Java native | Fresh exact-WAR JSON/XML/Spring/Java5 LTW, GeoFence DAO/transactions, ordinary codecs and actual PDF/PNG/TIFF printing; explicit JPEG2000 rejection and origin/fallback checks | Selected native MapFish 71 passes/six skips; broad historical Java suites and their failures remain tied to original artifacts |
| Identity | Fresh issued-token/role parsing, configured WFS/REST/admin positive and negative controls, stateless isolation, finite cache, revocation/restart | Unchanged owned Python wheels/database selection |
| Frontend/browser | Unchanged replay-02 displays known layer from current WAR; actual content, zoom/reload and backend restart under Chromium sandbox | Frontend compilation/native/IFC reused by integrity; five inherited lint failures |
| QGIS | Same selected manifest `a2152edc50a7fdb34401e148c1eec238dfdf5dad6600faf73e92a063a4c47baa` verified | Prior desktop/server/resource/restart and 66 C++/16 Python checks remain historical; no rebuild |
| Jupyter | Exact original wheels/locks/Hub/Lab/kernel evidence verified | No new isolation or native suite |
| Embedded GWC | Fresh private-cache public/authorized MISS→HIT→persistent restart HIT, protected denials; real PostGIS vector/two mosaic indexes, decoded WMS/WFS; live importer/format/print rejection and valid recovery | Same selected renderer/profile; native unsupported remote harvest and TIFF-JPEG2000 variants remain explicit |

This is bounded FND-02 evidence, not full policy/publication/concurrency/restore
or distribution acceptance. [Final criterion review](fnd-02-json-nojpeg2000-acceptance.md)
identifies the remaining owner decisions.

# Preserved revision 3 matrix — historical

# Java/GMT proposed revision 3

All seven combinations remain separately scoped. Exact artifacts and receipt
bindings are in the [manifest](../candidates/fnd-02-candidate.json) and
[Java/GMT handoff](java-gmt-remediation-handoff.md). Final selected WAR is
`e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044`.

| Combination | Revision3 evidence | Reuse/limits |
|---|---|---|
| Database | Exact original archive/tools checked | Historical native/upgrade; no new whole database suite |
| Java native | Fresh exact WAR parser/JSON/Spring/LTW, codecs/MapFish/renderer/logging; actualWAR PostgreSQL DAO/proxy commit/rollback | Source-native 62 GeoFence tests; importer 112 passes/6 skips no-Oracle check. Full priorXML/MapFish/OAuth suites historical; two JSON/two Marlin inherited failures explicit |
| Identity | Fresh strict GeoNode issuance/roles/removal/admin denial/controls/cache/restart | Exact unchanged owned Python wheels and source-owned database |
| Frontend/browser | Fresh sandboxed known GIS layer/zoom/reload/restart with new WAR | Unchanged replay02assets; compiler/native/IFC integrity-only reuse; five lint failures |
| QGIS | Fresh1130resource/model exclusions,265retainedpalettes, chooser/savedrefs/desktop/PostGISGetMap/restart | Same compiled binaries;66 C++/16 Python historical, no rebuild |
| Jupyter | Exact historical wheels and original boundedHub/Lab/kernel results checked | No new native/isolation suite |
| EmbeddedGWC | Fresh public/authorizedMISS→HIT→persistent-restartHIT, protected denials/controls; PostGISvector and realnative-mosaicindex/WMS | Fresh cache and selected renderer; no old rendered tiles reused |

Package tests, inventory integrity and a merged checkpoint never grant product
acceptance. Later policy/publication/isolation/recovery/concurrency gates remain.

# Preserved historical matrix

# FND-02 combination smoke — F02-05

**F02-05 bounded engineering evidence is owner-accepted through merged [PR #64](https://github.com/aloerch/ambisgis-platform/pull/64), reviewed `ee5be14d9d0d14f361dbd235dedc64b3fdb84db0`, merge `725d519820293f466b287d7f4cd779c36b9b7977` (verified during F02-06). FND-02 remains In progress.** Owner-merged #63 accepts F02-04 only:
reviewed `c68f42baa8cb6d21d6b34dce07c2e4ad3ee64409`, merge
`56186baf19dc6ee02d4152e019d2dd96c5ec1b3e`, verified current main at this slice's
start. Historical open-PR prose creates no new F02-04 gate or resource-rights approval.

This is one matrix of tested combinations. They did not all run simultaneously
and do not share one Python/native prefix. Six rows reuse bounded historical
results; only the missing embedded WMTS/cache/security/restart connection ran
fresh. [Compact index](../verification/combination-gwc/evidence.json) binds sources,
receipts, commands, artifacts, failures and independent review. Frozen tested
implementation: `4d58d7f17bba71bae60670fde2587f3fdbdf3307` on
`fnd-02/combination-gwc-smoke`. Subsequent evidence/status/publication edits are
documentation, not additional service tests.

All local paths below are relative to
`/home/revelberry/Projects/AmbisGIS/build-worktrees`, unless marked as repository
paths. Run timestamps are quoted only where actually present in retained records.
Several runtime receipts do not include an absolute UTC date; filesystem mtimes
are not substituted for execution dates.

| Selected combination | Exact source, runtime, artifact/profile | Retained positive smoke and restart scope | Evidence state and limits |
|---|---|---|---|
| PostgreSQL / PostGIS / GEOS / PROJ / GDAL | PostgreSQL 15.19 `2ff1375b5dd8bf09d8cb0e795974528180fd75ca`; PostGIS 3.5.7 `9816f82458db774e62906cfb2c4f01f8b262c862`; GEOS 3.13.1 / PROJ 9.6.2 / GDAL 3.10.3 in `postgis-slice/run-003/prefix`. Original output archive SHA256 `8605ce69555eecf216a9d80a0aa954a16aa2a30d030597be9fe7a05f3ab6bb55`. Exact dependency/runtime hashes and profile: [database index](../verification/postgis-slice.json), [profile](postgis-slice-evidence.md). | Real 3.5.6 → 3.5.7 stop/install/restart/extension-upgrade fixture: 13 old, 13 upgraded and 13 fresh spatial checks; final independent linkage smoke 13/13; actual GiST plan, GEOS, CRS, GeoJSON, nonempty MVT, GTiff round trip and topology. 672 source-mode + 672 installed SQL regressions; clusters stopped. Final smoke `2026-09-19T17:55:24.360313+00:00` → `17:55:28.119992+00:00`. | Historical demonstrated bounded database combination. Upgrade restart is not backup/host-restart acceptance. No managed branch, production security or full dependency suite claim. QGIS's separate expanded spatial/XML prefixes do not change this original combination. |
| Java / GeoTools / GeoServer and selected extensions | GeoTools 34.5 `aac73e9b89821331e77f67f1dd0921e541a78cfc`; GeoServer 2.28.5 `e0673323400321c0f3409fbae68b4871dc328d8a`; retained Temurin 17.0.20.1+1 / Maven 3.9.16. Source, retained dependencies and guarded repairs stay bound by [Java inputs](../../build-support/java/inputs.json), [native index](../verification/java-compatibility.json), [HTTP run index](../verification/java-http/run-index.json). Successor selected aggregate is #61 WAR `a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`: importer, oauth2-geonode, geofence-server, geofence-server-postgres, printing, postgis, authkey. | Referencing 667 pass/8 skips; importer 112 pass/6 skips; GeoFence persistence 62 pass/0 skips. Controlled XML `xml-http-04` 298 pass/4 skips; MapFish `mapfish-http-05` 71 pass/6 skips with actual WMS/WMTS fixture responses; OAuth principal 687 pass/1 skip. Their recorded starts: XML `2026-09-20T22:31:47.092245+00:00`, MapFish `22:51:23.281178+00:00`, OAuth `22:46:29.726204+00:00`. Successor #61 aggregate logging and real configured HTTP/restart are separately demonstrated in identity/frontend rows. | Historical selected native fixtures are not full servlet/tuple passes and are not embedded GWC tile evidence. 157-module successor aggregate packaging explicitly skipped tests. The unchanged source tuple and retained external dependencies support bounded reuse, not a claim that all older tests were rerun against successor WAR bytes. Java source ledger stays 48 structural / 12 unresolved / four partial. |
| GeoNode / GeoServer / authoritative role service | GeoNode 5.1.0 source `a1db97e81dfc26c16bb4ee1a5d2b408877af66c9` plus guarded strict verifier/role repairs; actual built 5.1.0.post1 wheel `d4194e17bfaa517d829b47550022bc0831a3fe0872483d968ecbf29251cd5c28`; client backend wheel `1ba859afca3993da35f05e838185fa027d0f9779a4cb26124dd638617157442b`; #61 WAR `a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52`; retained Jetty 10.0.25, Servlet API 4.0.6 and SLF4J 2.0.16. [Index](../verification/geonode-role-propagation/evidence.json), [loaded configuration/origins](../verification/geonode-role-propagation/configuration.json). | `geonode-role-propagation/integration-03`: 393 real GeoServer HTTP requests (384 initial + nine after restart), 82 assertions across 156 harness GeoNode HTTP requests; 96 correlated sequential/concurrent resource cases; membership/admin revoke/restore, fault denial/recovery, WFS/REST enforcement; persisted revoked membership denied after restart before restoration. 70 native Django passes; 39 Java role passes; successor OAuth/security 707 pass/one skip. Original services/fixture stopped and private credentials scrubbed. | Historical demonstrated strict local identity/role candidate; no canonical product policy, production SSO, global logout, publishing or maximum revocation SLA. Runtime receipt has no absolute UTC date field; aggregate packaging start is `2026-09-21T05:25:53.288295+00:00`. Guarded source changes and fixed local resource rules remain explicit. |
| Client / MapStore / browser / GeoNode / GeoServer | Client source `7ca4822125b67999c97cb4aa1faa84b8a28eee9b`; owned MapStore gitlink `0f3518737f29f4049b131247ce981e94519d9ab0`; Node 24.18.1 / npm 11.16.0. Served `frontend-completion/build-01` full output manifest `b60beafd554751946b2c6669a471a6198ba93011cc5cec42cd7a5fd51e50ce0f`, served manifest `1bb923a7a96254f370ab07d517b6ebfd84f899b5ae1704f0e24df2b043b33c57`, gn-map entry `e0932e972dd84059b2dd4a374a7042e97a29f1cf565462756a7ef412a46b3d60`; exact #61 wheels/WAR above; retained Chromium 153.0.8010.12. [Browser summary](../verification/frontend-completion/browser-evidence-summary.json), [complete manifest](../verification/frontend-completion/served-build-output-manifest.json). | `frontend-completion/browser-smoke-06` passes both initial/restarted backend phases: 109 responses and 43 checked loaded artifacts per phase, three WMS responses each, six actual rendering witnesses, wheel zoom to smaller BBOX and reload. Zero unexpected external requests, failed requests, blocking console errors or page errors; expected anonymous userinfo 401 is explicit. Same served build and same #61 WAR pass after backend restart; cleanup passes. | Historical demonstrated public viewer. No private browser authorization, full accessibility/cartography/publishing or byte-identical rebuild claim. No absolute runtime date in top-level retained receipt. Three clean frontend builds/native checks remain supporting evidence; five inherited lint errors/five webpack warnings and rights findings stay in F02-06. |
| QGIS desktop/server / PostGIS / selected native libraries | Owned QGIS 3.44.14 `1a4cda5f2620e7374e5926fc955a7d2d06493e15`, retained owned tar `229ce420ccf5f993eff29e58dc500f2fe7337395595989f947481c34c8cfb875`. `qgis-candidate/build-06/prefix`, reconciled manifest `931e5f0523e1d9bdba6b2fbd27e6c208297456db696265beb961a57e77ed82c9` (9,235 entries); Qt 5.15.19, Python 3.13.14, `support-07`, `spatial-04/prefix` (SQLite 3.50.4/PROJ 9.6.2/GDAL 3.10.3), `xml-profile-01/prefix` (libxml2 2.14.6 with HTTP), `python-gdal-02/python`, original database-prefix GEOS/libpq. [Index](../verification/qgis-candidate/evidence.json), [profile](../../build-support/qgis/profile-inputs.json). | `native-01` 66 C++ cases + 16 Python passes, no failures/skips. `runtime-04`: actual offscreen desktop, six completed canvas renders, zoom, Save Project/clear/reopen and File Exit 0; real local vector/raster and restricted PostGIS reads, exact CRS and GEOS witness. Six real native WMS requests over two server processes with one restart on the same loopback port; isolated local/database renders and combined output verified. Selected process maps/integrity and cleanup pass. | Historical demonstrated F02-04 engineering scope; bounded owner acceptance is verified in merged #63. Original build-06 final guard failure is retained alongside separate successful generated-file reconciliation, never relabeled. No physical display, full providers/OGC/cartographic/Windows/macOS, publishing or resource-rights clearance. Runtime receipt lacks absolute UTC date. |
| JupyterHub / proxy / JupyterLab / Server / kernel | Hub 6.0.1 `3e516c6f382b481e815ec455befb2f14d80d337b` wheel `e3c8ddb0b8307e54debddc75af2ffc1fc59d690fa3cf987693da09e404d5a277`; Lab 4.6.3 `e7255a9334c12ad8f9cb15db27584215fab5ece2` wheel `98c21e3a6a98e011418ad5d586f3679fdfe942254dd1ac1e3d1f4f10147b8d02`; `jupyter-slice/run-002`. Separate Hub/user venvs; host Python 3.13.15, Node 24.21.0/npm 11.19.0, proxy 5.3.0, Server 2.21.1, ipykernel 7.3.0/client 8.10.0. [Index](../verification/jupyter-slice.json), [profile](jupyter-slice-evidence.md). | Two fresh-state full probes `runtime-ivnhawpn` and `runtime-tgw1e3j7`: standalone Lab and actual Hub → proxy → owned single-user start; real kernel HTTP/WebSocket execution `AMBISGIS_KERNEL_RESULT=285`, notebook save/reopen, missing/invalid-credential denial, all observed TCP listeners loopback and clean shutdown. Same 418-asset manifest `9c0d114ec2143877b9b56cd78bc25a50995962b207263ccfc41ddc505a17f647`; all four notebook hashes `fe87ee918a863c83abf5d7a28266f90321f6169c685fd9d4f4d70bb7a705a163`. 329 selected native passes/zero skips. Build receipt starts `2026-09-19T19:19:53.018808+00:00`; runtime receipts have no absolute date. | Historical demonstrated trusted same-user development fixture. Two starts are not a host-restart/restore test. No two-user/origin isolation, production SSO, quotas, GIS notebook package profile, publishing or browser/accessibility acceptance. External runtime egress denial was not enforced. |
| Embedded GeoWebCache / selected GeoServer aggregate | Owned GWC 1.28.5 `59640420454b73f1e04e8409cc6ed43f4b24fed2`; exact #61 WAR above, unchanged. All 64 embedded GWC/GeoTools/GeoServer-GWC JARs match retained own reactor outputs. Same strict GeoNode wheels and original database/native prefix; same retained Java/Jetty runtime. Fresh task cache, explicit native route property, GWC security enabled, EPSG:4326 PNG, 1×1 metatiles and synchronous saves. | **Fresh `combination-gwc/smoke-07`, 2026-09-21 18:10:16–18:11:31 UTC:** 30 WMTS/GWC HTTP requests over initial/restarted GeoNode+GeoServer; public and authorized reader each MISS → HIT → restart HIT. Two 2,896-byte persistent entries; exact hashes/inodes/mtimes stay unchanged on hits/restart. Ten PNG responses pass independent geometry/layout decoding; eight protected anonymous/outsider denials plus two invalid-layer errors and valid controls. Same WAR/catalog/styles/cache, original security files unchanged, complete active security set unchanged after initialization. Cleanup and network proof pass. | **Demonstrated bounded embedded cache link.** Native protected-tile control is included, but no revocation/user partitioning/multi-node/private-cache product acceptance. One matrix/tile per layer; no full OGC, vector tiles, benchmark, browser/QGIS tile client, publishing or production claim. Six failed attempts remain unsuccessful and retained. |

## Primary retained receipt identities

| Combination | Receipt / artifact | SHA256 |
|---|---|---|
| Database | `postgis-slice/run-003/databases/database-dqiotqr3/prepare-upgrade-kva1evgy/report.json` | `7a2c6be9ca86c8f0b6be5994f26972a408ab3d87dcbaf2b326c50415d73923d0` |
| Database | `postgis-slice/run-003/databases/database-dqiotqr3/finish-upgrade-klpvwwyz/report.json` | `68fcb75c3e993a68a55ef4de9edb15361ec88ffc35aad4f714a2559a5d384694` |
| Database | `postgis-slice/run-003/databases/database-i77hsodz/smoke-m_jrcky1/report.json` | `8925f0a2c3099e8786e4945671d1b751200913da2d0314c29a02793dfe8387d3` |
| Java XML | `java-http/xml-http-04/result.json` | `bf4578d2407a88609df765ffcdd02f90ce153a1415d857722405bb1df9bc930c` |
| Java MapFish | `java-http/mapfish-http-05/result.json` | `291f825004a061c505e1046d2222d773abb38586fca3d254d6279159d349089e` |
| Java OAuth | `java-http/oauth-http-principal-01/result.json` | `fe9f1091fcf0266dd10abed4a6f07c138b0163729461b753a434f0abd8ec2862` |
| Identity | `geonode-role-propagation/integration-03/result.json` | `2da8948e846617effe9fb8e5200b1870141f0b6ce768034c177df3c19e5d4e5d` |
| Frontend | `frontend-completion/browser-smoke-06/result.json` | `b1dcc7f40305fc54ccee50542ee0744d591d1af1142347918fe0a0e703deaded` |
| QGIS | `qgis-candidate/runtime-04/result.json` | `a4d5289311abc1d8cce80b591b5b0068c4996be78e9247478f0d4ed43d9769be` |
| Jupyter | `jupyter-slice/runtime-evidence/runtime-ivnhawpn/report.json` | `edd963ad2d28d5a8ea85eafa58da5c0ab163177f3033917c4d42effdaa178f6e` |
| Jupyter | `jupyter-slice/runtime-evidence/runtime-tgw1e3j7/report.json` | `271c34044dbca848dfd8ce6381dfa6ec35448fd378b99abf6c43d9da7d6d7396` |

## Successor aggregate compatibility and read-only check

The older Java HTTP combined WAR
`bfc104892843c17c6c5b9aa8ab19609cb1f9e4fb8e971e6b3b845fe40f8288ac`
predates OAuth repairs and is not the selected runtime WAR. #61's
`a3cea4ad...` aggregate contains guarded OAuth/configured-auth/strict role repairs,
source-built authkey and the same owned source tuple. Its retained dependency
delta and inventory distinguish the new owned authkey library from unchanged
external inputs. The #61 native role/OAuth runs, compiled final-WAR probes,
configured identity HTTP/restart and #62 browser/backend restart supply actual
successor evidence. Older XML/MapFish/native passes retain their own artifacts
and tested scope; changed aggregate packaging is not claimed as their rerun.

`combination-gwc/reuse-audit.py` was run read-only against the QGIS integration
worktree. `combination-gwc/reuse-audit.json` records actual SHA256 and size checks at
`2026-09-21T17:51:12.064812+00:00`: **300/300 reference records**, **294 unique
paths**, zero mismatches/missing files. Groups: QGIS 59, Jupyter 19, database 79,
identity 46, frontend 42, Java HTTP 41 and Java native 14. Actual selected #61
WAR/wheels, database runtime binaries/output archive and Hub/Lab wheels were
hashed in addition to receipt references. QGIS/frontend complete output manifests
were hashed in that initial audit. A separate later current-payload check with
existing `common.verify_inventory` and `smoke.verify_manifest` now verifies every
QGIS staged entry (9,228 files + seven symlinks) and both original/served frontend
trees (1,038 files each, including 960 compiled entries). No missing, changed or
extra payload was found; `combination-gwc/payload-integrity.json` binds exact
commands/helper/manifest hashes. This is integrity verification, not another build
or native suite.
Historical failed receipts retained within indexes are hashed as evidence, not
counted as positive runs. No service/build/native test was rerun by this audit.
The audit script SHA256 is
`c385531b78795f45648205ea1827ef9909cf1c5e5be717034268a274b3ece4f5`.

Existing stronger read-only prefix verification helpers are in
`build-support/qgis/common.py`: `verify_historical` compares the entire original
database prefix against its original retained output archive; `verify_selected`
checks exact support/spatial producer manifests and full inventory;
`verify_xml` checks the separately selected XML prefix. Import them only with
bytecode writes disabled when performing a read-only check. Do not invoke build,
reconcile or runtime entrypoints merely to regenerate already demonstrated results.

## Fresh embedded-cache result and resume

Run root: `/home/revelberry/Projects/AmbisGIS/build-worktrees/combination-gwc`.
Successful runtime/cache root: `smoke-07`, with a **new private persistent**
`smoke-07/tile-cache`. The real endpoint was
`http://127.0.0.1:34001/geoserver/gwc/service/wmts` (stopped).
Actual capabilities advertise EPSG:4326, matrix `EPSG:4326:5`, default empty style,
256×256 PNG, matrix size 64×32, top-left latitude/longitude `90 -180`.
Derived WMTS column 32/row 15 is native cache index `[32,16,5]`, x/y bounds
`[0,0,5.625,5.625]`. No guessed alternate-version grid identifiers.

Point `(longitude=1, latitude=2)` projects to pixel `(45.5111,164.9778)`.
The independent 28px red-circle oracle finds 562 red/640 opaque pixels, centroid
`(45,164.5)`, correct radial interior/exterior and otherwise transparent output.
[Retained public PNG](../verification/combination-gwc/public-tile.png) and the
same protected synthetic geometry both hash to
`09e004ea5ab2c00f1dde369fef6b0b29fe36aae3c585d8a2e11fe2ab582efa69`.
Equal bytes do not establish cache reuse: each request is also bound to its
exact native cache path, header index/grid/bounds, new/unchanged file set and
inode/mtime. Paths are `fixture_public_points/EPSG_4326_05/4_2/32_16.png` and
`fixture_private_points/EPSG_4326_05/4_2/32_16.png`; together only 5,792 tile bytes.

The fixture explicitly sets `securityEnabled=true` (the previous fixture's GWC
setting was false), `metaTilingThreads=0`, 1×1 metatiles, gutter zero and PNG-only
EPSG:4326. Scoped bearer administration enables only the two synthetic layers.
Existing stateless bearer/strict GeoNode role filters and GeoFence rules remain
unchanged. Native startup/authentication adds five recorded CSP/provider/keystore/
user-schema files; **zero originally configured security files change**. The
complete active set remains identical throughout tile tests and restart. Reader
access succeeds; anonymous/outsider get the exact native HTTP400 GWC HTML denial
`Cannot access private_points with the current privileges`, including after
caching/restart. This is actual authorization evidence with positive controls,
not an absent-layer/disabled-service inference. Invalid layer returns HTTP400
OWS `InvalidParameterValue`/`LAYER`, followed by a valid HIT.

The unchanged WAR needs the supported JVM setting `-Dgwc.context.suffix=gwc`.
Actual readback proves `/gwc/rest/layers` registration and the intended active
cache path/security/metatile settings. Failed URL-suffix and file-property
attempts remain recorded; the exact earlier placeholder resolver ordering is
not proven. No source/dependency repair, substituted JAR or aggregate rebuild
was needed. The only Java change is an opt-in fixture launcher readback of cache
settings/controller mappings, compiled from the retained platform source.

Exact configuration and tooling manifests:
`smoke-07/cache-configuration.json` SHA256
`09828bb7b8f2c1f4737f95a04cecf2a2fbcf515b8e252e90dc689de834aa7887`;
`smoke-07/tooling.json` SHA256
`21cab631510d93123928a729aa605e905e648a15922aaef876feb20e4574c2a8`.
Final result SHA256
`95f70873a5ac71179fa77dd289a543304c3f05bb2cfab30910bcd066e1b0a00f`.
The index binds every relevant request/response, cache/image witness, pre/post
installed-file origins, loaded native settings, source snapshot and stop outcome.
The runtime command is in [the recipe](../../build-support/gwc/README.md); use a
new output name, never reuse `smoke-07`.

GeoNode, GeoServer, HTTP client and Pillow decoder run under the unchanged
trusted-fixture loopback supervisor: 79 parent + 79 exec-child probes pass,
zero UDP packets, task group stopped and broker sockets closed. PostgreSQL alone
uses the previously documented SCRAM/loopback exception for native `setsid`.
Both phases' GeoServer/GeoNode processes stopped normally on requested termination;
PostgreSQL exited zero. Native stored credentials were invalidated; private config,
key, server/database credentials were scrubbed. Diagnostic secret/security hit
counts are zero. These are not hostile-code, full filesystem or whole-host
isolation proofs. Original caches and prior attempts remain untouched.

Fresh harness checks: **59** image/cache/HTTP/integrity regressions, **4** runtime
input checks, **7** configured-fixture checks, **15** supervisor regressions;
all pass without skips. From the actual `plan/` using the verified IDE validation
venv: **203 package tests** and **four strict schemas/examples** pass. Package
checks are not GIS tests. The real 30 HTTP requests and ten decoded PNG assertions
are separate evidence. Unchanged full Java, GWC native, GeoNode, database,
frontend, QGIS and Jupyter suites were not repeated.

Preserved failures: `smoke-01` documented `.xml` GWC route 404; `smoke-02`
no-extension route still 404; `smoke-03` file-only prefix still 404; `smoke-04`
real public MISS/HIT but failed overly narrow OWS-only private-denial classifier;
`smoke-05` completed initial tile controls but failed pre-start security inventory
comparison; `smoke-06` failed lazy generated users.xsd inventory comparison.
All six remain exit1 with cleanup receipts. The final guard compares every original
security input plus the fully initialized active set across requests/restart.
Independent negative tests also retained pre-repair failures for wrong geometry,
wrong-layer/coordinate cache evidence, misleading exceptions and a login form.
All material findings were repaired; the final independent review has no open
bounded harness finding. This does not replace owner security review.

## Historical owner-checkpoint handoff (accepted in #64)

The review request below is preserved checkpoint history. F02-06 now proceeds in
[the candidate proposal](fnd-02-candidate-proposal.md); it creates no new smoke gate.

Review this new PR/head's fixture route/security configuration, native cache and
protected-tile evidence, generated-file integrity guards, failures and precise
reuse limits. Prior #63 acceptance covers F02-04 only. Owner review gates merging
this new checkpoint; it does not block independent F02-06 engineering. This slice
does not merge, deploy, release or change source-fork defaults/workflows/secrets.

The next finite row is **F02-06**: consolidate the exact candidate source/runtime/
dependency proposal and explicit source/license selection decisions; then F02-07
maintenance binding and F02-08 final acceptance. QGIS resource rights, frontend
web-ifc/notice findings, five lint errors and the distinct Java ledger remain
unchanged blockers/decisions. Neither recorded limits nor successful caching
confers source viability, legal clearance or redistribution permission.

[Project publication/readback](../verification/combination-gwc/project.json)
verified **76 → 77 items** with exactly two writes: add #64 by content identity
and set its Evidence link to #64/issue #3. All 76 prior items, represented fields,
archive decisions, repository links and saved-view configuration/order were
preserved; no Task ID/Delivery/Review gate was copied. FND-02 Delivery stays
In progress; only #64 matches the unchanged `is:pr is:open` queue. No importer or
GOV-02 setup was rerun. This is complete API readback, not a new UI acceptance.
The publication snapshot records head `c4a515bdb2475ee1fb9a363d5e9be7ad9e714ae5`;
subsequent publication-documentation commits preserve the tested implementation.
The final issue evidence comment pins the final pushed review head.
