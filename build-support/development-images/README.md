# Owned development image assembly

This directory assembles four OCI archives from retained, source-bound artifacts:
database, catalog, GeoServer and gateway. It does not build from external images,
invoke a package manager, import the selected Python packages, or start a
container. These artifacts remain a developer installation candidate. Runtime
execution, ABI relocation, persistent installation acceptance and distribution
approval are separate gates.

`recipe.py` verifies the retained Python RPM payload, canonical FND-08 catalog
wheels and dependency custody, owned PostgreSQL/PostGIS output, spatial support,
final owned Java WAR, tested runtime profile, servlet closure and JDK archive.
It writes a fresh selection with exact member inventories. The fixed launchers
use `/opt/ambisgis/python/bin/python3` and the committed owned service modules;
the image has no separate mutable product configuration. Installation config,
credentials and data arrive through the reviewed Compose bindings.

```sh
python recipe.py \
  --work /absolute/retained/build-worktrees \
  --custody /absolute/retained/source-archives \
  --java-classes /absolute/plt01-runtime-checks/java-002 \
  --python-lock /absolute/python312-image-inputs.lock.json \
  --gpl3-notice /absolute/retained/geodb/COPYING \
  --output /absolute/new-selection
python assemble.py --selection /absolute/new-selection/selection.json \
  --output /absolute/new-images-one
python assemble.py --selection /absolute/new-selection/selection.json \
  --output /absolute/new-images-two
python -m unittest discover -s . -p 'test_*.py' -v
```

Run these commands from this directory using the reviewed retained build
interpreter. All output paths must be fresh. The assembler verifies every input
again, writes sorted deterministic tar members with fixed epoch and root archive
ownership, and passes every result through the actual installer OCI verifier.
`result.json` supplies each archive hash, manifest digest, immutable image ID and
explicit local image reference. All images carry the common source-manifest hash
and the applicable owned component revisions. The original artifact receipts
remain unchanged.

`source-manifest.json` records every image member, source component and hash,
including exact source/rights evidence references. It records the following
explicit packaging projections:

- Regular producer files become 0644, executable files and directories 0755, so
  root-owned archive members can be read by arbitrary `keep-id` users. Original
  tree/wheel modes remain recorded; special modes and capabilities are excluded.
- The Python distro import-reporting startup hook is retained under notices,
  outside interpreter startup. Package scripts never run.
- Wheel top-level `test`/`tests` packages and non-import wheel data remain under
  per-distribution data directories. This preserves their bytes while avoiding
  unrelated distributions overwriting each other's test modules. Nested package
  test data and all notices remain intact. No console script is added to PATH.
- One exact PROJ library has a derived copy whose absolute SQLite DT_NEEDED
  becomes `libsqlite3.so`. `relocate_proj.py` requires the original artifact
  SHA256, verifies dynamic/symbol/version string references, rejects overlapping
  or ambiguous strings and changes only the recorded string span. The original
  library remains untouched. The derived hash and tool hash are explicit.

The retained native builds contain original absolute RPATH strings. Those bytes
are preserved and reported; the image supplies fixed library search paths. A
static `elf_closure.py` scan reads actual OCI layer members and models potential
RPATH inheritance. It reports conditional loader contexts, unrelated alternate
architecture helpers and missing optional full-JDK GUI/audio dependencies. It
does not prove actual loading, symbol versions, `dlopen`, font resolution or ABI
compatibility. The qualified target remains the selected headless developer
profile. No claim that every incidental shipped executable is supported is made.

Exact third-party notices are carried in their original wheels/JARs/JDK tree and
the selected notice directories. The Waitress source LICENSE and COPYRIGHT are
both included. The common notice records the existing first-party
GPL-3.0-or-later declaration and carries the complete retained GPL version 3
text. Corresponding third-party source remains in the explicitly referenced
retained source custody; this assembly is not a new assertion of legal clearance
or a self-contained source release. Historical JDK source-rebuild and other
recorded custody limitations remain visible.

Before adoption, independently review the concrete selection and archives, then
perform the authorized ordinary installer tests with the separately qualified
runtime. The existing targeted runtime-probe hold is unaffected by this recipe.
