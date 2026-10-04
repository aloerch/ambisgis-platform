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
