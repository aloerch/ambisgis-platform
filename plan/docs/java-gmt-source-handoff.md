# F02-06 coordinated Java source variants

This is component evidence inside the new proposed Java/GMT **NO-ORACLE**
candidate, based on owner-merged #66. FND-02 remains In progress. The current
owner prompt separately authorizes these local variants; no source adoption,
license clearance, distribution, merge or release is implied.

The [compact evidence index](../verification/java-gmt-remediation/source-evidence.json)
binds original JARs, recovered source, author notices, recipes, all attempts,
source/output manifests and actual probes. Original sources and publisher binaries
remain untouched. The aggregate importer uses explicit content-pinned local
mappings; the replacement filenames and embedded metadata identify new variants.
No modified binary was published into a donor namespace.

| Target | New source/output and compatibility | Remaining condition |
|---|---|---|
| F02-JAVA-aspectj154 | Complete retained release tree `b50c23b0a214e315791677a5bfef990db271ecd9`, all runtime/weaver Java5 roots and embedded BCEL sources compiled with retained Temurin17. Only JRockitAgent is omitted; its five unavailable BEA classes are never copied. Runtime/weaver classes are partitioned without duplicates. | Final exact-WAR GeoFence/PostgreSQL persistence, transaction proxy, commit and rollback checks pass. Configured HTTP authorization remains aggregate evidence. Java7+ **load-time** weaving remains unsupported; both publisher and new build reject its invalid stackmaps. |
| F02-JAVA-xmlpull1131 | Exactly four API files from the publisher's `xpp3:1.1.4c` source archive, SHA `113c8174cda963aa8c9e46f59945838dbe1a094cc736e476d640453e07d9e9c6`; public signatures match 1.1.3.1 exactly. Original author dedication recovered from the authoritative XMLPull site. | Original binary/source equivalence is not claimed. Actual finalWAR MXParser/XStream tests pass; deployed service evidence remains separate. |
| F02-JAVA-json-lib | All 51 production sources from `fernandor777/Json-lib` revision `1ff8dc03730cb00afb4628350f3106f35c122d34` compiled as a distinct **2.4.1-derived** variant. APIs, 213 serialization/parsing/shape/depth contracts match original 2.4.2. | **Adoption blocked:** exact historical JSON-derived permission chain remains unresolved. Apache headers/POM plus seven `@author JSON.org` attributions do not establish that chain. Actual aggregate WFS/REST/OAuth/role tests are recorded separately. |

AspectJ's all-369-library scan found BEA/JRockit references only in the original
weaver's adapter and BEA classes. No retained production consumer selects that
adapter. GeoFence's inspected `applicationContext.xml` has its
`aspectj-autoproxy` line commented; no required aspect is bypassed. Effective
public API comparison checks **788 classes, 20,387 method contracts and 5,131
fields**, including inherited methods. Raw `javap` text differs because javac
and the historic compiler emit different inherited/bridge/enum members; the
actual effective contracts pass. A real Spring AspectJ advice invocation also
passes. Runtime version metadata explicitly identifies the AmbisGIS source build.

