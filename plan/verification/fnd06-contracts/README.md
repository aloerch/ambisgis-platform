# Initial FND-06 contract validation checkpoint

485 package tests and ten schema/example pairs passed after independent review
identified and the implementation fixed lowercase RFC3339 error handling and
decimal zero at equal precision/scale. The original missing-module baseline is
retained. These are contract/package checks, not GIS product acceptance.

`validation.json` binds actual commands, logs and source bytes. The negative
receipt fixture intentionally emits a JSON `failed` record after the unittest
suite reports OK; this is an exercised rejection, not a hidden test failure.
Actual Koop/PostGIS/catalog execution, corpus review and aggregate FND-06
review/acceptance remain separate. No product release or phase is accepted.
