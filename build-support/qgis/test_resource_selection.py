import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import resource_selection as selection
import runtime


def fixture():
    rows=[]; findings=[]
    for key,total in selection.EXPECTED.items():
        scopes={"SRC-01":19,"SRC-02":2,"SRC-03":1,"SRC-04":1}[key]
        notices=[]
        for index in range(scopes):
            directory=key.lower()+"/scope"+str(index)
            notice={"source_path":selection.SOURCE_RESOURCE+directory+"/COPYING.xml","sha256":"a"*64}
            count=total//scopes+(index < total%scopes)
            notice["selected_svg_files"]=count;notices.append(notice)
            rows.append({"path":"share/qgis/"+notice["source_path"],"sha256":"a"*64,"bytes":1})
            for number in range(count):
                rows.append({"path":selection.RESOURCE+directory+"/palette"+str(number)+".svg","sha256":"b"*64,"bytes":1})
        findings.append({"id":key,"subject":"recorded scope","notice_files":notices})
    for index in range(265):rows.append({"path":selection.RESOURCE+"cb/"+str(index)+".svg","sha256":"c"*64,"bytes":1})
    return rows,findings


class SelectionTests(unittest.TestCase):
    def test_exact_partition_and_colorbrewer(self):
        rows,findings=fixture();before=copy.deepcopy((rows,findings))
        result=selection.derive_selection(rows,findings)
        self.assertEqual({k:v["count"] for k,v in result["groups"].items()},selection.EXPECTED)
        self.assertEqual(len(result["exclusions"]),1129);self.assertEqual(len(result["colorbrewer"]),265)
        self.assertEqual((rows,findings),before)

    def test_duplicate_paths_rejected(self):
        rows,findings=fixture();rows.append(rows[0])
        with self.assertRaisesRegex(ValueError,"duplicate"):selection.derive_selection(rows,findings)

    def test_overlap_rejected(self):
        rows,findings=fixture();findings[1]["notice_files"][0]=findings[0]["notice_files"][0]
        with self.assertRaisesRegex(ValueError,"overlapping"):selection.derive_selection(rows,findings)

    def test_count_mismatch_rejected(self):
        rows,findings=fixture();rows.pop(2)
        with self.assertRaisesRegex(ValueError,"count mismatch"):selection.derive_selection(rows,findings)

    def test_notice_hash_mismatch_rejected(self):
        rows,findings=fixture();rows[0]["sha256"]="d"*64
        with self.assertRaisesRegex(ValueError,"notice binding"):selection.derive_selection(rows,findings)

    def test_colorbrewer_missing_rejected(self):
        rows,findings=fixture();rows.pop()
        with self.assertRaisesRegex(ValueError,"ColorBrewer"):selection.derive_selection(rows,findings)

    def test_nineteen_notice_scopes_required(self):
        rows,findings=fixture();findings[0]["notice_files"].pop()
        with self.assertRaisesRegex(ValueError,"scope count"):selection.derive_selection(rows,findings)

    def test_unsafe_paths_rejected(self):
        for path in ("../foo","/foo","foo/../bar","foo//bar"):
            with self.subTest(path=path), self.assertRaises(ValueError):selection.safe_path(path)

    def test_catalogue_semantic_scope_does_not_remove_esdb(self):
        data=b'<selection><gradients><gradient dir="es/a" file="one"/><gradient dir="esdb" file="two"/></gradients><seealsocollects><collect dir="jm">name</collect></seealsocollects></selection>'
        result,removed=selection.trim_catalogue(data,["es","jm"])
        self.assertEqual(len(removed),2);self.assertIn(b'esdb',result);self.assertNotIn(b'dir="es/a"',result)
        self.assertEqual(selection.trim_catalogue(result,["es","jm"]),(result,[]))

    def test_unknown_xml_reference_fails(self):
        with self.assertRaisesRegex(ValueError,"unexpected"):selection.trim_catalogue(b'<selection><other dir="es/a"/></selection>',["es"])

    def test_container_magic_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/"hidden.dat").write_bytes(b"PK\x03\x04payload")
            with self.assertRaisesRegex(ValueError,"container"):
                selection.audit_packaged_references(root,{"exclusions":[selection.RESOURCE+"es/a.svg"],"omitted_collection_roots":[selection.RESOURCE+"es"]})

    def test_database_embedded_reference_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);connection=sqlite3.connect(root/"hidden.dat")
            connection.execute("CREATE TABLE styles (payload TEXT)");connection.execute("INSERT INTO styles VALUES (?)",("es/a",));connection.commit();connection.close()
            with self.assertRaisesRegex(ValueError,"embedded in database"):
                selection.audit_packaged_references(root,{"exclusions":[selection.RESOURCE+"es/a.svg"],"omitted_collection_roots":[selection.RESOURCE+"es"]})

    def test_style_variant_reference_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/"style.xml").write_text('<style><Option name="schemeName" value="es/autumn"/></style>')
            with self.assertRaisesRegex(ValueError,"packaged style"):
                selection.audit_packaged_references(root,{"exclusions":[selection.RESOURCE+"es/autumn_01.svg"],"omitted_collection_roots":[selection.RESOURCE+"es"]})

    def test_runtime_output_roots_and_escapes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/"qgis-candidate";old.mkdir()
            with patch.object(runtime,"TASK",old):
                self.assertEqual(runtime.validate_output(old/"fresh"),old/"fresh")
                variant=root/"frontend-qgis-remediation/qgis";variant.mkdir(parents=True)
                self.assertEqual(runtime.validate_output(variant/"fresh"),variant/"fresh")
                for path in (old,variant,root/"elsewhere",variant/".."/"escape"):
                    with self.subTest(path=path), self.assertRaises(AssertionError):runtime.validate_output(path)
                outside=root/"outside";outside.mkdir();(variant/"escape").symlink_to(outside,target_is_directory=True)
                with self.assertRaises(AssertionError):runtime.validate_output(variant/"escape/new")


if __name__ == "__main__":unittest.main()