The XMLPull author notice was recovered from
[the original dedication](https://www.xmlpull.org/v1/download/unpacked/LICENSE.txt),
SHA `4eeafa29d1d9a0cdbdad0f5178cd553527329b57b5808ffe912cb9c698343612`.
It names Stefan Haustein and Aleksander Slominski and excludes tests from its
public-domain dedication. This is positive terms evidence, not an inference from
missing notices. The source archive contains all four APIs. The new JAR packages
only those APIs and the dedication; it does not add a second provider. Actual
factory discovery selects the unchanged `io.github.xstream.mxparser.MXParser`.
Explicit provider loading, malformed XML, absent providers/serializer,
namespace handling, XStream round-trip and forbidden-class denial pass.

The JSON source archive SHA is
`221c662bbafa7f722746c00f625ae7f30c06354be0d8eccfa0ca363c747bf14b`.
Its POM explicitly identifies 2.4.1-geoserver and credits Douglas Crockford.
The complete Apache license, original headers and seven JSON.org attributions
are retained, with an explicit notice describing the unsatisfied historical
permission condition. The prior incorrect-release candidate remains rejected as
exact 2.4.2 provenance. No relabeling or general JSON-stack rewrite occurred.
The tested source requires no compatibility repair: builder depth remains 100 by
default, 8 when configured to 8, and 100 for zero/invalid settings. Nulls, numeric
values, escaping, Unicode, JSON round-trips and bounded WFS/REST/OAuth/role-shaped
values agree with the publisher JAR. These shape checks do not substitute for
actual HTTP contract tests.

`source/build-01` produced these frozen outputs:

| Output | SHA-256 |
|---|---|
| aspectjrt-1.5.4-ambisgis-temurin17-1.jar | `5bf41bf5474d618423d2a6d8042468cf4e7e57db8895604f205d75fe61d5090b` |
| aspectjweaver-1.5.4-ambisgis-temurin17-1.jar | `e35095ad483cc38a2cf17777f74f9a59abafed1fcabc7cf951b1fbf8153370d6` |
| xmlpull-1.1.3-api-ambisgis-xpp3-source-1.jar | `fb4f2393e1cdf1c078a7800312eac6d1392ebd27c3015d06c25401d3bd705573` |
| json-lib-2.4.1-ambisgis-source-1.jar | `92c744bdb2ed2a6ff255af473f271bf3954e00ab037ed5649a39056eeab2fbf2` |

All build and Java probe commands ran under the existing process-local socket
denial wrapper with verified AF_INET/AF_INET6 failures. Trusted host files and
AF_UNIX remain the documented containment limits. Only fresh, supervised PostgreSQL fixtures were started for the native and exact-WAR persistence checks; both were stopped. The established AF_UNIX-only fixture uses no external database or generated secret. The supervising database process is the documented socket-denial exception. Compile inputs include retained
optional Groovy/XOM/ORO APIs so all original JSON public classes compile; their
sources, original notices and retrieval receipts are indexed. Those optional
libraries were **not added to the production WAR**. Full independent toolchain
rebuilding and distribution notice reconciliation remain later gates.

`source/probe-05` ran **359 unchanged native JSON tests: 357 passed, two failed**.
The two `TestJSONObject` tests request the JavaBean `class` property suppressed by
the selected modern Commons BeanUtils. Both failures reproduce against original
2.4.2 using identical dependencies; the security suppression was not weakened.
The failed tests remain failures, not skips. The other five selected native
classes pass. All 225 focused JSON/XML/proxy assertions and the effective API
comparison pass. Genuine ECJ-generated Java5 bytecode is successfully transformed
at load time and its advice executes under normal Temurin17 verification.
The test-only `--add-opens java.base/java.lang=ALL-UNNAMED` is explicit; neither
`-noverify` nor classfile-header alteration is used. Java7-target LTW fails in
both baseline and variant and remains preserved in `probe-01`.

`source/war-probe-02` freshly passed against final aggregate-02 WAR
`e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044`.
It verifies each mapped JAR/source-manifest hash, every target class origin,
absence of duplicate AspectJ/XMLPull/JSON definitions and post-run integrity.
The 213 JSON, 10 XML/XStream and two real AspectJ advice assertions plus actual
legacy LTW use only libraries freshly extracted from that exact WAR.
Its result SHA is `96460c76522ec815d94bb5c27616bbdeb7eacbc22575d6e4a5f6d84086b511bb`.
The earlier aggregate-01 result remains preserved as predecessor evidence.

`geofence-native-02` uses the unchanged frozen runner and `--stage package`:
**62 tests passed, zero failures/errors/skips**, including 27 PostgreSQL DAO
cases. The preserved `geofence-native-01` stopped before the PostgreSQL module
because the earlier `test` lifecycle had not attached its test-source artifact.
The native-02 input mapping contains the prior Marlin variant; that renderer is
unused in this database suite. Final-WAR persistence is checked separately.

`source/war-geofence-probe-01` runs those **27 actual PostgreSQL DAO tests** with
production libraries extracted only from final WAR `e291629c...`. The sole test
JAR supplements are retained JUnit 4.13 and Hamcrest 1.3. The harness rejects
production class shadowing, asserts seven actual production code origins, checks
the real `gfUserDAO` Spring transaction proxy and interceptor, and verifies real
PostgreSQL commit, rollback and cleanup. All pass, no cases are skipped, the
cluster is stopped and both WAR/classpath hashes remain unchanged.
Its result SHA is `288c2c50dfccd6a631c31369e801523b4fb321bf300e6ecf5e151a55b01cf7a8`.
This uses the native test application context; configured deployed authorization
and actual WFS/REST/OAuth HTTP acceptance remain the aggregate evidence.

The complete source tree manifest was rechecked after the final probes. The
build-01 executed recipe and input hashes match physically retained post-build
recovery copies; the JSON notice matches the actual JAR member. Recovery timing
is explicit, with no backdated receipt. Final probe recipes and fixtures are
also retained, with recorded input hashes checked where available. These records
are all linked from the compact evidence index.

The [independent imaging review](../verification/java-gmt-remediation/source-imaging-review.json)
binds the reviewed recipes, exact final WAR, selected class/source maps and
notices. All 83 selected Marlin classes have retained source, and all 42 supplying
files contain the Classpath exception. Its native renderer regression failure
and the separate JJ2000 rights blocker remain explicit.

Preserved failed attempts include source-encoding errors, incomplete preliminary
AspectJ module lists caught by API inspection, invalid XML witness assumptions,
legacy-driver fixture selection errors and an API comparator's inherited-field
ambiguity. They precede the corrected source build/probe and remain indexed;
none is hidden or overwritten. No required functionality was disabled to obtain
a pass.

Resume from the platform worktree with a fresh output directory:

```sh
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-source/build.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/source/build-02
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-source/probe.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS \
  --build /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/source/build-01 \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/source/probe-06
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-source/war_probe.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS \
  --war /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/aggregate-02/work/source/geoserver/src/web/app/target/geoserver.war \
  --war-sha256 e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044 \
  --component-build /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/source/build-01 \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/source/war-probe-03
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-source/war_geofence_probe.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS \
  --war /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/aggregate-02/work/source/geoserver/src/web/app/target/geoserver.war \
  --war-sha256 e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044 \
  --native-build /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/geofence-native-02 \
  --output /home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/source/war-geofence-probe-02
```

The smallest remaining JSON action is to substantiate the historical JSON-derived
permission chain or prepare a separately reviewed compatible source repair for
those precise files. Passing technical tests cannot grant those missing rights.
All candidate-wide security, notices/brand, owner-adoption and later F02-07/F02-08
acceptance gates remain unchanged.
