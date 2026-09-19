# Contract status

These four JSON Schema 2020-12 files define **proposed starter envelopes**, not a complete implemented API. Corresponding examples use synthetic IDs and data. The complete OpenAPI specification, typed geometry/query/widget schemas, server authorization, semantic validation, concurrency behavior and conformance tests are implementation tasks.

`publication.schema.json` describes publication inputs. `edit-request.schema.json` describes a bounded atomic edit request. `post-request.schema.json` binds posting to an accepted reconcile and expected heads. `application.schema.json` describes initial declarative layout/widgets. A structurally valid object is not necessarily authorized, supported or semantically valid.

Validate with `python3 tools/validate_package.py --require-schemas` after installing `requirements-validation.txt` in an isolated environment. Negative schema tests are in `tests/test_contracts_and_plan.py`.
