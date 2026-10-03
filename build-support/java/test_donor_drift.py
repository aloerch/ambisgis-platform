from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

from donor_drift import (PRODUCER_INPUTS, attribute_archive, chronology, describe, drift, floating_resolver,
                         prepare, timestamp_changes, unexplained, zip_entries)


class DonorDriftFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'fixture'

    def test_actual_default_and_api_change_positive_control(self):
        prepare(self.root);before=describe(self.root);old=floating_resolver(self.root)
        drift(self.root);after=describe(self.root);new=floating_resolver(self.root)
        for field in ('ref','commit','tree','api_sha256'):
            self.assertNotEqual(before[field],after[field])
        self.assertNotEqual(old['payload'],new['payload'])

    def test_repeated_drift_refuses_changed_fixture(self):
        prepare(self.root);drift(self.root)
        with self.assertRaisesRegex(ValueError,'changed unexpectedly'):drift(self.root)

    def test_unowned_fixture_never_mutated(self):
        prepare(self.root);(self.root/'JOB_OWNERSHIP.json').write_text('{}')
        before=describe(self.root)
        with self.assertRaisesRegex(ValueError,'job-owned'):drift(self.root)
        self.assertEqual(before,describe(self.root))

    def test_archive_comparison_preserves_content_and_metadata(self):
        paths=[Path(self.tmp.name)/'a.jar',Path(self.tmp.name)/'b.jar']
        for p,date in zip(paths,[(2020,1,1,0,0,0),(2021,1,1,0,0,0)]):
            with zipfile.ZipFile(p,'w') as z:z.writestr(zipfile.ZipInfo('value',date_time=date),b'same bytes')
        a,b=map(zip_entries,paths)
        self.assertEqual(a['value']['sha256'],b['value']['sha256'])
        self.assertNotEqual(a['value']['timestamp'],b['value']['timestamp'])

    def test_timestamp_attribution_rejects_substantive_manifest_change(self):
        a=b'Version: 1\r\nBuild-Timestamp: 02-Oct-2026 00:00\r\n'
        b=b'Version: 1\r\nBuild-Timestamp: 03-Oct-2026 01:01\r\n'
        self.assertEqual(len(timestamp_changes('META-INF/MANIFEST.MF',a,b)),1)
        self.assertIsNone(timestamp_changes('META-INF/MANIFEST.MF',a,b.replace(b'Version: 1',b'Version: 2')))

    def test_nested_changed_bytecode_is_unexplained(self):
        paths=[Path(self.tmp.name)/'a.jar',Path(self.tmp.name)/'b.jar']
        for p,data in zip(paths,[b'old bytecode',b'new bytecode']):
            inner=Path(str(p)+'.inner')
            with zipfile.ZipFile(inner,'w') as z:z.writestr('Example.class',data)
            with zipfile.ZipFile(p,'w') as z:z.writestr('WEB-INF/lib/inner.jar',inner.read_bytes())
        changes=attribute_archive(*paths)
        self.assertEqual(unexplained(changes),1)
        self.assertEqual(changes[0]['changes'][0]['kind'],'unexplained-content')

    def test_fixture_created_after_first_build_is_rejected(self):
        first,second,fixture=[Path(self.tmp.name)/n for n in ('first','second','donor')]
        for p in (first,second,fixture):p.mkdir()
        paths=[fixture/'before.json',first/'started.json',first/'result.json',
               fixture/'drift.json',second/'started.json',second/'result.json']
        for n,p in enumerate(paths):
            p.write_text('{}');os.utime(p,ns=(100+n,100+n))
        self.assertTrue(chronology(first,second,fixture)['ordered'])
        os.utime(paths[0],ns=(103,103))
        with self.assertRaisesRegex(ValueError,'precede first build'):chronology(first,second,fixture)

    def test_compare_command_fails_and_retains_nested_bytecode_diagnostic(self):
        prepare(self.root)
        builds=[]
        for n,data in enumerate((b'old bytecode',b'new bytecode')):
            if n:drift(self.root)
            build=Path(self.tmp.name)/str(n);build.mkdir();builds.append(build)
            (build/'started.json').write_text('{}')
            target=build/'work/source';target.mkdir(parents=True)
            inner=build/'inner.jar'
            with zipfile.ZipFile(inner,'w') as z:z.writestr('Example.class',data)
            war=target/'product.war'
            with zipfile.ZipFile(war,'w') as z:z.writestr('WEB-INF/lib/inner.jar',inner.read_bytes())
            names=['build-support/java/'+p for p in PRODUCER_INPUTS]+['build-support/postgis/offline_exec.py']
            manifest={name:'a'*64 for name in names}
            (build/'tooling-manifest.json').write_text(json.dumps(manifest))
            result={k:'same' for k in ('source_successor','source_inputs_sha256','retained_inputs_sha256','runner_sha256','toolchain','tooling_manifest_sha256')}
            result.update(result_exit_code=0,network={'verified':True},artifacts={'built':[
                {'path':'product.war','sha256':hashlib.sha256(war.read_bytes()).hexdigest()}]})
            (build/'result.json').write_text(json.dumps(result))
        output=Path(self.tmp.name)/'comparison.json'
        done=subprocess.run([sys.executable,str(Path(__file__).with_name('donor_drift.py')),'compare',
            '--fixture',str(self.root),'--first',str(builds[0]),'--second',str(builds[1]),
            '--output',str(output)],capture_output=True,text=True)
        self.assertNotEqual(done.returncode,0)
        self.assertIn('Unexplained product content changes',done.stderr)
        self.assertEqual(json.loads(output.read_text())['unexplained_content_changes'],1)
