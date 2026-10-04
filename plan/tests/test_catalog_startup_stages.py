"""Actual catalog startup failures retain finite phase evidence without child text."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services/development"))
from ambisgis_development import catalog, startup_diagnostics as diagnostics
from installer.diagnostics import from_streams

class CatalogStartupStages(unittest.TestCase):
    def fixture(self, tmp):
        data = Path(tmp)
        product = {"install_id": "1927f2e7-9f44-45a6-b430-20317f087fee"}
        (data / "installation.json").write_text(json.dumps({"schema_version": 1, "install_id": product["install_id"], "purpose": "developer-catalog"}))
        (data / "installation.json").chmod(0o600)
        key = data / "oidc-key.pem"; key.write_text("synthetic-existing-private-key"); key.chmod(0o600)
        return data, product

    def test_actual_setup_failure_keeps_phase_and_fixed_import_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, product = self.fixture(tmp)
            with patch.object(catalog, "DATA", data), patch.object(catalog, "inputs", return_value=(product, {})), patch.object(catalog, "setup", side_effect=ModuleNotFoundError("private-credential")):
                try: catalog.initialize()
                except Exception as error: record = diagnostics.failure_record(error)
                else: self.fail("failure must propagate")
            self.assertEqual(record["stage"], "catalog_setup")
            self.assertEqual(record["code"], "module_missing")
            self.assertEqual(record["category"], "import")
            self.assertNotIn("private-credential", json.dumps(record))
            self.assertEqual(from_streams(b"", json.dumps(record).encode()), {k: record[k] for k in ("stage", "code", "category")})

    def test_input_and_identity_failures_are_distinct(self):
        with patch.object(catalog, "inputs", side_effect=ValueError("private-credential")):
            try: catalog.initialize()
            except Exception as error: record = diagnostics.failure_record(error)
            else: self.fail("failure must propagate")
        self.assertEqual(record["stage"], "catalog_input")
        with tempfile.TemporaryDirectory() as tmp:
            data, product = self.fixture(tmp)
            (data / "installation.json").write_text("{}")
            with patch.object(catalog, "DATA", data), patch.object(catalog, "inputs", return_value=(product, {})), patch.object(catalog, "setup") as setup:
                try: catalog.initialize()
                except Exception as error: record = diagnostics.failure_record(error)
                else: self.fail("failure must propagate")
                setup.assert_not_called()
            self.assertEqual(record["stage"], "catalog_identity")
            self.assertEqual(record["category"], "validation")

    def test_model_import_failure_is_separate_from_framework_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, product = self.fixture(tmp)
            original = __import__
            def importing(name, *args, **kwargs):
                if name == "django.core.management": raise ImportError("private-credential")
                return original(name, *args, **kwargs)
            with patch.object(catalog, "DATA", data), patch.object(catalog, "inputs", return_value=(product, {})), patch.object(catalog, "setup"), patch("builtins.__import__", side_effect=importing):
                try: catalog.initialize()
                except Exception as error: record = diagnostics.failure_record(error)
                else: self.fail("failure must propagate")
            self.assertEqual(record["stage"], "catalog_models")
            self.assertEqual(record["code"], "import_failed")
            self.assertNotIn("private-credential", json.dumps(record))

    def test_fixed_error_categories_ignore_values_and_unrecognized_class_names(self):
        configured = type("ImproperlyConfigured", (Exception,), {"__module__": "django.core.exceptions"})
        foreign = type("PrivateCredential", (Exception,), {})
        cases = [(ImportError("private"), "import_failed"), (ModuleNotFoundError("private"), "module_missing"), (AttributeError("private"), "attribute_missing"), (NameError("private"), "name_missing"), (configured("private"), "configuration_failed"), (foreign("private"), "unexpected")]
        module = ModuleType("django.core.exceptions")
        module.ImproperlyConfigured = configured
        with patch.dict(sys.modules, {"django.core.exceptions": module}):
            for error, expected in cases:
                with self.subTest(expected=expected):
                    record = diagnostics.failure_record(diagnostics.StartupFailure("catalog_setup", error))
                    self.assertEqual(record["code"], expected)
                    self.assertNotIn("private", json.dumps(record).lower())
                    self.assertIsNotNone(from_streams(b"", json.dumps(record).encode()))

    def test_unknown_exception_metaclass_cannot_escape_projection(self):
        for forbidden in ("__module__", "__name__"):
            class Hostile(type):
                def __getattribute__(cls, key):
                    if key == forbidden: raise RuntimeError("private-credential")
                    return super().__getattribute__(key)
            class Unknown(Exception, metaclass=Hostile): pass
            with self.subTest(forbidden=forbidden):
                record = diagnostics.failure_record(diagnostics.StartupFailure("catalog_setup", Unknown("private-credential")))
                self.assertEqual(record["code"], "unexpected")
                self.assertNotIn("private-credential", json.dumps(record))

    def test_unknown_exception_equality_cannot_escape_projection(self):
        class Hostile(type):
            def __eq__(cls, other): raise RuntimeError("private-credential")
        class Unknown(Exception, metaclass=Hostile): pass
        record = diagnostics.failure_record(diagnostics.StartupFailure("catalog_setup", Unknown("private-credential")))
        self.assertEqual(record["code"], "unexpected")
        self.assertNotIn("private-credential", json.dumps(record))

    def test_nested_phase_preserves_original_failure(self):
        try:
            with diagnostics.stage("catalog_bootstrap"):
                with diagnostics.stage("catalog_models"):
                    raise ImportError("private-credential")
        except Exception as error: record = diagnostics.failure_record(error)
        self.assertEqual(record["stage"], "catalog_models")
        self.assertEqual(record["code"], "import_failed")
        self.assertNotIn("private-credential", json.dumps(record))

if __name__ == "__main__": unittest.main()
