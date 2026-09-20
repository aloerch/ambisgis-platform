# ADR 004 — Exercise recovered Java source and bounded compatibility repairs

Status: FND-02 engineering experiment. Source, license/security, product baseline
and release approvals remain open. This extends ADR 003; it does not turn its
retained dependency graph into a complete source build.

The source-closure supplement accounts for all 64 recorded missing Maven source
classifiers. Each exact binary identity retains declarations/acquisition evidence,
observed test-classpath evidence where available, source revision and archive
hashes, original notice/header evidence, attempted recovery and remaining work.
SourceFile/package/declaration mapping is structural evidence. Generated inputs
and metadata-only packages have separate dispositions. No filename mapping,
embedded binary, empty classifier or similarly named release proves a reproducible
binary. Source recovery remains separate from final legal approval.

Use fresh disposable source/repository copies from the exact retained owned
archives. The compatibility runner selects bounded targets and checks toolchain,
source, input and resulting artifact hashes. All Java executions deny IPv4/IPv6
sockets. The available host refuses a new user/network namespace, so real TCP
fixture tests remain blocked until a controlled loopback-only environment is
available. Excluding unrelated reactor tests to reach a named component is
explicit target selection, never evidence that the excluded tests passed.

The MapFish 2.4.1 candidate still uses ADR 003's GeoTools 34.5 override. Its build
exposed missing dependency management in the owned GeoTools xmlcodegen Maven
plugin: that module does not inherit the platform BOM. A hash-guarded patch adds
`org.eclipse.emf.common` and `org.eclipse.emf.ecore` 2.15.0 to the plugin's own
dependency management, matching the existing platform BOM. The patch is retained
in `build-support/java/compatibility-patches/xmlcodegen-emf.patch` and applied only
to disposable source copies. It repairs concrete compilation prerequisites; it
does not accept the printing candidate or waive its failing rendering fixtures.

GeoFence's PostgreSQL tests use the retained owned PostgreSQL/PostGIS build,
verified against its existing artifact receipt. A fresh private cluster listens
only on its private Unix socket. A test-only JDK17 SocketFactory carries the
original PostgreSQL JDBC protocol over AF_UNIX with no TCP fallback. The fixture
changes only the disposable test connection and test compiler release; original
model/persistence tests remain intact. Its socket adapter does not emulate
SO_TIMEOUT; the parent imposes a finite process timeout and stops the cluster.
Passing these tests is component compatibility evidence, not canonical policy,
branch authorization or managed-geodatabase acceptance.

The importer fixture verifies the retained owned database/GDAL output archive
and its installed files, stages only gdal_translate/gdaladdo/gdalwarp, and uses
those tools for the original raster-transform tests. This reuses verified
outputs without repeating historical database native suites. Host/native closure
remains separate; Oracle/SQL Server fixtures remain explicit skips.

The SLF4J witness demonstrates the actual failure of API 2.0.17 with a legacy
1.x binder and a functioning retained Log4j 2.25.3 SLF4J2 provider. This does not
silently rewrite the aggregate product graph. A later controlled service build
must select one API/provider deliberately and test its actual packaged classpath.

Recovered Huldra and JavaCSV sources are compiled with the retained JDK and run
against their original native tests. JavaCSV's historical CRLF setting is explicit;
its Linux-default failures remain visible and reproduce against the original
binary. JGridShift source compilation/public-API comparison is narrower because
its retained core tree has no native tests. Marlin's missing OpenGL source remains
partial after an actual compile/disassembly mismatch; preceding source is not
substituted as exact release source.

Required service/metadata administration, branch editing, portal/apps, notebooks
and QGIS publishing remain unchanged. [Profile decisions](../docs/java-profile-decisions.md)
keep importer, OAuth, GeoFence/PostgreSQL and printing selected and explain the
bounded WPS exclusion. The inherited bootstrap is not activated. Schema archive
inspection and passing resolver tests do not complete owned repackaging or
file-level rights. All previous archives and unsuccessful runs remain retained.

No owner decision is needed to continue independent source recovery and bounded
fixtures. Merging these checkpoint PRs requires separate owner approval; final
security, license/brand, migration, signing and deployment gates remain separate.
