# F02-06 independently authored selected-profile JSON adapter

This successor implementation replaces the entire old `net.sf.json` production
layer in the selected Java/server profile. It is a distinct AmbisGIS artifact,
not an upstream json-lib release or a complete replacement for its optional
binding/XML/Groovy/function APIs. No adoption, distribution or legal clearance is
implied by passing tests.

The compact [JSON evidence](../verification/json-jpeg2000-remediation/json-evidence.json)
links the retained parent source audit, independently authored source manifests,
all final artifact identities and focused results. The source audit preserves
all 55 original Java/Groovy sources, including the 51 previously compiled Java
files. It identifies the seven attributed selected files: `JSONArray`,
`JSONObject`, `JSONException`, `JSONNull`, `util/JSONBuilder`,
`util/JSONStringer`, and `util/JSONTokener`. Two alternative JDK15 copies also
carry JSON.org attribution. Uncredited `JSONUtils` number/quoting/value helpers
make an attribution-only seven-file separation unjustified. None of this old
production layer is compiled or packaged into the new adapter; original sources,
notices and old JARs remain unchanged in custody. The retained historical
Apache declarations do not substantiate the missing original derived permission.
Current JSON-java grants are not asserted to apply retroactively.

The implementation uses Jackson core 2.21.0 already selected by the parent WAR;
no Jackson version changes, polymorphic/default typing, input-driven class
loading or code evaluation occur. Jackson tokenizes and emits JSON, while small
JDK map/list/writer adapters provide the observed consumer API. The complete
Jackson source archive, POM, Apache grant and original notices are pinned.
Jackson's shaded numeric-parser source/notice supplementation is recorded
separately; the Jackson binary remains unchanged and is not claimed freshly
source-built by this work.

The exact parent WAR has 20 static consumer classes using 48 members of eight
compatibility classes. The source and resource audit includes selected service,
OAuth/token/role sources and compiled reactor tests, not just those references.
It records zero dotted reflective class-name literals and three resource matches
(all POM metadata). Selected reactor tests additionally need meaningful
`optJSONObject`, `remove(String)`, `JSONArray.toCollection(..., JSONObject.class)`
and structural `JSONAssert` operations. The adapter supplies these, preserving
normal test compilation. The first new aggregate exposed a source-only generic
contract missed by binary signature scanning: `ImportJSONReader` assigns a
`JSONObject` to `Map<String,Object>`, which the old raw `Map` API permits. The
adapter preserves that raw public contract with typed internal storage. A fresh
supplemental compile now checks all 25 selected production and 69 selected test
source files against baseline and adapter; its negative control detects the
previous broken adapter. This is compilation evidence, not execution of those
69 tests, and the complete fresh aggregate remains required. Optional historical
APIs are absent, not hollow stubs.

The selected GeoNode token service delegates to Spring's map HTTP conversion;
the REST role service uses Jackson/JsonPath/json-smart. Their real HTTP checks
remain necessary aggregate evidence. MapFish uses another retained JSON stack;
its tests do not alone validate this adapter. Other existing org.json, openjson,
jettison and json-smart artifacts retain separate source/terms records. This is
not a claim that all JSON.org-related material disappeared from every profile.

Focused execution includes the unchanged 213 retained comparisons, additional
null/missing/property, Unicode, numeric type/precision, legacy syntax, bean and
writer cases, eight unchanged non-function json-lib native writer test methods,
and all 41 unchanged GeoServer `GeoJSONBuilderTest` tests. The two original
BeanUtils `class` property expectations remain historical failures. The full
359-test general-purpose json-lib suite is not represented as a fresh pass;
new tests separately establish continued safe `class` suppression.

Common legacy single quotes, unquoted keys, Java comments, trailing commas,
missing array values, equals/semicolon separators, hex/octal integers and
repeated-key accumulation are tested against the original implementation.
The bounded profile explicitly rejects ambiguous bare array text such as
`[1 2]` instead of silently creating a string; quoted equivalents work, and the
source audit found no selected consumer needing this extension. Function-looking
Java strings stay strings. Parser/conversion depth is bounded as well as writer
depth (default 100, valid positive configuration capped at 1,000); radix numbers
are bounded before conversion. Only standard exact JDK numeric types can emit
raw numeric tokens. Finite decimal values beyond double range use a bounded
`BigDecimal` fallback, preserving values such as `1e400` and `1e-400`. Extreme
valid exponent scales retain compact scientific notation; exponent overflow
raises a sanitized adapter exception. Ordinary fractions remain `Double` at
normal double precision, so the historical parser's accidental float rounding
(for example `1.234567890123456789` to `1.2345679`) is not reproduced; this is a
documented bounded compatibility difference. Diagnostics preserve a location without echoing input or
raw parser causes. Failed writers cannot resume or manufacture a completed
object, and caller-owned writers remain open.

The first broader WFS run exposed two real UUID map/list regressions. Their raw
logs and the initially overoptimistic receipt remain untouched; the explicit
[failure correction](../verification/json-jpeg2000-remediation/json-failure-correction.json)
classifies that run as failed and binds the repair. The final runner treats the
WFS suite as required and freshly executes that retained broken artifact as a
negative control proving failure detection. Another negative control rejects the
original json-lib runtime.

`inventory.py` checks every selected `net.sf.json` definition against exact new
compiled member hashes and a verified independently authored source manifest.
It rejects duplicate/foreign/versioned definitions, scans nested archives, and
requires both old binary fingerprint sources at recorded hashes. Source-level
accounting accompanies these checks; hash absence is not represented as proof
against arbitrary transformed copying. Its aggregate integration reopens the
actual WAR and derives the component result from the frozen, hash-verified
replacement mapping; a failed nested check raises instead of allowing a success
receipt.

Run on the host from the platform root, with a fresh output directory:

```sh
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-json/build.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS --output NEW_BUILD
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-json/probe.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS --build COMPONENT_BUILD \
  --war EXACT_NEW_WAR --war-sha256 EXACT_NEW_SHA --output NEW_PROBE
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-json/consumer_compile.py \
  --workspace-root /home/revelberry/Projects/AmbisGIS --build COMPONENT_BUILD --output NEW_COMPILE
flatpak-spawn --host /usr/bin/python3 build-support/java/remediation-json/inventory.py \
  --build COMPONENT_BUILD --war EXACT_NEW_WAR --output NEW_INVENTORY_JSON
```

Compiler and executable probes use the established process-local AF_INET/AF_INET6
socket denial wrapper and retained JDK verification. Exact new aggregate
compilation, WFS/REST/auth/role and other configured runtime acceptance remain
integration evidence; old-WAR receipts are never fresh acceptance of new bytes.

The [exact-WAR evidence](../verification/json-jpeg2000-remediation/json-war-evidence.json)
binds fresh execution to the successful aggregate-03 WAR. It passes the JSON
contracts and native tests above, ten XML contracts, two actual Spring/AspectJ
proxy contracts, and genuine Java5 load-time weaving with the normal Java17
verifier. It also freshly passes all 27 retained GeoFence DAO tests and real
transaction proxy commit/rollback against a fresh PostgreSQL AF_UNIX fixture;
cleanup stopped that cluster. JSON fixture classes are checked for production
shadowing, loaded origins are verified, and selected WAR/JAR/test inputs are
rechecked after execution. Full service/HTTP and imaging acceptance remains in
the integrator's separate matrix, with existing historical limitations preserved.
