# Exact FND-07 source-publication notice and disposition

**Delivery condition:** This notice, its original license/notice files and the exact publication evidence must be publicly available and byte-verified before creating any row marked publishable. The delivery announcement must link this companion alongside the source refs. This document alone does not claim remote publication, workflow disablement, product acceptance or a release.

The immutable PR #69 plan is SHA256 `a9477bbdcab4f85fad69cbf77ed04ed76de92efd63d3d663054bda34e4b573a6` at `1e5712e0ba3f931205d9b9be1d4a34e076ce1b87`. The only source destination is `refs/heads/ambisgis/review/fnd-07-baseline-v4`, with each approved commit/tree unchanged. Nine rows have a scoped publication basis; QGIS and GeoTools remain held. Owner authorization, creation-only ref handling and verified workflow containment remain separate mandatory gates.

## Scope and existing public source

The [authoritative evidence](authoritative-evidence.json) binds the fresh [owned-fork readback](preflight-initial.json), exact public base witnesses, source grants, changed objects and notices. Every accepted base was already publicly reachable on its owned fork. Object counts below are upper bounds relative to a proved public commit, not proof of unrestricted rights or comparison against every public ref. Source history and all original notices stay intact.

| Root | Disposition | Approved commit | Approved tree | Additional object upper bound |
|---|---|---|---|---|
| postgresql | Publishable after companion delivery | `2ff1375b5dd8bf09d8cb0e795974528180fd75ca` | `598df31816bda464f5b904c0badbcb25bafcc4f1` | 0 |
| postgis | Publishable after companion delivery | `9816f82458db774e62906cfb2c4f01f8b262c862` | `ee927efacdc5a00d698cab2da047ad2232d1f579` | 0 |
| qgis | HELD | `1a4cda5f2620e7374e5926fc955a7d2d06493e15` | `c8542e82e3c3810950f32ce8d58a16bfed12e6c8` | 0 |
| jupyterhub | Publishable after companion delivery | `129e6b0a06dcf1aa17b580bf0f0a61dfd9dbce3a` | `a9ab20c5ff0641870194d666fcd1516ee2f2d65e` | 3 |
| jupyterlab | Publishable after companion delivery | `e7255a9334c12ad8f9cb15db27584215fab5ece2` | `0edadc56fb04f944097c0658a9a51686ba68bd16` | 0 |
| geotools | HELD | `f51fa68803c465f28a85c155e3e951df0d8788f7` | `60750f787dabf1a08e646e7d5f3f1497e560e94e` | 10 |
| geowebcache | Publishable after companion delivery | `b4e9a30c8e2be00b9aa87fb17324efa8e489ac22` | `8df655d13b9955776fe1532dfb27fac64612a772` | 6 |
| geoserver | Publishable after companion delivery | `fd2fe1dfcc78fa974bdb81673872879336312077` | `c12018e88493a351c60c370f2a43894701acf995` | 94 |
| geonode | Publishable after companion delivery | `2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4` | `f8fda01733dae258e319df14f42677cf3bd83e20` | 13 |
| mapstore-client | Publishable after companion delivery | `a0d3f434cea69dadc93d35e13bc969b844aceea1` | `8055ca37333ee3037f63624f2e1d6ee548d416f1` | 5 |
| mapstore | Publishable after companion delivery | `88064efbf20ef0aaffebe357f7a99a1ab4fb23b8` | `11b6eb8616b90c72570c4f3aad82212b52f1cdbe` | 3 |

The unchanged PostgreSQL/PostGIS/JupyterLab rows retain their applicable source grants and original notices. JupyterHub changes only its archive membership declaration under its preserved BSD terms. MapStore changes only a dependency declaration under preserved BSD terms. Source-fork refs do not contain the entire product composition. GeoServer has no Git submodule entries and its exact delta introduces no owned GeoTools commit/ref; its changed POMs remove the Oracle dependency and exclude Oracle UI compilation. GeoTools remains a required retained platform-composition input, with its public review ref held. Independent GeoServer Git-root delivery is not represented as a complete build or complete eleven-root delivery. The MapStore client, in contrast, has an exact required child gitlink and must wait for its owned MapStore commit to be published. Existing Class B sources, platform adapters/recipes and private retained assets remain independently required. Historical excluded JSON/JJ2000 custody archives are not added by any approved product delta. No new claim that every historical file was semantically audited is made.

## Prominent notice of AmbisGIS source modifications

**AmbisGIS source recovery modified the files below on 22 September 2026**, materializing the already reviewed candidate. Exact commit metadata and the [donor-change ledger](../../../build-support/source_restore/CHANGES_FROM_DONOR.md) preserve provenance. The ledger is at repository root `build-support/source_restore/CHANGES_FROM_DONOR.md`; this dated notice accompanies Git delivery and does not alter any approved source tree.

