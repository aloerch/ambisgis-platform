import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
import zipfile
import source_closure as sc
from resolution_inventory import InventoryError


def classfile(name='p/Foo', source='Foo.java'):
    def text(value):
        b=value.encode();return b'\x01'+struct.pack('>H',len(b))+b
    cp=[text(name),b'\x07\x00\x01',text('java/lang/Object'),b'\x07\x00\x03',text('SourceFile'),text(source or 'unused')]
    data=b'\xca\xfe\xba\xbe'+struct.pack('>HHH',0,52,7)+b''.join(cp)
    data+=struct.pack('>HHHHHHH',1,2,4,0,0,0,1 if source else 0)
    return data+(struct.pack('>HIH',5,2,6) if source else b'')


def zipbytes(members):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,data in members:z.writestr(name,data)
    return out.getvalue()


class SourceClosureTests(unittest.TestCase):
    def test_class_source_reads_exact_source_attribute(self):
        self.assertEqual(sc.class_source(classfile()),('p/Foo','Foo.java'))
    def test_missing_debug_attribute_stays_absent(self):
        self.assertEqual(sc.class_source(classfile(source=None)),('p/Foo',None))
    def test_reject_truncated_class(self):
        with self.assertRaises(sc.ClosureError):sc.class_source(classfile()[:-1])
    def test_reject_class_magic(self):
        with self.assertRaises(sc.ClosureError):sc.class_source(b'x'*100)
    def test_reject_trailing_class_bytes(self):
        with self.assertRaises(sc.ClosureError):sc.class_source(classfile()+b'x')
    def test_reject_class_source_path(self):
        with self.assertRaises(sc.ClosureError):sc.class_source(classfile(source='../Foo.java'))
    def test_source_attribute_package_mapping(self):
        report=sc.coverage({'p/Foo.class':classfile()}, {'source/Foo.java':b'package p; public class Foo {}'})
        self.assertEqual(report['mapped_class_count'],1)
        self.assertEqual(report['mappings'][0]['mapping_method'],'classfile-SourceFile-attribute')
    def test_wrong_package_is_not_coverage(self):
        report=sc.coverage({'p/Foo.class':classfile()}, {'source/Foo.java':b'package other; public class Foo {}'})
        self.assertEqual(report['mapped_class_count'],0)
    def test_stripped_class_has_labeled_declaration_inference(self):
        report=sc.coverage({'p/Foo.class':classfile(source=None)}, {'Foo.java':b'package p; public class Foo {}'})
        self.assertEqual(report['mapped_class_count'],1)
        self.assertIn('inferred',report['mappings'][0]['mapping_method'])
    def test_secondary_class_maps_to_actual_declaring_source(self):
        report=sc.coverage({'p/Helper.class':classfile('p/Helper',None)}, {'Foo.java':b'package p; public class Foo {} class Helper {}'})
        self.assertEqual(report['mapped_class_count'],1)
    def test_comment_does_not_forge_type_or_package(self):
        report=sc.coverage({'p/Foo.class':classfile(source=None)}, {'Bar.java':b'/* package p; class Foo {} */ package other; class Bar {}'})
        self.assertEqual(report['mapped_class_count'],0)
    def test_comment_delimiters_inside_strings_do_not_create_classes(self):
        source=b'package p; class Outer { String x="http://foo/*"; } class Helper {}'
        report=sc.coverage({'p/Helper.class':classfile('p/Helper',None)},{'Outer.java':source})
        self.assertEqual(report['mapped_class_count'],1)
    def test_nested_type_is_not_inferred_as_top_level(self):
        report=sc.coverage({'p/Helper.class':classfile('p/Helper',None)},{'Outer.java':b'package p; class Outer { class Helper {} }'})
        self.assertEqual(report['mapped_class_count'],0)
    def test_wrong_internal_class_path_rejected(self):
        with self.assertRaises(sc.ClosureError):sc.coverage({'other/Foo.class':classfile()}, {})
    def test_zip_traversal_rejected(self):
        with self.assertRaises(sc.ClosureError):sc.archive_members(zipbytes([('../x.java',b'x')]))
    def test_duplicate_zip_path_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');data=zipbytes([('x.java',b'x'),('x.java',b'y')])
        with self.assertRaises(sc.ClosureError):sc.archive_members(data)
    def test_zip_symlink_rejected(self):
        entry=zipfile.ZipInfo('x');entry.external_attr=0o120777<<16
        with self.assertRaises(sc.ClosureError):sc.archive_members(zipbytes([(entry,b'target')]))
    def test_tar_links_rejected(self):
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w') as t:
            item=tarfile.TarInfo('x');item.type=tarfile.SYMTYPE;item.linkname='outside';t.addfile(item)
        with self.assertRaises(sc.ClosureError):sc.archive_members(out.getvalue())
    def test_non_archive_rejected(self):
        with self.assertRaises(sc.ClosureError):sc.archive_members(b'<html>not found</html>')
    def test_input_digest_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'x').write_bytes(b'original')
            ref={'path':'x','sha256':sc.digest(b'changed'),'size':8}
            with self.assertRaises(sc.ClosureError):sc.checked_blob(root,ref)
    def test_symlink_blob_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'target').write_bytes(b'x');(root/'x').symlink_to(root/'target')
            with self.assertRaises(InventoryError):sc.checked_blob(root,{'path':'x','sha256':sc.digest(b'x'),'size':1})
    def test_restore_checks_hash_before_retaining(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);h=sc.digest(b'expected');ref={'path':'blobs/sha256/'+h,'sha256':h,'size':8,'url':'https://example.invalid/source'}
            with self.assertRaises(sc.ClosureError):sc.restore_sources({'artifacts':{'gav':{'sources':[ref]}}},root,lambda _:b'wrong')
            self.assertFalse((root/ref['path']).exists())
    def test_restore_preserves_existing_input_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=b'expected';h=sc.digest(data);ref={'path':'blobs/sha256/'+h,'sha256':h,'size':len(data),'url':'https://example.invalid/source'}
            manifest={'artifacts':{'gav':{'sources':[ref]}}}
            self.assertTrue(sc.restore_sources(manifest,root,lambda _:data)[0]['restored'])
            def fail(_):raise AssertionError('unexpected network request')
            self.assertFalse(sc.restore_sources(manifest,root,fail)[0]['restored'])
            (root/ref['path']).write_bytes(b'changed')
            with self.assertRaises(sc.ClosureError):sc.restore_sources(manifest,root,fail)
            self.assertEqual((root/ref['path']).read_bytes(),b'changed')
    def test_manifest_requires_all_exact_gaps(self):
        with self.assertRaises(sc.ClosureError):sc.build_report({'gaps':[{'gav':'g:a:1'}]},{'artifacts':{}},Path('/x'),Path('/y'))

class FullAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.frozen=self.root/'frozen';self.extra=self.root/'extra';self.extra.mkdir()
    def fixture(self,members):
        data=zipbytes(members);sha=sc.digest(data);blob=self.frozen/'blobs/sha256'/sha;blob.parent.mkdir(parents=True,exist_ok=True);blob.write_bytes(data)
        pom=b'<project><groupId>g</groupId><artifactId>a</artifactId><version>1</version></project>'
        h=sc.digest(pom);(blob.parent/h).write_bytes(pom)
        record=self.frozen/'records/central/g/a/1/a-1.pom.json';record.parent.mkdir(parents=True,exist_ok=True)
        record.write_text(json.dumps({'repository':'central','maven_path':'g/a/1/a-1.pom','sha256':h,'size':len(pom)}))
        return {'gav':'g:a:1','binary_sha256':sha,'binary_path':'g/a/1/a-1.jar','repository':'central','direct_effective_declarations':[], 'direct_effective_plugin_matches':[], 'retained_pom_examples':[], 'resolved_plugin_log_examples':[]}
    def test_embedded_source_not_missing_classifier(self):
        gap=self.fixture([('p/Foo.class',classfile()),('p/Foo.java',b'package p; class Foo {}')])
        report=sc.summarize(gap,self.frozen,self.extra,{})
        self.assertEqual(report['disposition'],'embedded-source-coverage')
        self.assertFalse(report['source_binary_correspondence_established'])
    def test_empty_maven_metadata_counts_separately(self):
        gap=self.fixture([('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0')])
        report=sc.summarize(gap,self.frozen,self.extra,{})
        self.assertEqual(report['disposition'],'metadata-only-no-java-classes')
    def test_nested_jar_under_metadata_not_empty(self):
        gap=self.fixture([('META-INF/maven/g/a/hidden.jar',b'executable')])
        with self.assertRaises(sc.ClosureError):sc.summarize(gap,self.frozen,self.extra,{})
    def test_arbitrary_resource_not_empty(self):
        gap=self.fixture([('native.so',b'ELF')])
        with self.assertRaises(sc.ClosureError):sc.summarize(gap,self.frozen,self.extra,{})
    def test_unmapped_class_remains_unresolved(self):
        gap=self.fixture([('p/Foo.class',classfile())]);report=sc.summarize(gap,self.frozen,self.extra,{})
        self.assertEqual(report['disposition'],'unresolved-source')
    def test_generated_rule_without_source_recipe_rejected(self):
        gap=self.fixture([('p/Foo.class',classfile())])
        rule={'source_member':'no-source','source_sha256':'0'*64,'recipe_member':'no-recipe','recipe_sha256':'0'*64,'mechanism':'claimed generator'}
        with self.assertRaises(sc.ClosureError):sc.summarize(gap,self.frozen,self.extra,{'generated_classes':{'p/Foo':rule}})
    def test_observed_classpath_requires_exact_binary_identity(self):
        gap=self.fixture([('p/Foo.class',classfile())])
        with self.assertRaises(sc.ClosureError):sc.summarize(gap,self.frozen,self.extra,{'observed_use':[{'gav':'g:a:1','artifact_sha256':'0'*64}]})
    def test_java_template_is_explicit(self):
        report=sc.coverage({'p/Foo.class':classfile()},{'Foo.java.in':b'package p; class Foo {}'})
        self.assertEqual(report['mappings'][0]['candidates'][0]['source_kind'],'generation-template')
    def test_posix_colon_member_is_inert(self):
        self.assertEqual(sc.archive_members(zipbytes([('docs/prof-stack:lines=20.log',b'data')]))['docs/prof-stack:lines=20.log'],b'data')
    def test_windows_drive_archive_path_rejected(self):
        with self.assertRaises(sc.ClosureError):sc.archive_members(zipbytes([('C:/data.java',b'data')]))

if __name__=='__main__':unittest.main()
