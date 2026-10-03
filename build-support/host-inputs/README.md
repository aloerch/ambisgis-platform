# Selected Linux host input custody

These tools retain the compiler, headers, build utilities and mapped runtime
libraries actually selected by the FND-08 Linux builds. The starting observation
contains sixteen compiler/tool executables; the QGIS runtime adds observed
library, locale and resource paths. Native/catalog/browser build records add
the actual system tool and resolved-library paths, including Python 3.12's
bootstrap modules. Only this selected set and its conservative
installed RPM providers are included. The unrelated full host package inventory
remains private.

`inventory.py` verifies observed file hashes and retained publisher metadata,
preserves complete package identities across versions/architectures, and uses
librpm's version comparison for installed providers. Simple two-atom `if`/`or`
requirements are supported; other expressions remain unresolved. This is a
conservative custody inventory, not an installation solver transaction. It does
not change the system package database or run package scripts.

`retain.py binaries` acquires only exact recorded public RPM URLs. It checks
publisher hashes, signatures against the existing RPM trust store, package
identity, and the original installed header digest. Both current and fixed
historical publisher locations may supply identical pinned bytes; no version is
substituted when a URL disappears.

`retain.py sources` verifies already retained source RPMs. When the exact source
RPM is unavailable, it recovers the complete source directory from the anonymous
public OBS API at the source digest embedded in the verified binary's `DISTURL`.
The source-entry set is checked against that original OBS digest, every file
against its published digest/size, and all retained bytes receive SHA256 hashes.
OBS's original MD5 addressing is recorded as provenance, not described as a new
cryptographic signature. Multibuild flavors resolve to the shared source package
at the same exact digest. Unexpanded source links, changed cached listings,
traversal and mismatched bytes fail. No package/source script is executed.

`verify_payload.py` compares actual system tool/library/header/module files with
the retained signed RPM payload metadata. Generated library-selection links have
separate records and must resolve to a verified retained target. Dynamic-loader,
MIME and character-conversion caches are observed/generated resources, not
misrepresented as shipped RPM bytes. User homes and unrelated host configuration
are outside file-reading scope. Missing/unreadable files and non-selected changes
remain counted; selected build-input differences fail.

Run each command with the host Python, which supplies the existing RPM bindings:

```sh
python3 inventory.py --observation TOOL_OBSERVATION.json \
  --runtime-observation RUNTIME_OBSERVATION.json \
  --support-manifest ../qgis/support-inputs.json --catalogs CATALOGS.json \
  --package glibc-devel --package libstdc++6-devel-gcc15 --output SELECTION.json
python3 retain.py binaries --manifest SELECTION.json --retained CUSTODY --output BINARY_RECEIPT.json
python3 retain.py sources --manifest SELECTION.json --retained CUSTODY --output SOURCE_RECEIPT.json
python3 verify_payload.py --manifest SELECTION.json --retained CUSTODY --output PAYLOAD_RECEIPT.json
python3 -m unittest discover -s . -v
```

The actual invocation additionally selects the recorded shell/build/archive
utilities; the selection manifest preserves that full list. Collection can exit
nonzero for unavailable source-RPM metadata even when the later source recovery
retains the exact OBS build inputs. Keep the original diagnostic and the separate
source recovery proof; do not rename an OBS source directory as an original RPM.

`summarize.py` binds the selection, binary/source/payload receipts and retained
no-network replay, checks the additional observed system paths, and projects
only selected custody data into a public lock. It rejects missing packages,
source groups, provider dependencies, payload coverage and failed replay. It
does not replace actual signature or payload verification.

This work establishes input custody and current installed-file correspondence.
It does not backdate observations to earlier build starts, independently rebuild
the compiler/bootstrap chain, reproduce generated OS caches, install a clean
base OS, clear distribution rights, or satisfy OWN-02 by itself. The exact
development host is openSUSE Tumbleweed x86_64; no other platform is certified.
