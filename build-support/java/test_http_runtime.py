"""Fail-closed orchestration tests, separate from real HTTP/native acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import compatibility


class HttpRuntimeTests(unittest.TestCase):
    def run_fixture(self, root, build_exit=0, runtime_exit=0, cleanup_error=False, proof_error=False, tamper_snapshot=False, receipt_runner_hash=None):
        calls=[]
        output=root/'result'
        def prepare(_custody,path):
            (path/'source').mkdir(parents=True)
            (path/'source/pom.xml').write_text('<project/>')
            (path/'user').mkdir()
            return path
        def execute(cmd,source,env,stream,timeout):
            build='network-denial-build.json' in ' '.join(cmd)
            calls.append(('build' if build else 'runtime',cmd,dict(env)))
            if build:
                (output/'network-denial-build.json').write_text(json.dumps({'status':'completed','command_exit_code':build_exit,
                    'probes':[{'family':f,'operation':'socket(SOCK_STREAM)','errno':1,'passed':True} for f in ('AF_INET','AF_INET6')]}))
                return build_exit
            reports=source/'geotools/modules/library/xml/target/surefire-reports'
            reports.mkdir(parents=True)
            (reports/'TEST-actual.xml').write_text('<testsuite name="org.geotools.xml.SchemaCacheTest" tests="5" failures="0" errors="0" skipped="0">' + ''.join('<testcase classname="org.geotools.xml.SchemaCacheTest" name="case%d"/>' % i for i in range(5)) + '</testsuite>')
            if tamper_snapshot:
                snapshot=output/'tooling/java/loopback_exec.py'
                snapshot.write_bytes(snapshot.read_bytes() + b'\n# changed after execution\n')
            return runtime_exit
        with patch('compatibility.prepare',side_effect=prepare), \
             patch('compatibility.materialize',return_value=[]), \
             patch('compatibility.toolchain.verify_extracted',return_value={'verified':True}), \
             patch('compatibility.execute',side_effect=execute), \
             patch('compatibility.startup_test_agent',return_value={'java_option':'-javaagent:/retained/original-agent.jar'}), \
             patch('http_fixtures.prepare',return_value={'java_properties':['-Djdk.net.hosts.file=/retained/hosts']}), \
             patch('http_fixtures.finalize',side_effect=RuntimeError('owned fixture not stopped') if cleanup_error else None,return_value={'stopped':True}), \
             patch('loopback_exec.verify_receipt',create=True,side_effect=ValueError('child denial proof missing') if proof_error else None,return_value={'verified':True, 'runner_sha256':receipt_runner_hash if receipt_runner_hash is not None else compatibility.sha(Path(compatibility.__file__).with_name('loopback_exec.py'))}):
            result=compatibility.probe(root/'audit',root/'custody',root/'tc',root/'tools',output,'xml','package',tests='target',runtime_http=True)
        self.assertEqual(json.loads((output/'result.json').read_text()),result)
        return result,calls

    def test_build_must_succeed_before_http_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,calls=self.run_fixture(Path(tmp),build_exit=1)
        self.assertEqual([c[0] for c in calls],['build'])
        self.assertNotEqual(result['result_exit_code'],0)
        self.assertIsNone(result['exit_code'])

    def test_build_denial_and_offline_runtime_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,calls=self.run_fixture(Path(tmp))
        self.assertEqual([c[0] for c in calls],['build','runtime'])
        self.assertTrue(calls[0][1][1].endswith('/result/tooling/postgis/offline_exec.py'))
        self.assertTrue(calls[1][1][1].endswith('/result/tooling/java/loopback_exec.py'))
        self.assertTrue(result['retained_tooling_unchanged'])
        self.assertIn('-DskipTests=true',calls[0][1])
        self.assertNotIn('JAVA_TOOL_OPTIONS',calls[0][2])
        self.assertIn('--offline',calls[1][1])
        self.assertNotIn('-DskipTests=true',calls[1][1])
        self.assertEqual(result['result_exit_code'],0)
        self.assertTrue(result['build_network_denial_verified'])

    def test_runtime_failure_is_not_erased_by_successful_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,_=self.run_fixture(Path(tmp),runtime_exit=1)
        self.assertEqual(result['build_exit_code'],0)
        self.assertEqual(result['result_exit_code'],1)

    def test_cleanup_failure_overrides_maven_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,_=self.run_fixture(Path(tmp),cleanup_error=True)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['result_exit_code'],1)
        self.assertIn('not stopped',result['finalization_error']['message'])

    def test_missing_child_enforcement_proof_overrides_maven_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,_=self.run_fixture(Path(tmp),proof_error=True)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['result_exit_code'],1)
        self.assertIn('proof missing',result['finalization_error']['message'])

    def test_retained_tooling_drift_overrides_maven_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,_=self.run_fixture(Path(tmp),tamper_snapshot=True)
        self.assertEqual(result['build_exit_code'],0)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['result_exit_code'],1)
        self.assertEqual(result['status'],'failed')
        self.assertIn('retained executed tooling changed: java/loopback_exec.py',result['finalization_error']['message'])
        self.assertNotIn('retained_tooling_unchanged',result)

    def test_receipt_runner_mismatch_overrides_maven_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,_=self.run_fixture(Path(tmp),receipt_runner_hash='0'*64)
        self.assertEqual(result['build_exit_code'],0)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['result_exit_code'],1)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['retained_tooling_unchanged'])
        self.assertIn('loopback receipt runner differs from retained tooling',result['finalization_error']['message'])

    def test_principal_repair_requires_redaction(self):
        with self.assertRaisesRegex(ValueError, 'requires the diagnostic'):
            compatibility.probe(Path('/a'),Path('/b'),Path('/c'),Path('/d'),Path('/not-created'),'oauth','test',runtime_http=True,oauth_principal=True)

    def test_http_mode_refuses_unsupported_targets_or_compile_only(self):
        for target,tests,timeout in (('referencing','target',120),('xml','compile-only',120),('oauth','target',10)):
            with self.subTest(target=target,tests=tests),self.assertRaises(ValueError):
                compatibility.probe(Path('/a'),Path('/b'),Path('/c'),Path('/d'),Path('/not-created'),target,'test',timeout=timeout,tests=tests,runtime_http=True)

if __name__=='__main__': unittest.main()
