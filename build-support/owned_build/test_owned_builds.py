import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from common import export_owned,git
from fixture import prepare,drift,floating_resolver
from pair_native import diagnose,require_matching_inputs
from native import require_unchanged_source
from frontend import require_only_generated_changes
from compare_frontend import content_difference,logical_path


class OwnedBuilds(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def repository(self):
        repo=self.root/'repo';subprocess.run(['git','init','-q',str(repo)],check=True)
        (repo/'original').write_text('owned source\n')
        (repo/'.gitattributes').write_text('original export-ignore\n')
        git(repo,'add','.');git(repo,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','Owned source')
        commit=git(repo,'rev-parse','HEAD').decode().strip();tree=git(repo,'rev-parse','HEAD^{tree}').decode().strip()
        return repo,{'commit':commit,'tree':tree,'repository_id':1}

    def test_exact_blob_export_retains_export_ignored_source(self):
        repo,selection=self.repository();export_owned(repo,selection,self.root/'source')
        self.assertEqual((self.root/'source/original').read_text(),'owned source\n')

    def test_wrong_tree_rejected_before_source_write(self):
        repo,selection=self.repository();selection['tree']='0'*40
        with self.assertRaisesRegex(ValueError,'tree identity'):export_owned(repo,selection,self.root/'source')
        self.assertFalse((self.root/'source').exists())

    def test_unexpected_gitlink_rejected_and_exact_gitlink_recorded(self):
        repo,selection=self.repository();child=selection['commit']
        git(repo,'update-index','--add','--cacheinfo','160000,'+child+',module')
        git(repo,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','Selected module')
        selection.update(commit=git(repo,'rev-parse','HEAD').decode().strip(),tree=git(repo,'rev-parse','HEAD^{tree}').decode().strip())
        with self.assertRaisesRegex(ValueError,'Unsupported'):export_owned(repo,selection,self.root/'source')
        selection['gitlinks']={'module':child};r=export_owned(repo,selection,self.root/'approved')
        self.assertEqual(r['gitlinks'],selection['gitlinks'])

    def test_synthetic_donor_positive_control_changes(self):
        path=self.root/'fixture';prepare(path);before=floating_resolver(path);drift(path)
        self.assertNotEqual(before['payload_sha256'],floating_resolver(path)['payload_sha256'])

    def test_original_native_source_mutation_is_rejected(self):
        require_unchanged_source({'postgresql':{},'postgis':{}})
        with self.assertRaisesRegex(ValueError,'modified selected original source'):
            require_unchanged_source({'postgresql':{'owned.c':{'before':'a','after':'b'}},'postgis':{}})

    def test_changed_native_support_manifest_is_rejected(self):
        first={key:'a'*64 for key in ('source_inputs_sha256','support_inputs_sha256',
                                     'support_manifest_sha256','tooling_manifest_sha256')}
        self.assertEqual(require_matching_inputs([first,first])['support_manifest_sha256'],['a'*64]*2)
        second={**first,'support_manifest_sha256':'b'*64}
        with self.assertRaisesRegex(ValueError,'input identities changed'):
            require_matching_inputs([first,second])

    def test_frontend_mutation_boundary_accepts_only_declared_generated_outputs(self):
        require_only_generated_changes({'mapstore':{},'mapstore-client':{
            'geonode_mapstore_client/client/version.txt':{},
            'geonode_mapstore_client/static/mapstore/dist/js/entry.js':{}}})
        for component,path in (
            ('mapstore','web/client/security.js'),
            ('mapstore-client','geonode_mapstore_client/client/js/security.js'),
            ('mapstore-client','geonode_mapstore_client/static/mapstore/auth.json'),
            ('mapstore-client','geonode_mapstore_client/static/mapstore/dist-evil/js/entry.js')):
            with self.subTest(component=component,path=path):
                with self.assertRaisesRegex(ValueError,'outside generated outputs'):
                    require_only_generated_changes({component:{path:{}}})

    def files(self,a,b):
        first,second=self.root/'build-1',self.root/'build-2';first.mkdir();second.mkdir()
        x,y=first/'file',second/'file';x.write_bytes(a);y.write_bytes(b)
        return x,y,first,second

    @staticmethod
    def archive(stamp,payload,uid=1000):
        header=(f'{"sample.o/":<16}{stamp:<12}{uid:<6}{1000:<6}{"100644":<8}{len(payload):<10}`\n').encode()
        return b'!<arch>\n'+header+payload+(b'\n' if len(payload)%2 else b'')

    def test_static_archive_dates_attributed_without_hiding_payload_change(self):
        x,y,a,b=self.files(self.archive(100,b'same machine code'),self.archive(200,b'same machine code'))
        self.assertEqual(diagnose(x,y,a,b)['kind'],'static-archive-dates-and-recorded-job-paths')
        y.write_bytes(self.archive(200,b'evil machine code'))
        self.assertEqual(diagnose(x,y,a,b)['kind'],'unexplained-content')

    def test_archive_non_date_metadata_is_not_ignored(self):
        x,y,a,b=self.files(self.archive(100,b'code'),self.archive(200,b'code',uid=2000))
        self.assertEqual(diagnose(x,y,a,b)['kind'],'unexplained-content')

    def test_job_paths_attributed_but_changed_logic_rejected(self):
        first,second=self.root/'build-1',self.root/'build-2'
        x,y,a,b=self.files(str(first).encode()+b' same',str(second).encode()+b' same')
        self.assertEqual(diagnose(x,y,a,b)['kind'],'recorded-job-paths-only')
        y.write_bytes(str(second).encode()+b' evil')
        self.assertEqual(diagnose(x,y,a,b)['kind'],'unexplained-content')

    def test_ui_generated_hash_and_job_path_do_not_hide_logic_change(self):
        a,b=self.root/'first',self.root/'second';ha,hb='1'*16,'2'*16
        x=(str(a)+' '+ha+' safe();').encode();y=(str(b)+' '+hb+' safe();').encode()
        self.assertEqual(content_difference(x,y,a,b,ha,hb)['kind'],'recorded-build-path-or-webpack-hash-references')
        self.assertEqual(content_difference(x,y.replace(b'safe();',b'evil();'),a,b,ha,hb)['kind'],'unexplained-content')
        self.assertEqual(logical_path('dist/js/1.'+ha+'.chunk.js',ha),'dist/js/1.<WEBPACK-HASH>.chunk.js')
        self.assertEqual(logical_path('unrelated/'+ha+'.png',ha),'unrelated/'+ha+'.png')

    def test_ui_compare_command_fails_on_changed_logic_and_retains_diagnosis(self):
        pair=self.root/'pair';pair.mkdir()
        fixture=pair/'synthetic-donor';fixture.mkdir();(fixture/'drift.json').write_text('{}')
        for number in (1,2):
            build=pair/f'build-{number}';build.mkdir()
            result={'result_exit_code':0,**{key:'a'*64 for key in (
                'source_inputs_sha256','dependency_manifest_sha256','tooling_manifest_sha256')}}
            (build/'result.json').write_text(json.dumps(result))
            token=str(number)*16;relative=f'dist/js/1.{token}.chunk.js'
            output=build/'client/geonode_mapstore_client/static/mapstore'/relative
            output.parent.mkdir(parents=True);output.write_text('safe();' if number==1 else 'evil();')
            (build/'output-manifest.json').write_text(json.dumps([{
                'path':relative,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size}]))
            config=build/'client/geonode_mapstore_client/client/MapStore2/build/buildConfig.js'
            config.parent.mkdir(parents=True);config.write_text('chunkFilename: "[name].[hash].chunk.js"')
        report=self.root/'comparison.json'
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('compare_frontend.py')),
                               '--pair',str(pair),'--output',str(report)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        diagnostic=json.loads(report.read_text())
        self.assertEqual(diagnostic['result_exit_code'],1)
        self.assertEqual(diagnostic['unexplained'],1)
        self.assertIn('Unexplained UI output content',result.stderr)


if __name__=='__main__':unittest.main()