For GeoServer and GeoNode, this scoped source delivery follows GPL3 under existing applicable version-or-later grants. GeoServer's root `LICENSE.md` expressly permits GPL2 or later; its sixteen modified inherited Java headers refer to that root grant, and both new NO-JPEG2000 files state GPL2-or-later. GeoNode's root GPL2-or-later grant and applicable GPL3-or-later file notices remain intact. GeoWebCache retains its LGPL3 grant, incorporating GPL3. This is exercise of existing options, not replacement of original grants or blanket licensing of third-party material. GeoServer's EMF/XSD/OSHI exception remains intact.

The verbatim [GPL3 text](notices/gnu/GPL-3.0.txt) and [LGPL3 text](notices/gnu/LGPL-3.0.txt) accompany this notice. GNU GPL3 sections 4, 5 and 14 provide the relevant preserved-notice, dated work-level modification and existing later-version rules; the [official GNU-hosted text](https://gcc.gnu.org/onlinedocs/gcc/Copying.html) is also available. This source-only interpretation does not imply aggregate binary, security, trademark or product-release clearance.

### aloerch/ambisgis-geowebcache

Approved source commit `b4e9a30c8e2be00b9aa87fb17324efa8e489ac22`; recorded change date `2026-09-22T16:42:17-07:00`.

```text
M	geowebcache/diskquota/jdbc/pom.xml
```

### aloerch/ambisgis-geoserver

Approved source commit `fd2fe1dfcc78fa974bdb81673872879336312077`; recorded change date `2026-09-22T16:42:17-07:00`.

```text
M	src/community/security/oauth2-geonode/src/main/java/org/geoserver/security/oauth2/services/GeoNodeTokenServices.java
M	src/community/security/oauth2/oauth2-core/src/main/java/org/geoserver/security/oauth2/GeoServerOAuth2FilterConfig.java
M	src/community/security/oauth2/oauth2-core/src/main/java/org/geoserver/security/oauth2/GeoServerOAuthAuthenticationFilter.java
M	src/community/security/oauth2/oauth2-core/src/main/java/org/geoserver/security/oauth2/GeoServerOAuthRemoteTokenServices.java
M	src/extension/authkey/src/main/java/org/geoserver/security/GeoServerRestRoleService.java
M	src/extension/authkey/src/main/java/org/geoserver/security/GeoServerRestRoleServiceConfig.java
M	src/extension/importer/core/pom.xml
M	src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/ImportTaskController.java
M	src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/ImportContextJSONMessageConverter.java
M	src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/ImportDataJSONMessageConverter.java
M	src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/ImportLayerJSONMessageConverter.java
M	src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/ImportTaskJSONMessageConverter.java
M	src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/ImportTransformJSONMessageConverter.java
M	src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/TransformChainJSONMessageConverter.java
M	src/extension/importer/web/pom.xml
M	src/extension/importer/web/src/main/java/org/geoserver/importer/web/ImportDataPage.java
A	src/main/src/main/java/org/geoserver/filters/NoJpeg2000Filter.java
A	src/main/src/main/java/org/geoserver/filters/NoJpeg2000Policy.java
M	src/main/src/main/java/org/geoserver/security/auth/GuavaAuthenticationCacheImpl.java
M	src/restconfig/src/main/java/org/geoserver/rest/catalog/CoverageStoreFileValidator.java
M	src/web/app/src/main/webapp/WEB-INF/web.xml
```

### aloerch/ambisgis-geonode

Approved source commit `2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4`; recorded change date `2026-09-22T16:42:17-07:00`.

```text
A	geonode/api/backend_roles.py
A	geonode/api/backend_tokeninfo.py
A	geonode/api/test_backend_roles.py
A	geonode/api/test_backend_tokeninfo.py
M	geonode/api/views.py
M	geonode/security/middleware.py
M	geonode/settings.py
M	pyproject.toml
```

## MapStore client: inherited executable source availability

Approved client commit `a0d3f434cea69dadc93d35e13bc969b844aceea1` retains 956 tracked `geonode_mapstore_client/static/mapstore/dist/` files and 34 `ms-translations/` files. Their removal from the private frontend build assembly never removed them from this Git tree. They are inherited from an already-public base; the new commit changes only `package.json` and its MapStore gitlink. Existing public availability is not the publication-rights basis.

**Recipients of the following unchanged Web-IFC 0.0.50 executable files may obtain their exact reviewed covered source, original MPL2 terms and source build scripts at the immutable public links below.** The source is available under its original Mozilla Public License 2.0 and original applicable third-party terms. No fee, new external agreement or private archive request is needed to access those public sources.

| Path under `geonode_mapstore_client/static/mapstore/dist/js/web-ifc/` | Git blob | SHA256 |
|---|---|---|
| `web-ifc-mt.wasm` | `7c4a7ebe9393f67418be1665452d5bf4c4abe283` | `797f6e0be82d95c22292894e8c9c8e8e70eb46d20b519b3f081a8df1e91208ca` |
| `web-ifc-node.wasm` | `2c0ca1ec530e4e04be74618a3e66d38f4a55672b` | `94e1927131654a4288f8b868f33766c33979a8290d019ad3b9def7f40a0afbd6` |
| `web-ifc.wasm` | `2c0ca1ec530e4e04be74618a3e66d38f4a55672b` | `94e1927131654a4288f8b868f33766c33979a8290d019ad3b9def7f40a0afbd6` |

These exact hashes match accepted [Web-IFC evidence](../frontend-qgis-remediation/webifc-evidence.json). The current public source tree, build scripts and MPL notices were checked against the previously accepted hashes; evidence records exact endpoints, times and Git object identities. The main CMake script pins all eight supporting revisions.

| Source | Exact source endpoint |
|---|---|
| webifc | [b55d8bde10067415d4536b23c27edcc13acf217c](https://github.com/ThatOpen/engine_web-ifc/tree/b55d8bde10067415d4536b23c27edcc13acf217c) |
| fastfloat | [2b2395f9ac836ffca6404424bcc252bff7aa80e4](https://github.com/fastfloat/fast_float/tree/2b2395f9ac836ffca6404424bcc252bff7aa80e4) |
| tinynurbs | [2fc6562d71665312c6298f7c340bace1bcf1b7a1](https://github.com/pradeep-pyro/tinynurbs/tree/2fc6562d71665312c6298f7c340bace1bcf1b7a1) |
| tinycpptest | [12e42c8ac6e032ce450fb3f772ebdfd1ddc6008c](https://github.com/kovacsv/TinyCppTest/tree/12e42c8ac6e032ce450fb3f772ebdfd1ddc6008c) |
| glm | [bf71a834948186f4097caa076cd2663c69a10e1e](https://github.com/g-truc/glm/tree/bf71a834948186f4097caa076cd2663c69a10e1e) |
| earcut | [4811a2b69b91f6127a75e780de6e2113609ddabb](https://github.com/mapbox/earcut.hpp/tree/4811a2b69b91f6127a75e780de6e2113609ddabb) |
| cdt | [4d0c9026b8ec846fe544897e7111f8f9080d5f8a](https://github.com/artem-ogre/CDT/tree/4d0c9026b8ec846fe544897e7111f8f9080d5f8a) |
| spdlog | [7e635fca68d014934b4af8a1cf874f63989352b7](https://github.com/gabime/spdlog/tree/7e635fca68d014934b4af8a1cf874f63989352b7) |
| fuzzy | [28251ebc68144e9b4613e0c289304c040e01ccf8](https://github.com/tomvandig/fuzzy-bools/tree/28251ebc68144e9b4613e0c289304c040e01ccf8) |

At the Web-IFC revision, [`src/wasm/CMakeLists.txt`](https://github.com/ThatOpen/engine_web-ifc/blob/b55d8bde10067415d4536b23c27edcc13acf217c/src/wasm/CMakeLists.txt), [`Dockerfile`](https://github.com/ThatOpen/engine_web-ifc/blob/b55d8bde10067415d4536b23c27edcc13acf217c/Dockerfile), `package.json`, `package-lock.json` and `.github/workflows/publish.yml` preserve the historical source build declarations. The Dockerfile names Emscripten 3.1.44; no execution of that Dockerfile, network bootstrap or independent WASM rebuild is claimed here. Exact source custody remains retained locally under the accepted composition; public donor URLs provide recipient source access, not AmbisGIS build authority.

Original accompanying terms: [Web-IFC MPL2](notices/webifc/LICENSE.md), [CDT MPL2](notices/cdt/CDT/LICENSE), [fuzzy-bools MPL2](notices/fuzzy/LICENSE.md), [fast_float Apache](notices/fastfloat/LICENSE-APACHE)/[Boost](notices/fastfloat/LICENSE-BOOST)/[MIT](notices/fastfloat/LICENSE-MIT), [TinyNURBS](notices/tinynurbs/LICENSE), [TinyCppTest](notices/tinycpptest/LICENSE.md), [GLM](notices/glm/copying.txt), [earcut](notices/earcut/LICENSE), [spdlog](notices/spdlog/LICENSE), [bundled fmt](notices/spdlog/include/spdlog/fmt/bundled/fmt.license.rst) and [fuzzy bundled GLM](notices/fuzzy/deps/glm/copying.txt). Their bytes and origins are bound in `authoritative-evidence.json`; original alternatives, attributions and disclaimers remain. Inclusion of supporting/test notices is not a claim that every listed file is compiled into each WASM.

MPL2 [sections 3.1/3.2/3.4](https://www.mozilla.org/en-US/MPL/2.0/) require usable covered source access, recipient notification and original-notice preservation. Mozilla [FAQ Q7](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) addresses unchanged executable redistribution and additional notice duties for libraries. This companion is supplied with the exact Git delivery announcement to meet the concrete recorded source-availability condition. It must remain publicly accessible alongside the delivery record; an internal-only ledger is insufficient. Source/byte/binding correspondence is established; an independently byte-identical WASM rebuild, complete compiler/runtime closure and broader binary release remain unclaimed.

The client gitlink must resolve to the separately published owned MapStore commit `88064efbf20ef0aaffebe357f7a99a1ab4fb23b8`. Its unchanged `.gitmodules` still names `https://github.com/geosolutions-it/MapStore2.git`, branch `geonode-5.1.x`. Remote recovery therefore uses an explicit bounded mapping to `https://github.com/aloerch/ambisgis-mapstore.git`; ordinary donor-recursive cloning is not represented as self-contained.

## QGIS publication hold

Commit `1a4cda5f2620e7374e5926fc955a7d2d06493e15` is unchanged and already public at the selected tag, but its exact source tree retains all 1,130 palettes excluded from the tested resource package. Preserve the [existing file-level findings](../../docs/qgis-dependency-audit.md) and [one-file GMT exclusion](../../docs/java-gmt-qgis-handoff.md). Neither package exclusions nor this source-ref authorization grants new rights to those assets. All paths below begin `resources/cpt-city-qgis-min/`.

| Scope / count | Exact notice or asset blob | Reason |
|---|---|---|
| `jjg/ccolo/evad/COPYING.xml` / 256 | `131ebb7c3e70fb8bf1822c84c2ec6e1a94bf03f1` | Nineteen collection notices apply CC BY-NC-SA 3.0; intended public source context needs an applicable noncommercial/permission basis. |
| `jjg/neo10/COPYING.xml` / 135 | `71e2bf3e4d5e62268eb07d01ced3ce0a4b5561c1` | Free-to-use notice marks distribute=no; adequate public redistribution grant not established. |
| `td/COPYING.xml` / 3 | `b2f257a4d4419bc115e4635e7fa9b568fbc78cb4` | Free-to-use/none-specified notice marks distribute=no; adequate public redistribution grant not established. |
| `gmt/GMT_dem1.svg` / 1 | `92b800f48b2d6c4c42ffa3298c92182f8e581d17` | Exact duplicate/provenance uncertainty recorded by accepted one-file exclusion; no new permission inferred from matching bytes. |
| `es/COPYING.xml` / 690 | `f417f430eed60109ab324ad3977099e523b1332e` | Custom redistribution requires credit, original preview/name and collection conditions; historical approval link not established. |
| `jm/COPYING.xml` / 45 | `54d6260e01e94b19aaa9fd9667b0889de0b1c685` | Full agreement includes personal/nontransferable and client-internal-use language; source-transfer applicability remains unresolved. |

The ccolo row is a representative notice for nineteen scopes. CC BY-NC-SA3 [actual conditions](https://creativecommons.org/licenses/by-nc-sa/3.0/legalcode) do not establish rights for the other collections. Existing ColorBrewer acknowledgement/naming conditions and QGIS icon notices remain unchanged; they are not the reason to broaden this hold.

**Smallest remedy:** authoritative permission/applicability and applicable attribution evidence for these exact source-publication scopes; otherwise a separately reviewed source-tree/history plan. Retain the current commit and bundle. Do not delete palettes, rewrite history, upload first, or invent permission from donor visibility.

## GeoTools publication hold

Commit `f51fa68803c465f28a85c155e3e951df0d8788f7` modifies `build/maven/xmlcodegen/pom.xml` and `modules/plugin/imagemosaic/pom.xml`. Their exact new blobs are `f6e454a420d20ca201cbd27d23200c342beee655` and `ea80b3e4578df9f2db8348ece5d851b10c24d9b0`. Root `pom.xml` declares **LGPL-2.1-only**; `docs/user/welcome/license.rst` specifies version 2.1.

LGPL2.1 section 2(b) requires modified files to carry prominent change/date notices. The preserved Git commit is dated, and the external donor-change ledger identifies both paths, but the two POMs lack added in-file change/date notices. No authoritative interpretation established that a companion in another repository satisfies this file-specific requirement. The work-level GPL3 reasoning above is not silently applied to an LGPL2.1-only grant.

**Smallest remedy:** authoritative confirmation that this exact existing Git/file-history notice arrangement satisfies the clause, or separate review/authorization of a narrowly changed commit adding the required notices. Retain the approved commit and bundle; no changed SHA is substituted under this plan.

These two holds do not reopen FND-02 selection or add FND-08 builds as a prerequisite for independently supportable rows. All eleven exact identities, publication scope, operational gates and final FND-07 acceptance remain separate.
