# Selected host inputs for FND-08

The [selected inventory](selected-inputs.json) records the Linux host compiler,
headers, build utilities, Python bootstrap modules and runtime providers used
by the initial owned builds. The [evidence](evidence.json) binds the original
private observations, acquisition receipts, signed-payload comparison and
no-network replay. The full host package list is not published.

There are 276 exact binary RPMs and 175 associated source groups: 69 retained
original source RPMs and 106 complete OBS build-source directories at the
revision recorded in the signed binary. These are distinct custody forms.
All 1,474 files in the OBS groups have retained size, original publisher digest
and SHA256 records. The original eight unavailable-source-RPM metadata
diagnostics are preserved; each associated source group was recovered through
the explicit OBS path. No binary version or source revision was substituted.

Current installed-file verification matched 24,889 payload files. All 244
selected system paths are covered with no blocking difference. The broader
package inventory also records 2,538 directories, 197 paths outside the
build-file scope, eight unreadable non-selected files and 25 unshipped ghost
entries. Three generated BLAS/LAPACK selection links resolve to verified
signed payloads. Dynamic-loader, MIME and character-conversion caches are
separately observed generated resources, with regeneration still unperformed.

The additional native/catalog/browser observation includes 157 paths, of
which 139 are system files. The remaining paths belong to retained tools or
new owned build outputs and remain in their component custody records. Its
linkage records are `ldd` resolutions, not claims of observed process mappings.
QGIS runtime observations separately include actual mapped libraries.

Independent review found two missing rejection cases: a cached source RPM
could bypass the exact signed build-revision comparison, and an OBS listing
could be written through an existing symlink before the later download guard.
Both are repaired in `4debc63`, with positive and negative tests. The final
retained replay uses those repaired helpers; 276 binaries and 175 source
groups verify with network calls prohibited. Failed earlier attempts and the
reviewer's original reproduction remain in private evidence.

The collector and projection are in [build-support/host-inputs](../../../build-support/host-inputs/README.md).
Their 19 guard tests cover identity drift, provider syntax, unresolved linkage,
source-entry digests, retained corruption, redirected destinations and
incomplete evidence. They are package/custody tests, not GIS product tests.

This observation is dated after the builds and is not backdated. No whole-host
reinstall, base-image reproduction, compiler/boot-JDK source rebuild, generated
cache reproduction, redistribution clearance or OWN-02 acceptance is claimed.
The tested development host is openSUSE Tumbleweed x86_64; a clean supported
product installer remains required.
