"""Inert catalog configuration checks; never import GeoNode or load native code."""
from contextlib import ExitStack
import ctypes
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "services/development/ambisgis_development/catalog_settings.py"
PATHS = {
    "GDAL_LIBRARY_PATH": "/opt/ambisgis/support/lib/libgdal.so",
    "GEOS_LIBRARY_PATH": "/opt/ambisgis/support/lib/libgeos_c.so",
}


def fixture_settings(source=SETTINGS, role="catalog", inherited=None):
    """Execute the owned settings with synthetic input and an inert source stub."""
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        data = Path(directory)
        (data / "oidc-key.pem").write_text("synthetic-private-key")
        common = ModuleType("_catalog_path_fixture.common")
        common.DATA = data
        common.inputs = lambda: (
            {"public_origin": "http://127.0.0.1:18080", "engine_origin": "http://engine:8080"},
            {"catalog_migrator": "synthetic-owner-password",
             "catalog_runtime": "synthetic-serving-password",
             "django_key": "synthetic-django-key", "policy_key": "synthetic-policy-key"},
        )
        source_settings = SimpleNamespace(OAUTH2_PROVIDER={}, **(inherited or {}))
        stack.enter_context(patch.dict(sys.modules, {common.__name__: common}))
        stack.enter_context(patch.dict(os.environ, {
            "AMBISGIS_SERVICE_ROLE": role,
            "GDAL_LIBRARY_PATH": "/caller/redirect-gdal.so",
            "GEOS_LIBRARY_PATH": "/caller/redirect-geos.so",
            "LD_LIBRARY_PATH": "/caller/libraries",
        }, clear=True))
        for target in ("subprocess.Popen", "subprocess.run", "socket.socket",
                       "ctypes.CDLL", "ctypes.PyDLL", "os.system"):
            stack.enter_context(patch(target, side_effect=AssertionError("external execution forbidden")))
        imported = stack.enter_context(patch("importlib.import_module", return_value=source_settings))
        spec = importlib.util.spec_from_file_location("_catalog_path_fixture.catalog_settings", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        imported.assert_called_once_with("geonode.settings")
        database_url = os.environ["DATABASE_URL"]
        return module, database_url


class CatalogLibraryPathsTests(unittest.TestCase):
    def test_serving_settings_select_owned_libraries_without_inherited_values(self):
        module, _ = fixture_settings()
        for name, path in PATHS.items():
            self.assertEqual(getattr(module, name, None), path)

    def test_migration_settings_select_the_same_owned_libraries(self):
        module, _ = fixture_settings(role="catalog-init")
        for name, path in PATHS.items():
            self.assertEqual(getattr(module, name, None), path)

    def test_inherited_library_paths_cannot_redirect_owned_selection(self):
        module, _ = fixture_settings(inherited={
            "GDAL_LIBRARY_PATH": "/inherited/redirect-gdal.so",
            "GEOS_LIBRARY_PATH": "/inherited/redirect-geos.so",
        })
        for name, path in PATHS.items():
            self.assertEqual(getattr(module, name, None), path)

    def test_missing_or_malformed_inherited_values_are_replaced(self):
        for value in (None, "", 42, ["untrusted"]):
            with self.subTest(value_type=type(value).__name__):
                module, _ = fixture_settings(inherited=dict.fromkeys(PATHS, value))
                self.assertEqual({name: getattr(module, name, None) for name in PATHS}, PATHS)

    def test_serving_role_keeps_runtime_credentials(self):
        module, url = fixture_settings()
        self.assertFalse(module.MIGRATING)
        self.assertEqual(module.DATABASE_ROLE, "ambisgis_catalog_app")
        self.assertIn("synthetic-serving-password@", url)
        self.assertNotIn("synthetic-owner-password", url)

    def test_initializer_keeps_separate_owner_credentials(self):
        module, url = fixture_settings(role="catalog-init")
        self.assertTrue(module.MIGRATING)
        self.assertEqual(module.DATABASE_ROLE, "ambisgis_catalog_owner")
        self.assertIn("synthetic-owner-password@", url)
        self.assertNotIn("synthetic-serving-password", url)


if __name__ == "__main__":
    unittest.main()
