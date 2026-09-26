# Changes from donor — accepted revision 4 source materialization

This consolidated platform ledger records the exact permanent core changes replayed
for FND-07. Original source ancestry and notice files remain intact. The immutable
candidate and [full commit/tree/bundle plan](../../plan/verification/source-baseline-restore/promotion-plan.json)
supply exact identities. These local commits are awaiting public branch and human
review approval; they are not upstream releases or distribution permissions.

## aloerch/ambisgis-postgresql

Unchanged accepted implementation. Build-generated files remain in the original database recipe.

Accepted base `2ff1375b5dd8bf09d8cb0e795974528180fd75ca`. Local product `2ff1375b5dd8bf09d8cb0e795974528180fd75ca`; tree `598df31816bda464f5b904c0badbcb25bafcc4f1`.

No tracked source changes.

## aloerch/ambisgis-postgis

Unchanged accepted implementation. Autogen/build outputs remain derived, not unexplained new source.

Accepted base `9816f82458db774e62906cfb2c4f01f8b262c862`. Local product `9816f82458db774e62906cfb2c4f01f8b262c862`; tree `ee927efacdc5a00d698cab2da047ad2232d1f579`.

No tracked source changes.

## aloerch/ambisgis-qgis

Unchanged editable core source. The platform regenerates 307 GRASS records and selects exact resources/notices with 1,130 palette exclusions; generated/packaged outputs stay separate.

Accepted base `1a4cda5f2620e7374e5926fc955a7d2d06493e15`. Local product `1a4cda5f2620e7374e5926fc955a7d2d06493e15`; tree `c8542e82e3c3810950f32ce8d58a16bfed12e6c8`.

No tracked source changes.

## aloerch/ambisgis-jupyterhub

Preserve five owned runtime-data files in archive packaging using the accepted MANIFEST.in additions.

Accepted base `3e516c6f382b481e815ec455befb2f14d80d337b`. Local product `129e6b0a06dcf1aa17b580bf0f0a61dfd9dbce3a`; tree `a9ab20c5ff0641870194d666fcd1516ee2f2d65e`.

```text
M	MANIFEST.in
```

## aloerch/ambisgis-jupyterlab

Unchanged editable core source; frontend generation and wheel packaging remain identified in the accepted recipe.

Accepted base `e7255a9334c12ad8f9cb15db27584215fab5ece2`. Local product `e7255a9334c12ad8f9cb15db27584215fab5ece2`; tree `0edadc56fb04f944097c0658a9a51686ba68bd16`.

No tracked source changes.

## aloerch/ambisgis-geotools

Replay the guarded XML code-generation and NO-ORACLE source profile repairs.

Accepted base `aac73e9b89821331e77f67f1dd0921e541a78cfc`. Local product `f51fa68803c465f28a85c155e3e951df0d8788f7`; tree `60750f787dabf1a08e646e7d5f3f1497e560e94e`.

```text
M	build/maven/xmlcodegen/pom.xml
M	modules/plugin/imagemosaic/pom.xml
```

## aloerch/ambisgis-geowebcache

Replay the accepted aggregate dependency/profile preparation.

Accepted base `59640420454b73f1e04e8409cc6ed43f4b24fed2`. Local product `b4e9a30c8e2be00b9aa87fb17324efa8e489ac22`; tree `8df655d13b9955776fe1532dfb27fac64612a772`.

```text
M	geowebcache/diskquota/jdbc/pom.xml
```

## aloerch/ambisgis-geoserver

Replay accepted aggregate lifecycle, OAuth, configured authorization/stateless role-service and NO-ORACLE/NO-JPEG2000 guarded changes.

Accepted base `e0673323400321c0f3409fbae68b4871dc328d8a`. Local product `fd2fe1dfcc78fa974bdb81673872879336312077`; tree `c12018e88493a351c60c370f2a43894701acf995`.

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

## aloerch/ambisgis-geonode

Replay accepted headless dependency selection, opaque-token verification and role-service repairs.

Accepted base `a1db97e81dfc26c16bb4ee1a5d2b408877af66c9`. Local product `2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4`; tree `f8fda01733dae258e319df14f42677cf3bd83e20`.

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

## aloerch/ambisgis-mapstore-client

Replace floating project dependency with a retained local archive; bind the nested MapStore gitlink to the actual local product source commit.

Accepted base `7ca4822125b67999c97cb4aa1faa84b8a28eee9b`. Local product `a0d3f434cea69dadc93d35e13bc969b844aceea1`; tree `8055ca37333ee3037f63624f2e1d6ee548d416f1`.

```text
M	geonode_mapstore_client/client/MapStore2
M	geonode_mapstore_client/client/package.json
```

## aloerch/ambisgis-mapstore

Replace floating Patcher declaration with the retained local archive.

Accepted base `0f3518737f29f4049b131247ce981e94519d9ab0`. Local product `88064efbf20ef0aaffebe357f7a99a1ab4fb23b8`; tree `11b6eb8616b90c72570c4f3aad82212b52f1cdbe`.

```text
M	package.json
```

## Platform-maintained dependency sources

The [source summary](../../plan/verification/source-baseline-restore/source-summary.json)
and restored recipe receipt map AspectJ, XMLPull, the independently authored JSON
adapter, Jackson/FastDoubleParser, Marlin, ImageIO, GeoFence/MapFish, frontend local
inputs and web-ifc plus eight dependency sources. Permanent variants are maintained
through platform recipes/patches under the Class B vendor policy in ADR 009. Their
actual terms and original notices survive; historical excluded JSON/JJ2000 code
is custody material only. No new public fork, copyright transfer or blanket license.

Verification is source recovery, guarded source/output comparisons, ancestry,
assets and actual offline bundle-chain restoration. Existing exact-WAR/runtime
evidence is linked through the accepted candidate; no runtime suite is relabeled
as newly run. Security, distribution, full build/repair and release gates remain.
