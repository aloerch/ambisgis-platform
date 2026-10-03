# FND-06 final candidate evidence

[evidence.json](evidence.json) assembles the original task criteria, exact component
reviews and combined validation. This is the acceptance candidate in
[PR77](https://github.com/aloerch/ambisgis-platform/pull/77), not a merged-task or
product-release receipt. The final aggregate review and protected integration
are separately recorded against the exact final head.

All 503 package tests, ten schema/example checks, 35 Koop guards and 14 actual-input
notice guards pass without skips. Runtime005 independently audited 227 assertions
on 100,000 actual database rows, with native catalog authorization and unchanged
Koop encoding. Separate corpus evidence covers actual owned-QGIS small/100k/1m
runs and malformed-input rejection. Package checks remain distinct from these
native executions and from the still-required full product acceptance.

The reviewed tr46 supplement resolves its precise missing-notice/source finding
for a reproducible software/documentation/source staging layout. Future artifacts
must actually include those notices and fulfill all remaining license, security,
source, signing and branding obligations. Original failed attempts, historical
receipts and dependency archives remain unchanged.

The native error-contract validation records its original-schema rejection and
the additive correction consumed by the final runtime. The initial validation
driver stopped before tests due to a fixture-path typo; its note remains in that
receipt. A deliberate negative package fixture prints a failed receipt after
unittest OK, as required by the rejection test.
