# Retained catalog compatibility provider

The owned catalog image projects wheels into `/opt/ambisgis/python-site` and
selects that directory through `PYTHONPATH`. Python 3.12 does not process `.pth`
files in arbitrary `PYTHONPATH` directories. Its removed standard-library
`distutils` is therefore not restored merely by copying the retained setuptools
wheel and its `distutils-precedence.pth` file.

A completed, isolated setup-only replay observed the intrinsic missing-module
name `distutils`. This identifies a missing import in that replay, not the exact
first importing module or the cause of every previous installation failure.
The retained source contains a setup-reachable chain from Django app readiness
through GeoNode harvesting API routers to DRF extensions' `utils.py`, which
imports `distutils.version.LooseVersion`.

`catalog.setup` now activates the exact retained setuptools 82.0.1 shim before
importing Django, for both initialization and serving. The first-party helper
checks fixed bootstrap/provider fingerprints and origins, selects `local`, calls
`_distutils_hack.add_shim()`, and verifies that `distutils` and `distutils.version`
resolve to the bundled `setuptools/_distutils` implementation. It rejects a
foreign preloaded provider or system customizer. Repeated activation supports
the retained provider's two exact compiler namespace packages. This bootstrap
uses no general `.pth` evaluator, package installer, alternate dependency version
or network fallback. Full image member custody remains the image manifest's
responsibility; these small entry-point fingerprints do not replace it.

The retained wheel SHA256 is
`a59e362652f08dcd477c78bb6e7bd9d80a7995bc73ce773050228a348ce2e5bb`.
Its existing source, licenses and notices remain unchanged.

The bounded import witness uses the retained Python 3.12 interpreter with
`-I -S -B`, a fresh byte-verified wheel projection and the actual `catalog.setup`
function. Django setup is replaced only in this witness with the exact retained
DRF `distutils.version` import statement: no database, GIS library, Django model
setup, container or service is executed. The original setup fails with the
observed missing-module name; the corrected setup resolves the retained provider
for both roles and on repeated activation. An unrelated `.pth` sentinel remains
unexecuted. Portable tests cover ordering, changed/missing sources, origins,
preloaded providers, namespace identity and fixed environment selection.

An initial candidate guard incorrectly rejected the provider's implicit compiler
namespaces on repeated activation. That failed witness is retained; the final
candidate admits only the two exact retained namespace paths. Real catalog
startup, migrations, serving, authorization and all remaining PLT-01 installation
criteria still require actual subsequent verification.
