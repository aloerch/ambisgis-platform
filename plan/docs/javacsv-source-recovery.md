# JavaCSV 2.0 exact-source recovery and compatibility probe

`net.sourceforge.javacsv:javacsv:2.0` now has retained publisher source
provenance despite its missing Maven source classifier. Its original native
suite passes **105 tests without failures/ignores** on the recovered source
under the suite's explicit CRLF newline assumption. The first Linux-default
run failed 16 hard-coded CRLF assertions; the original selected binary fails
exactly the same 16 assertions. Those failures remain evidence and the Linux
suite is not represented as passing.

## Exact recovery

The [official source page](https://sourceforge.net/p/javacsv/code/) links the
[publisher's complete CVS snapshot](https://sourceforge.net/code-snapshots/cvs/j/ja/javacsv.zip).
Snapshot SHA256 is `608624c41a5b499e7f0085854fb39e359c1e34a133506ddf16c86331703263d3`
(225,143 bytes). CVS `javacsv.jar` revision **1.2**, dated
2006-12-20 20:01:26, is byte-for-byte identical to the selected Maven 2.0
artifact: SHA256 `c287e9d431e4e05a0f7c9c023d133edf8a40112885cdb6e81b07773eee4680ed`
(13,417 bytes). The publisher's 2.1 archive has a different binary and was
retained only as a rejected exact-version candidate.

Contemporaneous original files are selected by actual CVS revisions:

| File | Revision | SHA256 |
|---|---|---|
| `src/com/csvreader/CsvReader.java` | 1.9 | `659de2080f9641e3d0ee3446eaa9b4ea1a8b3c30a3a6c470fcddcce7646867b4` |
| `src/com/csvreader/CsvWriter.java` | 1.8 | `adc1bb26bec625bb661d8e5902daaa98f69b8c10d7160e5531bbf41ad727b977` |
| `src/AllTests.java` | 1.4 | `f51edc54a4679ffd3ec1a09b6d3ce37971d1ba0e2b038f818c5fd4d0942c90fe` |
| `build.xml` | 1.3 | `e13866b5101f12cfbaffa77d76cb4dc90d32cb2ae9fd3819b95bb772dcd20866` |

Library source headers retain Bruce Dunwiddie's copyright and LGPL-2.1-or-later
terms. Historical `AllTests.java` has no file header; this is explicit license
review evidence, not final legal approval. The full original CVS history,
original source bytes and publisher responses remain retained.

[javacsv_recovery.py](../../build-support/java/javacsv_recovery.py) verifies
both pinned input hashes, reconstructs RCS trunk reverse deltas without
executing repository hooks, proves the original binary equality and checks
every selected source hash/date before emitting a deterministic source
capsule. It does not use the changed 2.1 writer. Capsule SHA256:
`7d0022112ccafbf27c940e80756f2591f6f7c8686d075af87cd57040bd9cffbe`
(18,729 bytes). Original notices and `DERIVATION.json` are inside the capsule.

Custody root:
`/home/revelberry/Projects/AmbisGIS/source-archives/java-source-closure-research`.
The capsule and `recovery.json` are in its `javacsv-2.0-recovered/` directory;
URL/hash receipts are in `receipts/`, original responses in `blobs/sha256/`.
`research-snapshot-01.json` records immutable input hashes. Its scope also
includes explicitly unsuccessful json-lib/JavaCSV source discovery attempts.

## Actual compilation and native results

[javacsv_probe.py](../../build-support/java/javacsv_probe.py) compiles original
sources/tests with retained Temurin 17.0.20.1+1 (`--release 8`, ISO-8859-1),
JUnit 4.13.2 and Hamcrest 1.3. No source or test expectation was edited.
An owned JUnit runner verifies actual library class origin and fails unless
all 105 native tests run without failures/ignores. It avoids the inherited
interactive test main, which mishandles teardown and may wait for console
input after a failure. The JDK/Maven extracted trees were reverified.

Every compile/test runs through the existing process-local seccomp runner.
Receipts verify AF_INET/AF_INET6 socket creation denied; this is not full
host/toolchain closure or a hostile-code/filesystem sandbox.

| Retained run | Library and newline setting | Actual native result |
|---|---|---|
| `javacsv-01` | Rebuilt source; actual Linux default LF | 105 run, 16 failures, 0 ignored |
| `javacsv-02` | Rebuilt source; explicit historical CRLF | 105 run, 0 failures, 0 ignored |
| `javacsv-03` | Original selected 2.0 JAR; actual Linux LF | Same 16 failures among 105 tests, 0 ignored |
| `javacsv-04` | Original selected 2.0 JAR; explicit CRLF | 105 run, 0 failures, 0 ignored |
| `javacsv-05` | Fresh rebuilt source; final counted-result runner, explicit CRLF | 105 run, 0 failures, 0 ignored |

Runs are under
`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-compatibility/`.
[Machine evidence](../verification/javacsv-source-recovery.json) includes
commands, tool/dependency/output hashes, native counts, failed test names and
actual network-denial receipts. Every compile/native log, including both
failures, is committed as `verification/javacsv-0*-*.log`.

This validates a recoverable source candidate and its historical CSV behavior.
It does not reproduce Java 5 byte output, prove whole GeoTools/importer
integration, approve license/security baselines, or satisfy FND-07/FND-08.
The existing default-newline contract remains platform-dependent; any product
CSV newline choice needs its own integration contract and tests.

## Reproduction and tooling checks

```sh
python3 build-support/java/javacsv_recovery.py \
  --snapshot /path/to/608624c41a5b499e7f0085854fb39e359c1e34a133506ddf16c86331703263d3 \
  --artifact /path/to/c287e9d431e4e05a0f7c9c023d133edf8a40112885cdb6e81b07773eee4680ed \
  --output /new/recovered-source-directory
python3 build-support/java/javacsv_probe.py \
  --sources /new/recovered-source-directory \
  --jdk /retained/jdk-17.0.20.1+1 --maven-custody /retained/maven \
  --toolchain-custody /retained/toolchain-archives \
  --run /new/probe-directory --line-separator crlf
```

Omit `--line-separator crlf` to retain the actual Linux-default diagnostic;
`--original-artifact /path/to/the/verified/2.0/jar` compares original behavior.
Outputs require new directories; previous runs are never overwritten.

All **148 Java tooling tests** passed (eight new recovery/result guards),
**175 package tests** passed and all **four strict schemas/examples** passed,
without failures/errors/skips in those tooling/package suites. Evidence is in
`verification/javacsv-tooling-tests.txt`, `javacsv-package-tests.txt`,
`javacsv-package-schemas.txt` and `javacsv-toolchain-verification.json`.
These counts are separate from the native runs above. Database/Jupyter
native checks were not repeated. No workflow, remote PR, release or task
progress changed in this engineering slice.

## Probe guard review follow-up

The initial runs and their failures remain unchanged. Review identified that
the first probe recorded Java executable hashes without itself enforcing the
retained extracted toolchain, inherited the caller's environment, and did not
validate its socket-denial receipts before reporting success. These guards
are now enforced within the recipe; the historical independent toolchain
verification is not substituted for the new checks.

The current probe requires `--toolchain-custody` and verifies every installed
JDK/Maven file/link with `toolchain.verify_extracted` before execution. It
requires the exact retained JDK root and pinned JUnit/Hamcrest hashes. Only
`PATH=/usr/bin:/bin`, `LANG=C.UTF-8` and `LC_ALL=C.UTF-8` reach subprocesses;
JVM options/agents, classpaths and credentials are not inherited. It copies
and compiles only the selected hashed source files, and rechecks both original
custody and local copied source bytes after each step and on completion.

Both command receipts must report **completed**, the matching argv/exit,
`no_new_privs`, and unique successful AF_INET/AF_INET6 `EPERM` denial probes.
Each command has a bounded timeout (default/maximum 300 seconds); the existing
process-group runner terminates and then kills remaining descendants after
a two-second grace period. Errors/timeouts retain logs and a failed result.

Fresh **`javacsv-06` compiled and passed all 105 native tests, zero failures
or ignores**, with explicit historical CRLF. Its class-origin guard points to
the newly compiled classes. Both denial receipts and unchanged-source checks
passed; toolchain verification checked 342 files and 208 symlinks. See
[the fresh result](../verification/javacsv-hardened-probe.json) and
`verification/javacsv-06-*-offline.json` / `javacsv-06-*.log`.

Eight new adversarial guard tests cover bad toolchain custody, inherited JVM
options, missing/wrong denial evidence, altered/symlinked sources, extra
unselected source files and timeout failure retention. The updated complete
Java tooling suite passed **156 tests**, the plan suite passed **175 tests**,
and all four schemas/examples passed, without failures/errors/skips. Fresh
outputs are `verification/javacsv-hardened-{tooling,package}-tests.txt` and
`javacsv-hardened-package-schemas.txt`. These guard/native results still make
no host/toolchain-closure, license/security or product-acceptance claim.

## Separate json-lib finding

The actual GeoServer patch author in [PR 3736](https://github.com/geoserver/geoserver/pull/3736)
and [GEOS-9321](https://osgeo-org.atlassian.net/browse/GEOS-9321) retains
`fernandor777/Json-lib` branch `limit-fix-2.4`, commit
`1ff8dc03730cb00afb4628350f3106f35c122d34`. Its source archive is retained with
SHA256 `221c662bbafa7f722746c00f625ae7f30c06354be0d8eccfa0ca363c747bf14b`.
Its POM differs from the selected published 2.4.2-geoserver POM only in the
version (source says 2.4.1-geoserver). That is a useful source candidate, but
**exact 2.4.2-geoserver publisher source remains unproven**: a POM comparison
does not rule out uncommitted Java changes. No source classifier was fabricated.
[Exact research evidence](../verification/jsonlib-source-research.json)
retains the difference and the next compatibility/provenance step. No maintainer
was contacted and no later json-lib release was silently substituted.
