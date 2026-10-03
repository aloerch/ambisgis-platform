# FND-08: merged client successor builds

The owned client formatting repair merged through
[client PR 1](https://github.com/aloerch/ambisgis-mapstore-client/pull/1) as
`c1f6ad9df52f08ac3bfd7211db9e3ee744b21407`, tree
`4b7d454ec77490317d73db1821b0cc14d53cdbb8`. This increment selects that exact
merged commit for the catalog and frontend producers. The source change fixes
the five inherited lint errors in two files without disabling rules or changing
assertions. The prior builds, lint failures and source snapshots remain intact.

[evidence.json](evidence.json) binds four actual fresh builds under
`build-worktrees/fnd08-client-successor/`, their exact source/input/tooling/output
manifests, donor fixtures, socket-denial receipts and native validation. The
only producer changes are the explicit client commit and tree selections.
GeoNode, MapStore, first-party policy and dependency selections remain exact
as recorded in the earlier reviewed recipes.

| Fresh pair | Build result | Output comparison |
| --- | --- | --- |
| `catalog-pair-001` | Both passed | Two owned wheels and the policy source/bytecode capsule are byte-identical |
| `frontend-pair-001` | Both compilations passed | 1,038 logical assets each; 526 identical raw names/content, 1,005 identical contents after explicit generated-name mapping, 33 explained content differences, zero unexplained |

Each pair creates its marked synthetic donor fixture before build one, changes
only that fixture after build one completes, and then performs a fresh second
build with the same exact selected inputs. The floating positive control
observes the changed sentinel. Fresh source, caches and outputs use retained
packages; actual IPv4/IPv6 socket-denial probes pass for all four builds.

The frontend pairing command retains its failed raw identity comparison. The
separate successful attribution receipt explains generated webpack hash/name
references and two literal build-root strings; no output bytes are rewritten
or normalized into a byte-identity claim. These remaining build-path strings
are still a distribution limitation. The reviewed fail-closed source-mutation
guards are present in the actual producer snapshots used for these builds.

Full client lint and the native browser suites ran against the first actual
fresh frontend build: **358 client and 152 framework assertions passed**, with
zero failures, errors or skips. This new combined native result passes; the
earlier failed lint result is not relabeled. The enclosing unprivileged user/
network namespace has only loopback, verifies successful local communication
and rejected external IPv4/IPv6 routes, and retains Chromium sandboxing. The
test runner itself still honestly reports that it does not enforce networking;
the separate namespace receipt establishes the enclosing restriction. Selected
source state is identical before and after these tests.

The [supplemental test-tool custody receipt](test-host-custody.json) is an exact
copy of the independently reviewed record for this browser-test environment.
It covers 42 signed RPMs and 33 exact corresponding-source groups, reusing 38
packages from the frozen 276-package initial-spine selection. The four additions
are `iproute2`, `libbpf1`, `libmnl0` and `libxtables12`; `unshare` was already
covered by `util-linux`. All 11 selected executable/library paths match retained
signed payloads, with zero selected differences. Both binary and source custody
replay with external sockets denied. The initial-spine selection remains
unchanged. Nonselected payload diagnostics and missing source-RPM metadata
records remain explicit; exact OBS inputs cover the latter in the separate
source receipt. This is input custody, not a source-built OS/toolchain claim.

The test-tool supplement's independent review SHA-256 is
`36386e56500ac64a8e7792b779ba8cd84aec38efb82c6b3166b41fad991c0050`.
Final pair/source acceptance remains with the integrator and independent
review; this increment does not itself accept all of FND-08 or a distribution.

Reproduce using the same `pair_catalog.py`, `pair_frontend.py` and
`compare_frontend.py` commands documented in the earlier
[remaining-slice evidence](../fnd08-remaining-slices/README.md), with new output
directories and the newly selected exact client source. The new pair receipts
retain the actual full command arrays. The committed [browser recipe](browser-helper.py)
and [original invocation](native-command.json) are byte-for-byte copies of the
executed files, also retained in the run root. The source-state snapshot and
JUnit records bind the actual compiled build. Re-run the recipe with the same
successful build and retained Chromium, choosing a fresh output directory and
capturing the current parent network namespace:

```python
import os
import subprocess

subprocess.run([
    "/usr/bin/unshare", "--user", "--map-current-user", "--net", "--keep-caps",
    "/usr/bin/python3", "plan/verification/fnd08-client-successor/browser-helper.py",
    "--build", "/home/revelberry/Projects/AmbisGIS/build-worktrees/fnd08-client-successor/frontend-pair-001/build-1",
    "--platform", os.getcwd(), "--output", "/your/fresh/native-output",
    "--chrome", "/home/revelberry/Projects/AmbisGIS/build-worktrees/frontend-completion/browser-inputs/chromium/chrome",
    "--parent-namespace", os.readlink("/proc/self/ns/net"),
], check=True)
```

Run from the platform root. `native_tests.py` remains the native suite authority;
this enclosing recipe selects no alternate assertions or browser security flags.

Twelve owned-build helper tests, 457 plan tests and four schema/example checks
passed. They remain separate from the native browser and actual build evidence.
The catalog's ten previously documented wheels without separate sdists retain
their embedded Python implementation and recorded limitations. Runtime assembly
must stage the fresh UI assets alongside the client wheel, which still contains
inherited static files. Linux-only scope, complete corresponding-source repair,
Windows, full product installation and release qualification remain unchanged.
