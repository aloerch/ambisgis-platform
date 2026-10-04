"""Owned compatibility activation order and fail-closed selection guards.

The separate pinned Python 3.12 witness exercises the real retained provider.
These portable tests use synthetic modules and files, with no product startup.
"""
import hashlib
import importlib.machinery
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/development'))
from ambisgis_development import catalog, catalog_compat as compat


class CatalogDistutilsTests(unittest.TestCase):
    def test_activation_precedes_framework_import_and_setup_for_both_roles(self):
        original = __import__
        for role in ('catalog', 'catalog-init'):
            with self.subTest(role=role):
                observed = []
                django = ModuleType('django')
                django.setup = lambda: observed.append('setup')
                def importing(name, *args, **kwargs):
                    if name == 'django':
                        observed.append('import')
                        self.assertEqual(observed, ['activate', 'import'])
                        return django
                    return original(name, *args, **kwargs)
                with patch.object(compat, 'activate_distutils', side_effect=lambda: observed.append('activate')), patch('builtins.__import__', side_effect=importing), patch.dict(compat.os.environ):
                    catalog.setup(role)
                self.assertEqual(observed, ['activate', 'import', 'setup'])

    def fixture(self, root):
        sources = {}
        for relative in compat.SOURCES:
            p = root / relative; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'# synthetic provider file\n')
            sources[relative] = hashlib.sha256(p.read_bytes()).hexdigest()
        modules = {}
        for name, relative in [('_distutils_hack', '_distutils_hack/__init__.py'), ('setuptools', 'setuptools/__init__.py'), ('distutils', 'setuptools/_distutils/__init__.py'), ('distutils.version', 'setuptools/_distutils/version.py')]:
            mod = ModuleType(name); mod.__file__ = str(root / relative); modules[name] = mod
        modules['_distutils_hack'].add_shim = lambda: None
        def spec(name):
            if name == '_distutils_system_mod': return None
            return importlib.machinery.ModuleSpec(name, None, origin=modules[name].__file__)
        return sources, modules, spec

    def activate(self, root, sources, modules, spec):
        with patch.object(compat, 'SITE', root), patch.object(compat, 'SOURCES', sources), patch.object(compat.sys, 'modules', {}), patch.object(compat.importlib.util, 'find_spec', side_effect=spec), patch.object(compat.importlib, 'import_module', side_effect=modules.__getitem__):
            compat.activate_distutils()

    def test_fixed_local_selection_and_repeated_activation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(compat.os.environ, {'SETUPTOOLS_USE_DISTUTILS': 'stdlib'}):
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            self.activate(root, sources, modules, spec)
            self.activate(root, sources, modules, spec)
            self.assertEqual(compat.os.environ['SETUPTOOLS_USE_DISTUTILS'], 'local')

    def test_missing_or_changed_source_fails_before_hook(self):
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); sources, modules, spec = self.fixture(root)
                target = root / '_distutils_hack/__init__.py'
                if missing: target.unlink()
                else: target.write_text('# changed')
                with patch.object(compat.importlib, 'import_module') as imported:
                    with self.assertRaises(ImportError): self.activate(root, sources, modules, spec)
                    imported.assert_not_called()

    def test_source_symlink_fails_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            p = root / '_distutils_hack/__init__.py'; target = root / 'redirect.py'
            target.write_bytes(p.read_bytes()); p.unlink(); p.symlink_to(target)
            with self.assertRaises(ImportError): self.activate(root, sources, modules, spec)

    def test_external_spec_cannot_select_host_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            def foreign(name):
                if name == 'setuptools': return importlib.machinery.ModuleSpec(name, None, origin='/host/setuptools/__init__.py')
                return spec(name)
            with self.assertRaises(ImportError): self.activate(root, sources, modules, foreign)

    def test_system_customizer_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            def custom(name):
                return importlib.machinery.ModuleSpec(name, None, origin='/host/custom.py') if name == '_distutils_system_mod' else spec(name)
            with self.assertRaises(ImportError): self.activate(root, sources, modules, custom)

    def test_preloaded_foreign_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            for name in ('distutils', 'distutils.version', '_distutils_hack', 'setuptools'):
                with self.subTest(name=name):
                    bad = ModuleType(name); bad.__file__ = '/host/foreign.py'
                    with patch.object(compat, 'SITE', root), patch.object(compat, 'SOURCES', sources), patch.object(compat.sys, 'modules', {name: bad}), patch.object(compat.importlib.util, 'find_spec', side_effect=spec), patch.object(compat.importlib, 'import_module') as imported:
                        with self.assertRaises(ImportError): compat.activate_distutils()
                        imported.assert_not_called()

    def test_preloaded_traversal_origin_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            bad = ModuleType('distutils.foreign')
            bad.__file__ = str(root / 'setuptools/_distutils/../../foreign.py')
            with patch.object(compat, 'SITE', root), patch.object(compat, 'SOURCES', sources), patch.object(compat.sys, 'modules', {'distutils.foreign': bad}), patch.object(compat.importlib.util, 'find_spec', side_effect=spec):
                with self.assertRaises(ImportError): compat.activate_distutils()

    def test_only_exact_retained_compiler_namespace_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            for paths, accepted in (([str(root / 'setuptools/_distutils/compilers')], True), ([], False), (['/host/compilers'], False), ([str(root / 'setuptools/_distutils/compilers'), '/host/compilers'], False)):
                with self.subTest(paths=paths):
                    namespace = ModuleType('distutils.compilers'); namespace.__file__ = None; namespace.__path__ = paths
                    with patch.object(compat, 'SITE', root), patch.object(compat, 'SOURCES', sources), patch.object(compat.sys, 'modules', {'distutils.compilers': namespace}), patch.object(compat.importlib.util, 'find_spec', side_effect=spec), patch.object(compat.importlib, 'import_module', side_effect=modules.__getitem__):
                        if accepted: compat.activate_distutils()
                        else:
                            with self.assertRaises(ImportError): compat.activate_distutils()

    def test_final_provider_origin_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources, modules, spec = self.fixture(root)
            modules['distutils.version'].__file__ = '/host/distutils/version.py'
            with self.assertRaises(ImportError): self.activate(root, sources, modules, spec)


if __name__ == '__main__': unittest.main()
