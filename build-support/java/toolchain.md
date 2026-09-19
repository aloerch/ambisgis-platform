# FND-02 Java toolchain custody

The selected acquisition tools are **Eclipse Temurin JDK 17.0.20.1+1**, Linux
x64 HotSpot, and **Apache Maven 3.9.16**. They satisfy the audited Java 17 and
Maven `[3.8,4.0)` constraints. This checkpoint retains distributions, corresponding
publisher source archives, metadata, checksums and original notices. It does not
establish complete toolchain source/build closure or Java/GIS acceptance.

Selection used the retained [official Temurin release metadata](https://github.com/adoptium/temurin17-binaries/releases/tag/jdk-17.0.20.1%2B1)
and [Apache Maven download page](https://maven.apache.org/download.cgi). The
Adoptium API initially returned HTTP 403; that failed observation is recorded in
`toolchain-validation.txt`. The download page and initial GitHub discovery
endpoint are snapshots, never floating inputs to the acquisition recipe.

`toolchain-inputs.json` records **44 files / 316,260,577 bytes** in
`/home/revelberry/Projects/AmbisGIS/source-archives/java-resolution/toolchain`.
It covers both tools' binary/source tar files, release metadata, Temurin SBOM,
checksums/signatures, Apache KEYS snapshot, acquisition receipts, notice inventory
and version output. Temurin build-script source at the metadata-declared commit
`e6ba7dec3d07654074559310376a3ae89da5f4ac` is also retained. Metadata declares
OpenJDK source commit `79597447bd94ff9f8216e2e3a573d5261ee49f2e`; source-to-binary
correspondence has not been independently rebuilt.

All four publisher archive checksums matched before tool execution: SHA256 for
Temurin and SHA512 for Maven. Signatures are retained, but **trusted signing-key
verification was not performed**. HTTPS and same-publisher checksum equality
are the recorded integrity evidence. They are not independent authenticity proof.

The complete archives preserve their original notices. `license-inventory.json`
records 324 notice/legal file and link entries by filename/path. The Temurin
NOTICE declares GPLv2 with Classpath Exception; its legal tree includes additional
third-party terms. Maven source has Apache-2.0 LICENSE/NOTICE; its distribution
includes separate dependency licenses/notices. This inventory is not file-level
license clearance. License/brand and security review remain open.

## Verify and restore

Run from the platform worktree:

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
python3 build-support/java/toolchain.py \
  --custody "$TASK_ROOT/source-archives/java-resolution/toolchain"
python3 -m unittest discover -s build-support/java -p 'test_toolchain.py' -v
```

Default verification is offline and executes no tools. It checks the exact
custody inventory, regular-file paths, byte sizes, SHA256 hashes and publisher
checksums. Changed, missing, symlinked and unrecorded inputs fail verification.

`--acquire` restores missing files only from manifest-recorded fixed HTTPS URLs
and requires both expected size and SHA256. Existing changed files are never
overwritten. Restore discovery metadata, generated evidence, KEYS and receipts
from retained backup; their original bytes cannot be recreated by querying
moving endpoints. This recipe does not select new versions.

`--extract /new/empty/path` requires a nonexistent destination and extracts only
distribution archives after complete custody verification, preserving originals.
It requires Python's `tarfile.data_filter` (Python 3.12+ or a backport), rejects
unsafe paths/links and duplicate nondirectory members, and allows the Maven
archive's repeated directory entries. It invokes no executable. If extraction
fails, inspect the partial output and retry with another fresh destination.

An actual temporary-copy recovery restored the Maven source SHA512 file from
its fixed URL. Fresh extraction then succeeded. The initial hardlink attempt
failed because `/tmp` is another filesystem; independent copies were used.
The first extractor rejected a legitimate repeated Maven directory; the fix,
regression test and successful rerun are recorded with the original failure.
All **12 toolchain tests passed**, with no failures/errors/skips in the final run.

The initial task-local extracted executables are:

```sh
TASK_JAVA_HOME=/home/revelberry/Projects/AmbisGIS/build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1
TASK_MAVEN_HOME=/home/revelberry/Projects/AmbisGIS/build-worktrees/java-resolution/toolchain/apache-maven-3.9.16
```

`java --version`, `javac --version` and `mvn --version` each exited 0. Maven
reports source revision `2bdd9fddda4b155ebf8000e807eb73fd829a51d5`.
The version commands used `MAVEN_SKIP_RC=true` and removed inherited
`JAVA_TOOL_OPTIONS`, `JDK_JAVA_OPTIONS`, `MAVEN_OPTS`, `MAVEN_ARGS` and `CLASSPATH`.
No build, Maven goal, resolver, inherited workflow, global install or remote
mutation was performed by this toolchain subtask. The verifier checks archives;
verify installed files against them or extract fresh before later execution.

## Remaining custody limits

The JDK native compiler/build dependencies, boot JDK, publisher base-image
layers and host shared-library source closure are not retained by this step.
The Maven source archive does not retain the full source/build closure for its
bundled external libraries. Publisher SBOM/build metadata describes inputs but
does not make those inputs locally recoverable. No independent source rebuild,
network-denied rebuild, repair exercise or GIS/runtime acceptance is claimed.
Parent/BOM/plugin/test/native/application dependency acquisition remains a
separate FND-02 step with its own explicit reactor/profile selection.
