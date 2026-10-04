"""Activate the retained setuptools compatibility provider in the owned image.

The custom PYTHONPATH directory is not a site-packages directory: Python does
not process its .pth files. Invoke the one retained shim explicitly instead.
"""
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType

SITE = Path('/opt/ambisgis/python-site')
# Selection pins from the retained setuptools 82.0.1 wheel. The image inventory
# still binds every member; these pins select the bootstrap and provider entry.
SOURCES = {
    '_distutils_hack/__init__.py': 'df81e6bcba34ee3e3952f776551fb669143b9490fdd6c4caeb32609f97e985b4',
    'setuptools/__init__.py': 'f94b531bda5d7846646222054faf51724302ab151d5482e38f6e20dea789feb7',
    'setuptools/_distutils/__init__.py': 'c4662e856c0b1b4ec9d10e3d0559c48cfcbac320dc77abde24c0c95fb9639723',
    'setuptools/_distutils/version.py': 'bc8993e7e1025e4436d6828bd17605893a8ae8dc8cd3d729cc136803fdf80905',
}
ERROR = 'Owned catalog compatibility provider is unavailable'


def _origin(module, expected):
    if not isinstance(module, ModuleType) or vars(module).get('__file__') != str(expected):
        raise ImportError(ERROR)


def activate_distutils():
    """Select only the bundled provider, before any Django/catalog import."""
    for relative, expected in SOURCES.items():
        source = SITE / relative
        if source.resolve() != source or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ImportError(ERROR)
    # Reject an ambient provider/customizer instead of accepting a host fallback.
    if importlib.util.find_spec('_distutils_system_mod') is not None:
        raise ImportError(ERROR)
    for name, module in tuple(sys.modules.items()):
        if name == 'distutils' or name.startswith('distutils.'):
            if not isinstance(module, ModuleType): raise ImportError(ERROR)
            origin = vars(module).get('__file__')
            # The retained provider has two implicit compiler namespaces.
            namespaces = {'distutils.compilers': 'compilers', 'distutils.compilers.C': 'compilers/C'}
            if origin is None and name in namespaces:
                if list(vars(module).get('__path__', ())) != [str(SITE / 'setuptools/_distutils' / namespaces[name])]:
                    raise ImportError(ERROR)
            elif (not isinstance(origin, str) or Path(origin).resolve() != Path(origin)
                  or not Path(origin).is_relative_to(SITE / 'setuptools/_distutils')):
                raise ImportError(ERROR)
        if name in ('_distutils_hack', 'setuptools'):
            _origin(module, SITE / name / '__init__.py')
    for name in ('_distutils_hack', 'setuptools'):
        spec = importlib.util.find_spec(name)
        if spec is None or spec.origin != str(SITE / name / '__init__.py'):
            raise ImportError(ERROR)
    os.environ['SETUPTOOLS_USE_DISTUTILS'] = 'local'
    hook = importlib.import_module('_distutils_hack')
    _origin(hook, SITE / '_distutils_hack/__init__.py')
    hook.add_shim()
    provider = importlib.import_module('distutils')
    version = importlib.import_module('distutils.version')
    _origin(provider, SITE / 'setuptools/_distutils/__init__.py')
    _origin(version, SITE / 'setuptools/_distutils/version.py')
