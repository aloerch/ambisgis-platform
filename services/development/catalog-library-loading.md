# Catalog GIS library selection

The development catalog defines Django's `GDAL_LIBRARY_PATH` as
`/opt/ambisgis/support/lib/libgdal.so` and `GEOS_LIBRARY_PATH` as
`/opt/ambisgis/support/lib/libgeos_c.so` **before** importing the owned GeoNode
settings. It reasserts both fixed values after inheriting those settings.
Catalog initialization and serving therefore select the same retained support
libraries, including during settings import. Caller environment values and
inherited settings cannot redirect the paths; database roles and credentials
are unchanged.

The selected image includes GDAL 3.10.3 and GEOS 3.13.1 with their relative
symlink chains. Django 5.2.15 otherwise calls `ctypes.util.find_library`; the
selected Linux CPython 3.12 implementation depends on discovery tools absent
from this minimal image. An `LD_LIBRARY_PATH` entry alone does not replace
those tools. This change adds no dependency, host discovery command, environment
fallback or library ABI change.

Import order matters. The retained `geonode/settings.py` imports its serializer,
which imports GeoDjango GIS code. GIS library selection can therefore request
Django settings while the owned module is still importing. Django's settings
loader can re-enter that partially initialized module and see only values
already assigned. Defining these paths only after the inherited import is too
late.

Run the portable inert checks from the repository root:

```sh
python3 -B -m unittest discover -s plan/tests -p test_catalog_library_paths.py -v
```

The initial six configuration checks and retained loader witness exercised
completed settings with an inert inherited-settings stub. They missed this
early import boundary. The added regressions inspect the actual owned module
during the inherited import, for both roles and with hostile inherited values.
Their baseline fails before the pre-import definitions are added.

A separate retained witness evaluates the exact Django `Settings` class,
`LazySettings._setup` and `__getattr__` methods, and GIS library-selection
statements against synthetic inputs. A fixed import bridge represents the
statically inspected GeoNode serializer path; a sentinel stops before
`CDLL` loads native code. The late-definition baseline fails both selections;
the repaired source selects both exact owned paths without discovery and
preserves them after inheritance. Native, process and socket execution are
denied. The full dependency import graph is not executed by this witness.

The prior failures and witness limitations remain retained. These checks prove
configuration ordering and selection only, not native ABI compatibility,
successful migrations or installation acceptance. Lifecycle009 and lifecycle010
do not establish their catalog initializer's underlying cause; a separately
reviewed runtime check is still required.
