# FND06 Koop candidate custody — pre-execution review

This increment retains the candidate for the required
[FND06 reuse experiment](https://github.com/aloerch/ambisgis-platform/issues/5).
It does not select Koop for the product or claim C1 compatibility. Independent
review must precede execution of newly acquired package code. The offline install
recipe is prepared but has not run at this checkpoint.

The exact official source is `koopjs/koop` repository ID `11542346`, commit
`333518a19d43adf2fd12faed1a3be52d9c90dd3f`, tree
`3357f74aa588b18703f26cdb5b5a5f7809d7d150`. All 447 source files were retained,
checked against Git blob identities and a recomputed complete Git tree. Original
source package manifests, tests and notices remain unchanged. The source archive,
API identity/tree metadata, original lock, registry version metadata and 238
distinct registry archives are retained under
`/home/revelberry/Projects/AmbisGIS/source-archives/fnd06-koop/candidate-002`.
Ninety-seven archives reuse already retained exact bytes; every archive passes
the selected integrity and exact-version metadata digests. Where the original
lock included integrity it is preserved; missing identities are supplemented
explicitly as described below. Registry
signatures are retained as metadata, without claiming signature verification.

## Exact graph reconciliation

The committed upstream lock is stale for three workspace versions and two exact
workspace dependency edges. The source packages specify core `10.4.19`, output
`8.1.25`, FeatureServer `9.3.0`, Winnow `5.0.4`, cache `6.0.0` and logger `5.0.0`.
The derived lock substitutes those source identities. Every third-party version
comes from the original lock; no semver resolution, floating install or
donor-tip selection occurred. The original lock lacks archive URL/integrity for
127 selected installation paths in both its packages and legacy dependency maps.
`resolution-supplements.json` supplies those missing identities from 121 retained
exact-version registry metadata records, separately labeled as new metadata
provenance. Existing original archive identities remain unchanged. Traversal follows
Node's nearest installed dependency paths and includes production dependencies,
optional dependencies and required peers. Unresolved required edges or registry
archive identities fail. The complete graph has 265 entries including six
source workspaces and their links.

Independent review rejected candidate001 before execution because its archive
inventory omitted those unresolved rows. Its 120-archive snapshot remains intact
as an incomplete historical attempt and must not execute. Candidate002 uses a
separately retained acquisition helper snapshot and exact command receipt. Guards
cover the review finding and dependency-version substitution.

`reconciliation.json` records each original/selected workspace and every selected
edge. The original lock's development graph is excluded. All selected archive
URLs become retained local paths in the replay lock. `build-support/koop/inputs.json`
binds its manifest and lock digests; changing the retained inventory cannot silently
authorize a new graph.

The installation recipe creates pristine source plus a separate temporary app.
Only `devDependencies` is removed from the six temporary workspace manifests;
all runtime fields, implementation and license files remain identical. This
explicit build projection avoids requiring the original development graph for
a production-only installation. Each projection is recorded and checked after
installation. It is not a change to retained upstream sources.

## Execution boundary and hashing choice

The prepared recipe extracts the existing retained Node `24.18.1`/npm `11.16.0`
archive (SHA-256 `d6c664df3f3f61458e8c277585571328522d705166723a7c7823a9253a4d15a0`)
into a new attempt with a fresh home, npm cache and node_modules. The exact command
is `npm ci --offline --ignore-scripts --omit=dev --omit=optional --no-audit --no-fund`
under the existing kernel socket-denial runner. npm user/global configuration
is empty. All thirteen declared install/prepare hooks are inventoried and disabled.
No native binary members were found in the selected registry archives.

Optional farmhash and its dependency closure are retained, but the initial spike
does not install or compile them. The exact source's
`packages/winnow/src/filter-and-transform/helpers/hash-function.js` selects the
retained pure-JavaScript murmurhash implementation when
`OBJECTID_FEATURE_HASH=javascript`, and otherwise has an explicit catch/fallback.
The corresponding source tests are retained, not reported as executed. The
native contract supplies stable positive int32 `object_id` values; generated
feature hashes will not become the product identity authority.

Installation verification checks every installed archive member against retained
bytes, every workspace link, every original source file and the six precise
manifest projections. Missing required packages or installed farmhash fail.
Corrupt source/archive, missing input, unsafe path/link, substituted source/tree,
unresolved dependency and changed reviewed-lock guards have actual stdlib tests.

## Notices, limitations and next work

The selected Koop package license files declare Apache-2.0 and preserve Esri
copyright notices. Every dependency has its actual manifest and archive contents
retained. Several packages have notices in README or source headers rather than
a license-named file. For example,
`murmurhash@2.0.1` includes the full MIT grant and 2020 Gary Court/Derek Perez
copyright; `@esri/proj-codes@3.4.0` includes Esri's 2010–2024 copyright and
Apache-2.0 declaration. These exact embedded notice hashes are recorded separately.
`geojson-validation@1.0.2` declares LGPL-3 and includes its LGPL text and JavaScript
implementation. Its corresponding-source and distribution obligations are not
waived. `tr46@0.0.3` declares MIT but its npm archive and registry-recorded source
revision contain no license/notice file; this remains an explicit notice-provenance
gap for disposition before distribution, not an invented copyright notice.
Package declarations are not full legal clearance. Generated JavaScript and data
are inventoried honestly; this does not claim independent compilation of every
third-party package or approve distribution.

After the concrete source/graph/code review, run the prepared fresh install and
record actual results. Then consume the integrator's native query contract and
existing catalog authority for the real PostGIS/Koop experiment. Output flags,
pushdown, immutable-revision pagination, error fidelity, cache isolation,
revocation, route/capability restrictions and resource limits still need actual
tests. No parallel permission model or bespoke C1 encoder is introduced here.
