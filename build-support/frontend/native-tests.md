# Bounded owned frontend checks

`native_tests.py` runs all 40 tests discovered in the selected GeoNode MapStore
client source and an explicit seven-file MapStore selection for configuration,
resource handling, OGC URLs and security state. These are unchanged inherited
assertions, executed with the retained project's native webpack/Babel/Mocha
configuration. This is not the complete MapStore suite or browser workflow
acceptance.

The launcher retains Chromium's sandbox and web security. It binds Karma to
loopback. No network-denial assertion is made by this runner; independent build
network-denial evidence belongs to the build harness. Review source tests and
use only synthetic fixtures. The runner runs ESLint without the inherited
`--fix` flag, records source hashes, and fails if client source contents change.

Use an already installed, reviewed client tree and the retained Node/browser:

```sh
python3 build-support/frontend/native_tests.py \
  --client /absolute/build-01/client/geonode_mapstore_client/client \
  --node /absolute/node-v24.18.1-linux-x64/bin/node \
  --chrome /absolute/retained-chromium/chrome \
  --output /absolute/evidence/native-run-001
```

The output directory must not exist; its parent must exist. Logs, generated
entrypoint, exact source-file hashes, JUnit counts and coverage are retained.
Individual checks can be chosen with `--suites lint`, `--suites client` or
`--suites framework`. Failures and skipped assertions remain visible. A
positive result requires real browser test cases in JUnit, zero failures/errors,
zero command errors/timeouts, and unchanged client sources. Skips are reported;
they are not converted to passes.

The browser path is explicit; no browser is downloaded. The caller owns any
browser library dependencies and source/provenance retention. The project
package must be retained locally. The runner creates an explicit entrypoint
because the inherited project's entrypoint assumes installation beneath
`node_modules/@mapstore/project`, which is not valid for every retained-source
layout. Framework fixture URLs are routed to that recovered checkout while
keeping the original assertions unchanged. Child processes inherit at most four
available CPUs so test bundling can coexist with the bounded completion work.
