"""Safety tests for data-only schema capsules; no network or extracted files."""
import hashlib
import io
import stat
import unittest
from unittest.mock import patch
import warnings
import zipfile

import schema_resources as schema


GAV = "org.geotools.schemas:cgiutilities-1.0:1.0.0-4"
PATH = "org/geotools/schemas/cgiutilities-1.0/1.0.0-4/cgiutilities-1.0-1.0.0-4.jar"
XSD = b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><!-- original notice --></xs:schema>'


def capsule(gav=GAV, extra=(), resources=True):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if resources:
            for name in schema.RESOURCES[gav]:
                archive.writestr(name, XSD if name.endswith(".xsd") else b"<dictionary/>")
        for name, data in extra:
            archive.writestr(name, data)
    return stream.getvalue()


def pom(gav=GAV):
    group, artifact, version = gav.split(":")
    return (f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
            f'<groupId>{group}</groupId><artifactId>{artifact}</artifactId><version>{version}</version>'
            '</project>').encode()


class SchemaResourceTests(unittest.TestCase):
    def test_all_nine_exact_capsules_report_original_members_and_sources(self):
        self.assertEqual(len(schema.RESOURCES), 9)
        self.assertEqual(sum(len(paths) for paths in schema.RESOURCES.values()), 73)
        for gav, resources in schema.RESOURCES.items():
            group, artifact, version = gav.split(":")
            path = f'{group.replace(".", "/")}/{artifact}/{version}/{artifact}-{version}.jar'
            with self.subTest(gav=gav):
                data = capsule(gav)
                report = schema.validate_schema_archive(path, data)
                self.assertEqual(report["gav"], gav)
                self.assertEqual(report["resource_count"], len(resources))
                self.assertEqual(report["missing_resources"], [])
                self.assertEqual(report["artifact_sha256"], hashlib.sha256(data).hexdigest())
                self.assertFalse(report["license_approval"])
                self.assertTrue(all(row["declared_source_url"] == resources[row["path"]]
                                    for row in report["members"]))

    def test_unknown_versions_classifiers_and_coordinates_have_no_exception(self):
        for path in (PATH.replace("1.0.0-4", "1.0.0-5"), PATH.replace(".jar", "-sources.jar"),
                     PATH.replace("cgiutilities", "unknown"), PATH + ".zip"):
            with self.subTest(path=path):
                self.assertIsNone(schema.schema_coordinate(path))
                with self.assertRaises(schema.SchemaResourceError):
                    schema.validate_schema_archive(path, capsule())
        self.assertEqual(schema.schema_checksum(PATH + ".sha1"), (PATH, "sha1"))
        self.assertIsNone(schema.schema_checksum(PATH + ".asc"))

    def test_partial_resource_capsule_is_rejected(self):
        resource = next(iter(schema.RESOURCES[GAV]))
        with self.assertRaisesRegex(schema.SchemaResourceError, "omits required"):
            schema.validate_schema_archive(PATH, capsule(resources=False, extra=[(resource, XSD)]))

    def test_embedded_pom_properties_manifest_and_notice_are_retained(self):
        prefix = "META-INF/maven/org.geotools.schemas/cgiutilities-1.0/"
        data = capsule(extra=[(prefix + "pom.xml", pom()),
                              (prefix + "pom.properties", b"groupId=org.geotools.schemas\nartifactId=cgiutilities-1.0\nversion=1.0.0-4\n"),
                              ("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\nCreated-By: Maven\n"),
                              ("META-INF/LICENSE.txt", b"Original retained license text\n")])
        report = schema.validate_schema_archive(PATH, data)
        self.assertTrue(report["embedded_pom_present"])
        self.assertEqual(report["notices"], ["META-INF/LICENSE.txt"])
        notices = [row for row in report["members"] if row["kind"] == "original-notice"]
        self.assertEqual(notices[0]["sha256"], hashlib.sha256(b"Original retained license text\n").hexdigest())

    def test_embedded_pom_and_properties_must_match_coordinate(self):
        prefix = "META-INF/maven/org.geotools.schemas/cgiutilities-1.0/"
        for name, value in ((prefix + "pom.xml", pom(GAV.replace("1.0.0-4", "2.0"))),
                            (prefix + "pom.properties", b"groupId=other\nartifactId=cgiutilities-1.0\nversion=1.0.0-4"),
                            ("META-INF/maven/other/other/pom.xml", pom())):
            with self.subTest(name=name), self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, capsule(extra=[(name, value)]))

    def test_embedded_recipe_cannot_change_declared_resources(self):
        recipe = pom().replace(b"</project>", b'<build><get src="https://wrong.example/x.xsd" dest="${project.build.outputDirectory}/wrong.xsd"/></build></project>')
        with self.assertRaisesRegex(schema.SchemaResourceError, "recipe differs"):
            schema.validate_schema_archive(PATH, capsule(extra=[("META-INF/maven/org.geotools.schemas/cgiutilities-1.0/pom.xml", recipe)]))

    def test_class_native_script_and_nested_archives_are_rejected(self):
        for name in ("Bad.class", "libbad.so", "bad.dll", "run.sh", "nested.jar", "nested.zip",
                     "META-INF/services/extension", "META-INF/LICENSE.class"):
            with self.subTest(name=name), self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, capsule(extra=[(name, b"payload")]))

    def test_resource_suffix_is_not_enough_without_actual_xml_schema(self):
        resource = next(iter(schema.RESOURCES[GAV]))
        for data in (b"\xca\xfe\xba\xbeclass", b"#!/bin/sh\nexit 1\n", b"<not-a-schema/>", b"<xs:schema"):
            with self.subTest(data=data), self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, capsule(resources=False, extra=[(resource, data)]))

    def test_path_traversal_duplicate_and_symlink_members_are_rejected(self):
        for path in ("../bad.xsd", "/bad.xsd", "net/../bad.xsd", "net//bad.xsd", "net\\bad.xsd"):
            with self.subTest(path=path), self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, capsule(extra=[(path, XSD)]))
        name = next(iter(schema.RESOURCES[GAV]))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            duplicate = capsule(extra=[(name, XSD)])
        with self.assertRaisesRegex(schema.SchemaResourceError, "duplicate"):
            schema.validate_schema_archive(PATH, duplicate)
        info = zipfile.ZipInfo(name)
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(schema.SchemaResourceError, "symlink"):
            schema.validate_schema_archive(PATH, capsule(resources=False, extra=[(info, b"outside")]))

    def test_decompression_bombs_and_member_limits_are_rejected(self):
        name = next(iter(schema.RESOURCES[GAV]))
        bomb = XSD.replace(b"original notice", b"A" * 1000000)
        with self.assertRaisesRegex(schema.SchemaResourceError, "bounds"):
            schema.validate_schema_archive(PATH, capsule(resources=False, extra=[(name, bomb)]))
        with patch.object(schema, "MAX_MEMBER_BYTES", 8):
            with self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, capsule())
        with patch.object(schema, "MAX_MEMBERS", 1):
            with self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, capsule())

    def test_manifest_execution_attributes_and_no_xsd_are_rejected(self):
        for key in ("Main-Class", "Class-Path", "Premain-Class", "Agent-Class", "Launcher-Agent-Class"):
            with self.subTest(key=key), self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, capsule(extra=[("META-INF/MANIFEST.MF", ("Manifest-Version: 1.0\n" + key + ": bad\n").encode())]))
        with self.assertRaisesRegex(schema.SchemaResourceError, "no actual XSD"):
            schema.validate_schema_archive(PATH, capsule(resources=False, extra=[("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\n")]))

    def test_xml_entities_doctype_and_stylesheet_instructions_are_rejected(self):
        name = next(iter(schema.RESOURCES[GAV]))
        for xml in ('<!DOCTYPE x [<!ENTITY e "bad">]><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>',
                    '<?xml-stylesheet href="https://example.invalid/xsl"?><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>'):
            for encoding in ("utf-8", "utf-16"):
                with self.subTest(encoding=encoding), self.assertRaises(schema.SchemaResourceError):
                    schema.validate_schema_archive(PATH, capsule(resources=False, extra=[(name, xml.encode(encoding))]))

    def test_executable_prefix_and_trailing_payload_are_rejected(self):
        for data in (b"MZbad" + capsule(), capsule() + b"executable trailing bytes"):
            with self.subTest(prefix=data[:8]), self.assertRaises(schema.SchemaResourceError):
                schema.validate_schema_archive(PATH, data)


if __name__ == "__main__":
    unittest.main()
