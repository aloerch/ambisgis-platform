# Catalog GIS library selection

The development catalog sets Django's `GDAL_LIBRARY_PATH` to
`/opt/ambisgis/support/lib/libgdal.so` and `GEOS_LIBRARY_PATH` to
`/opt/ambisgis/support/lib/libgeos_c.so` after importing the owned GeoNode
settings. Both catalog initialization and serving use the same retained spatial
support libraries. Caller environment values and inherited settings cannot
redirect these paths; database role and credential selection are unchanged.

The selected image already includes the GDAL 3.10.3 and GEOS 3.13.1 support
libraries and their relative symlink chains. Django 5.2.15 otherwise calls
`ctypes.util.find_library`; the selected Linux CPython 3.12 implementation
depends on discovery tools absent from this minimal image. An
`LD_LIBRARY_PATH` entry alone does not replace those tools. This change adds no
package, host discovery command, environment fallback or library ABI change.

Run the portable inert configuration checks from the repository root:

```sh
python3 -B -m unittest discover -s plan/tests -p test_catalog_library_paths.py -v
```

The retained local loading witness additionally evaluates the exact pinned
Django GDAL selection statements and GEOS `load_geos` function against
synthetic Django settings, with discovery stubbed and a sentinel that stops
before `CDLL` can load anything. The original settings fail to select either
library; the repaired settings reach the sentinel with the two exact paths and
no discovery call. Process, socket and native library execution are denied.
These checks establish configuration and selection only, not native ABI
compatibility, successful migrations or installation acceptance.

The missing settings are a confirmed source packaging defect. Lifecycle009's
removed catalog initializer did not retain its underlying error, so its actual
failure cause remains unconfirmed until a separately authorized runtime check.
