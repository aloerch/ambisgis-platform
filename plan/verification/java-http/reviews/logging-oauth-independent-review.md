# Independent logging, OAuth and receipt review

Reviewed the aggregate WAR logging probe, its lifecycle-repair manifest, both
Java OAuth witnesses, the OAuth diagnostic-repair manifest, runtime repository
priming, and the strict native-report parser. This was source/evidence review;
this reviewer did not execute the application or native Java suites.

## Findings and corrected implementation

1. **Reflected OAuth error disclosure.** The initial repair covered complete
   response-map logging and the invalid-token exception, but left the inherited
   `logger.debug` statement printing the validation server's `error` value.
   That value could reflect sensitive request content. The final repair replaces
   it with a fixed diagnostic too. A third regression captures the actual
   inherited logger category in a nonadditive memory appender, proves capture
   works before creating its random marker, invokes the native method with the
   marker in the error response, and asserts without including the marker in
   failure output. The separate exception regression remains. Source guards and
   exact replacement checks preserve the authentication decision code. Native
   baseline/repaired results are pending separate execution evidence; source
   review alone does not establish runtime success.
2. **WAR artifact identity.** The initial inventory accepted any known digest
   under any required library filename. The revised inventory requires the
   filename/digest pair from retained inputs or actual owned build outputs.
   It also refuses nonempty `WEB-INF/classes` rather than silently omit that
   classpath segment. The actual examined candidate has 368 library JARs and no
   `WEB-INF/classes` files. These guards have seven focused tests; a fresh
   reviewed witness result passes on the actual candidate after the changes.
3. **Runtime repository directory creation.** The initial priming helper called
   recursive mkdir before checking destination ancestors. A temporary reproducer
   confirmed that a symlinked ancestor could create an outside directory before
   refusal (no artifact bytes were written). The revised helper checks the
   local root and each ancestor before creating the next component. Its new
   regression requires no outside-directory creation. Existing conflicting
   artifact bytes still fail instead of being replaced; publisher sidecars stay
   retained and Maven's normalized cache copies are left alone.

The earlier native report counter-trust defect is fixed: all suite counts and
case identities are required, counts must match actual records, and contradictory
or flaky/retry outcomes fail. Historical duplicate setup/teardown errors remain
valid distinct records and are not converted into passes.

OAuth preparation now records intent to avoid printing fixture values rather
than the unobserved claim `tokens_logged=false`. Diagnostic capture contents,
request credentials, random fixture values, and exception text are not printed
by the witnesses. HTTP scenario output contains only fixed case names/outcomes.
This is bounded diagnostic evidence, not a claim that all application logging is
secret-free or that browser/SSO/canonical authorization has been accepted.

## Actual aggregate evidence inspected

Read-only verification of `combined-logging-reviewed-02` confirmed both compile
and runtime socket-denial receipts, their log hashes, 368 library entries, and
all seven native logger/bridge markers emitted exactly once. Result SHA256:
`3449af697df73eae5776c24421cc6be335271bfe07f90be9b241acc25acf8c4f`.
The witness exercises real component logger fields under explicit JUL/GeoTools
logging settings. Its receipt correctly says the application was not started
and service requests were not exercised. This result is not runtime deployment,
policy, license, source-to-binary closure or human security acceptance.

## Reviewed file identities

| File under `build-support/java` | SHA256 |
| --- | --- |
| `combined_logging_probe.py` | `55d5adffd5c0d6880479a9fbee0403741862432f1d8002b8f1b9fa90cbb36472` |
| `combined_logging_patch.py` | `ec2300807b9637aac08515ad49f710b14c46034af3d9d3863e8a3b4993586f7b` |
| `combined_logging-repairs.json` | `2be088f68cd65634490e3e69cb33d5ae167305ac1c5e60ab57bf154005dade0e` |
| `combined_logging-fixtures/CombinedLoggingWitness.java` | `6ba253fe03a13a52a2acf69b7eddbd54f966934962c97ef4a7e3a6e6433cd2e6` |
| `oauth_fixture.py` | `c288112625f612cc8eede5715862ede44dab54c7fe1e7e108f6f2016d5e9cec7` |
| `oauth-redaction.json` | `454de3891baa5767a1e7ecb7cc4d8114fccb33db53bd5ce62fe1473f34107490` |
| `oauth-fixtures/AmbisgisGeoNodeDiagnosticsTest.java` | `fa15e3e87ea4af5942a82befdc9e2498f192d86e9bc62bb078daeaea83bccfe7` |
| `oauth-fixtures/AmbisgisGeoNodeHttpTest.java` | `7efde143325d8aa29ee35b6a46a472f3c20fa118b3aeeb3c5cf97a4097149c68` |
| `compatibility.py` | `778e3fd341d205717bd86ce590430cf06fc7b4ddcbed6d62815bf13c224d486f` |
| `native_reports.py` | `5ae4497118ac4e36d1b5a5a40a54ea2014bfe7c310f2091040540ce65db5289b` |
