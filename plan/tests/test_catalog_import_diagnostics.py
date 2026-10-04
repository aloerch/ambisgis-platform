"""Finite GDAL hints use builtin exception slots, never arbitrary error values."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services/development"))
from ambisgis_development import startup_diagnostics as service
from installer import diagnostics as installer


class CatalogImportDiagnostics(unittest.TestCase):
    def project(self, error, code, *, cleanup=False):
        wrapped = service.StartupFailure("catalog_setup", error, cleanup_failed=cleanup)
        record = service.failure_record(wrapped)
        fields = {"stage": "catalog_setup", "code": code,
                  "category": "unexpected" if code == "unexpected" else "import"}
        if cleanup:
            fields["cleanup_failed"] = True
        self.assertEqual({key: record[key] for key in fields}, fields)
        self.assertEqual(set(record), set(fields) | {"event", "detail"})
        encoded = json.dumps(record).encode()
        self.assertNotIn(b"private-credential", encoded)
        self.assertNotIn(b"/private/path", encoded)
        self.assertEqual(installer.from_streams(b"", encoded), fields)
        envelope = {"command": "up", "ok": False, "error": "Fixed failure.",
                    "startup_failure": fields}
        self.assertEqual(installer.from_cli(json.dumps(envelope).encode(), "up"), fields)
        return record

    def test_only_two_exact_builtin_names_get_fixed_missing_code(self):
        for name in ("_gdal", "osgeo._gdal"):
            with self.subTest(name=name):
                self.project(ModuleNotFoundError("private-credential", name=name,
                             path="/private/path"), "gdal_extension_missing")

    def test_real_exception_chaining_retains_fixed_masked_import_hint(self):
        for name in ("_gdal", "osgeo._gdal"):
            with self.subTest(name=name):
                try:
                    try:
                        raise ImportError("private-credential", name="private-credential",
                                          path="/private/path")
                    except ImportError:
                        raise ModuleNotFoundError("private-credential", name=name) from None
                except ModuleNotFoundError as error:
                    self.project(error, "gdal_extension_import_failed", cleanup=True)

    def test_unknown_names_remain_generic_even_with_import_context(self):
        for name in (None, "", "osgeo", "_gdal_extra", "OSGEO._gdal",
                     "private-credential", "/private/path/_gdal", "_gdal\n", b"_gdal"):
            with self.subTest(name=name):
                error = ModuleNotFoundError("private-credential", name=name)
                error.__context__ = ImportError("private-credential")
                self.project(error, "module_missing")

    def test_name_slot_rejects_hostile_objects_without_comparison_or_formatting(self):
        calls = []
        class Hostile:
            def __eq__(self, other): calls.append("equality"); raise AssertionError()
            def __str__(self): calls.append("string"); raise AssertionError()
            def __repr__(self): calls.append("repr"); raise AssertionError()
            def __hash__(self): calls.append("hash"); raise AssertionError()
        class HostileString(str):
            def __eq__(self, other): calls.append("string-equality"); raise AssertionError()
            def __str__(self): calls.append("string-format"); raise AssertionError()
            def __hash__(self): calls.append("string-hash"); raise AssertionError()
        for name in (Hostile(), HostileString("_gdal")):
            self.project(ModuleNotFoundError("private-credential", name=name), "module_missing")
        self.assertEqual(calls, [])

    def test_exception_subclass_attributes_and_metaclass_equality_are_never_read(self):
        calls = []
        class HostileMeta(type):
            def __eq__(cls, other): calls.append("class-equality"); raise AssertionError()
            def __getattribute__(cls, key):
                if key in ("__name__", "__module__"):
                    calls.append("class-attribute"); raise AssertionError()
                return super().__getattribute__(key)
        class HostileError(ModuleNotFoundError, metaclass=HostileMeta):
            def __getattribute__(self, key): calls.append("instance-attribute"); raise AssertionError()
            def __str__(self): calls.append("string"); raise AssertionError()
        self.project(HostileError("private-credential", name="_gdal"), "unexpected")
        self.assertEqual(calls, [])

    def test_only_exact_importerror_context_gets_masked_hint(self):
        calls = []
        class HostileContext(ImportError):
            def __getattribute__(self, key): calls.append(key); raise AssertionError()
            def __eq__(self, other): calls.append("equality"); raise AssertionError()
            def __str__(self): calls.append("string"); raise AssertionError()
        for context in (None, ModuleNotFoundError("private-credential"),
                        RuntimeError("private-credential"), HostileContext("private-credential")):
            error = ModuleNotFoundError("private-credential", name="_gdal")
            error.__context__ = context
            self.project(error, "gdal_extension_missing")
        self.assertEqual(calls, [])

    def test_builtin_slots_ignore_shadow_dictionary_and_cause(self):
        error = ModuleNotFoundError("private-credential", name="_gdal")
        error.__dict__.update(name="private-credential", __context__=ImportError("private-credential"))
        error.__cause__ = ImportError("private-credential")
        self.project(error, "gdal_extension_missing")
        unknown = ModuleNotFoundError("private-credential", name="private-credential")
        unknown.__dict__["name"] = "_gdal"
        self.project(unknown, "module_missing")

    def test_nested_stages_and_cleanup_preserve_new_finite_codes(self):
        try:
            with service.stage("catalog_bootstrap"):
                with service.stage("catalog_setup"):
                    raise ModuleNotFoundError("private-credential", name="osgeo._gdal")
        except service.StartupFailure as error:
            record = service.failure_record(service.StartupFailure("catalog_unlock", error,
                                                                     cleanup_failed=True))
        self.assertEqual(record["stage"], "catalog_setup")
        self.assertEqual(record["code"], "gdal_extension_missing")
        self.assertTrue(record["cleanup_failed"])
        self.assertNotIn("private-credential", json.dumps(record))

    def test_contract_accepts_only_fixed_codes_with_import_category(self):
        self.assertEqual(service.CATEGORIES, installer.CATEGORIES)
        for code in ("gdal_extension_missing", "gdal_extension_import_failed"):
            fields = {"stage": "catalog_setup", "code": code, "category": "import"}
            self.assertEqual(installer.startup_fields(fields), fields)
            self.assertTrue(service.valid(fields))
            self.assertIsNone(installer.startup_fields(dict(fields, category="unexpected")))
            self.assertIsNone(installer.startup_fields(dict(fields, module="_gdal")))
        self.assertIsNone(installer.startup_fields({"stage": "catalog_setup",
                          "code": "gdal_private-credential", "category": "import"}))


if __name__ == "__main__":
    unittest.main()
