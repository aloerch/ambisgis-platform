# Supplemental Java source custody and recovery

This implements the source/provenance part of FND-02 after the frozen Java
resolution checkpoint. It does not declare a dependency source-build closure,
license approval, source/binary equivalence or product acceptance. See the
[64-coordinate evidence](../../plan/docs/java-source-provenance.md).

`source_closure.py` uses the exact recorded gap inventory and an explicit source
lock. It verifies original binary/POM bytes, source archive hashes, notice/header
hashes and acquisition receipts. It maps actual class SourceFile attributes;
when historical binaries omit debug attributes, it labels the weaker inference
from package and top-level type declarations. Generation templates and explicit
source/recipe hashes have a separate disposition. Metadata-only artifacts must
contain only exact Maven/JAR metadata and original notice text. Missing sources
and mismatched classes remain visible. Archives are inspected in memory with
path/type/duplicate/expansion checks, never executed by this command.

```sh
TASK_ROOT=/home/revelberry/Projects/AmbisGIS
python3 build-support/java/source_closure.py \
  --triage plan/verification/java-resolution-source-gap-triage.json \
  --manifest build-support/java/source-closure-inputs.json \
  --frozen-maven "$TASK_ROOT/source-archives/java-resolution/maven" \
  --supplement "$TASK_ROOT/source-archives/java-source-closure" \
  --output /tmp/ambisgis-java-source-new-report.json
```

Choose a fresh output path. Exit **2** means partial or unresolved source entries;
exit **1** means an integrity/validation error. `build_ready` and
`source_binary_correspondence_established` remain false even when all structural
mappings match. `acquisition.py --custody PATH --manifest PATH` verifies the
separate immutable custody snapshot, including failures, notices and probe outputs.

Add `--restore-sources` only for deliberate recovery of missing locked source
archives. This requests the recorded HTTPS URLs and requires the exact retained
SHA256/size before creating a content-addressed file. Existing mismatching files
are never overwritten; no moving discovery, version selection or donor
synchronization runs. Recover receipts/tooling/research from the retained snapshot.
JavaCSV's derived capsule must first be reproduced by the separate
`javacsv_recovery.py` recipe or restored from backup. Its original CVS archive is
also verified; downloading the original archive alone cannot stand in for the
derived sources. Source recovery does not modify the frozen Maven custody.

The bounded JGridShift probe compiles only its four retained core Java sources
using the already retained/verified JDK, `-proc:none`, and the existing socket-denial
runner. It compares actual public `javap` output against the exact selected binary,
verifies every IPv4/IPv6 denial receipt and checks unchanged source hashes:

```sh
python3 build-support/java/jgridshift_probe.py \
  --supplement "$TASK_ROOT/source-archives/java-source-closure" \
  --frozen-maven "$TASK_ROOT/source-archives/java-resolution/maven" \
  --toolchain-custody "$TASK_ROOT/source-archives/java-resolution/toolchain" \
  --tools "$TASK_ROOT/build-worktrees/java-resolution/toolchain" \
  --output "$TASK_ROOT/build-worktrees/java-source-closure/jgridshift-new"
```

This is a source compilation/API probe; its historical core source tree has no
test sources. API equality does not prove numeric grid correctness, identical
bytecode, a complete toolchain/native bootstrap, or a GIS release build. Both
successful and failed run directories are retained. No Maven donor lifecycle,
workflow, installer, deployment or publication executes.

Run tooling tests from the platform worktree:

```sh
python3 -m unittest discover -s build-support/java -p 'test_*.py' -v
```

Run package tests and strict validation from `plan/` in the already retained
validation venv. Host Python without jsonschema reports skips; preserve that
observation and use the existing venv to execute the required checks fully.
