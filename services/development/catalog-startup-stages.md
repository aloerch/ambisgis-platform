# Catalog initializer phases

Catalog initialization now attaches a finite stage to failures in configuration
inputs, persistent identity/key setup, Django setup, model imports, advisory
locking, migrations, catalog bootstrap, static files and advisory unlock.
The existing database/native calls and ordering are unchanged.

Fixed import, missing-attribute/name and Django configuration categories make
startup failures more useful without emitting exception messages, arbitrary
class names, paths, DSNs, child output, SQL or tracebacks. The installer accepts
only the matching finite contract. Nested phases retain the inner failure.

Attempt010 only established an entrypoint/unexpected failure. The new phase
records require a subsequent actual run; they do not retrospectively identify
that cause. Focused tests exercise real initializer input/identity/setup/import
failures with inert boundary doubles. They do not run native migrations.

Attempt011 reached `catalog_setup` and emitted `module_missing/import`. The
missing module and the cause of that actual failure remain unknown. Static
inspection of the exact retained GDAL wheel shows that `osgeo` catches an
`ImportError` from importing `osgeo._gdal` and then tries `_gdal`; that fallback
can mask an earlier import failure. This source path is a diagnostic hypothesis,
not a finding about the actual failed installation.

The next diagnostic increment recognizes only exact builtin
`ModuleNotFoundError` values whose builtin `ImportError.name` slot contains the
exact string `_gdal` or `osgeo._gdal`. It emits `gdal_extension_missing/import`.
If the builtin exception context slot contains an exact builtin `ImportError`,
it emits `gdal_extension_import_failed/import` instead. The latter records the
exception-chain shape; it does not establish a missing file, library, symbol,
ABI mismatch or other root cause. Unknown names remain `module_missing/import`,
and subclasses receive no new recognition. Neither names nor context values,
messages or paths are printed. No additional fields are accepted by the CLI.
Focused inert tests cover both codes, unknown and hostile values, builtin-slot
shadowing, nested phases, cleanup metadata and the existing bounded CLI parser.
Catalog operations, dependencies and native loading behavior are unchanged.
