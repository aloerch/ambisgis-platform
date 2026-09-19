"""Resolution safety contracts: no lifecycle goals or inherited credentials."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import hashlib
import subprocess
import resolution
import replay_model


class ResolutionTests(unittest.TestCase):
    def test_only_pinned_model_or_dependency_goals(self):
        for stage in ('deploy', 'install', 'package', 'validate', 'verify', 'test'):
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                resolution.command(Path('/task'), Path('/java'), Path('/maven'),
                                   stage, Path('/task/m2'), Path('/settings'), 'run')

    def test_isolated_settings_reactor_and_complete_alignment(self):
        cmd, env = resolution.command(Path('/task'), Path('/java'), Path('/maven'),
                                      'effective', Path('/task/m2-fresh'), Path('/task/settings'), 'run')
        self.assertEqual(cmd[cmd.index('-gs') + 1], '/task/empty-global-settings.xml')
        self.assertIn('-Dmaven.repo.local=/task/m2-fresh', cmd)
        self.assertIn('-Dgt.version=34.5', cmd)
        self.assertIn('-Dgt-version=34.5', cmd)
        self.assertIn('-Dmf.version=2.4.1', cmd)
        self.assertEqual(cmd[cmd.index('-pl') + 1], resolution.TARGETS)
        self.assertIn('-am', cmd)
        self.assertIn(resolution.HELP, cmd)
        self.assertEqual(env['MAVEN_SKIP_RC'], 'true')
        self.assertEqual(env['MAVEN_BASEDIR'], '/task/source')
        self.assertNotIn('HOME', env)
        self.assertNotIn('GH_TOKEN', env)
        self.assertNotIn('JAVA_TOOL_OPTIONS', env)
        self.assertIn('-Duser.home=/task/user', env['MAVEN_OPTS'])

    def test_effective_graph_reads_active_dependencies_not_inactive_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'effective.xml'
            path.write_text('''<projects xmlns="http://maven.apache.org/POM/4.0.0"><project>
            <groupId>sample</groupId><artifactId>app</artifactId><version>1</version>
            <dependencies><dependency><groupId>safe</groupId><artifactId>library</artifactId>
            <version>2</version><scope>test</scope></dependency></dependencies>
            <profiles><profile><dependencies><dependency><groupId>unused</groupId>
            <artifactId>snapshot</artifactId><version>1-SNAPSHOT</version></dependency>
            </dependencies></profile></profiles></project></projects>''')
            report = resolution.effective_report(path)
            self.assertEqual(report['project_count'], 1)
            self.assertEqual(report['projects'][0]['gav'], 'sample:app:1')
            self.assertEqual(len(report['projects'][0]['dependencies']), 1)
            self.assertEqual(report['projects'][0]['dependencies'][0]['scope'], 'test')
            self.assertFalse(report['transitive_closure_complete'])

    def test_pom_inventory_detects_changes_and_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'pom.xml'
            path.write_text('<project/>')
            initial = resolution.pom_inventory(root)
            path.write_text('<project>changed</project>')
            self.assertNotEqual(initial, resolution.pom_inventory(root))
            path.write_text('<project/>')
            (root / 'module').mkdir()
            (root / 'module/pom.xml').write_text('<project/>')
            self.assertNotEqual(initial, resolution.pom_inventory(root))

    def test_new_maven_configuration_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'pom.xml').write_text('<project/>')
            initial = resolution.maven_inventory(root)
            (root / '.mvn').mkdir()
            (root / '.mvn/extensions.xml').write_text('<extensions/>')
            self.assertNotEqual(initial, resolution.maven_inventory(root))

    def test_incomplete_effective_output_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'effective.xml'
            path.write_text('<project xmlns="http://maven.apache.org/POM/4.0.0">'
                            '<groupId>sample</groupId><artifactId>wrong</artifactId>'
                            '<version>1</version></project>')
            with self.assertRaisesRegex(ValueError, 'omitted required target'):
                resolution.validate_effective(path)

    def test_launch_failure_leaves_failure_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source').mkdir()
            (root / 'logs').mkdir()
            (root / 'source/pom.xml').write_text('<project/>')
            (root / 'empty-global-settings.xml').write_text('<settings/>\n')
            resolution.write_json(root / 'preparation.json',
                                  {'maven_files': resolution.maven_inventory(root / 'source')})
            java = root / 'jdk-17.0.20.1+1'
            maven = root / 'apache-maven-3.9.16'
            with patch('toolchain.verify_extracted', return_value={'verified': True}), \
                 patch('subprocess.Popen', side_effect=FileNotFoundError('missing tool')):
                result = resolution.run(root, root / 'custody', java, maven,
                                        root / 'tools', 'effective', True, 'failed')
            self.assertEqual(result['result_exit_code'], 1)
            self.assertIsNone(result['exit_code'])
            self.assertEqual(result['error']['type'], 'FileNotFoundError')
            self.assertTrue((root / 'logs/failed.json').exists())
            self.assertTrue((root / 'logs/failed-started.json').exists())

    def test_replay_cannot_report_success_with_malformed_effective_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source').mkdir()
            (root / 'logs').mkdir()
            (root / 'source/pom.xml').write_text('<project/>')
            (root / 'empty-global-settings.xml').write_text('<settings/>\n')
            resolution.write_json(root / 'preparation.json',
                                  {'maven_files': resolution.maven_inventory(root / 'source')})
            def malformed(cmd, *_args):
                target = next(arg.split('=', 1)[1] for arg in cmd if arg.startswith('-Doutput='))
                Path(target).write_text('<invalid')
                return 0
            with patch('toolchain.verify_extracted', return_value={'verified': True}), \
                 patch('replay_model.verify_custody', return_value={
                     'verification': {'valid': True}, 'artifacts': []}), \
                 patch('replay_model.execute', side_effect=malformed):
                result = replay_model.replay(root, root / 'custody', root / 'tool-custody',
                                             root / 'tools', root / 'replay')
            self.assertEqual(result['exit_code'], 0)
            self.assertEqual(result['result_exit_code'], 1)
            self.assertEqual(result['error']['type'], 'ParseError')
            self.assertEqual(json.loads((root / 'replay/result.json').read_text())['result_exit_code'], 1)


class DependencyReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ambisgis-dependency-replay-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'source').mkdir()
        (self.root / 'logs').mkdir()
        (self.root / 'source/pom.xml').write_text('<project/>')
        (self.root / 'empty-global-settings.xml').write_text('<settings/>\n')
        resolution.write_json(self.root / 'preparation.json',
                              {'maven_files': resolution.maven_inventory(self.root / 'source')})
        self.custody = self.root / 'custody'
        self.path = 'org/example/fixture/1/fixture-1.pom'
        self.data = b'<project>retained model fixture</project>'
        self.digest = hashlib.sha256(self.data).hexdigest()
        blob = self.custody / 'blobs/sha256' / self.digest
        blob.parent.mkdir(parents=True)
        blob.write_bytes(self.data)
        selection = self.custody / 'selections' / (self.path + '.json')
        selection.parent.mkdir(parents=True)
        resolution.write_json(selection, {'repository': 'central', 'maven_path': self.path})
        self.inventory = {'verification': {'valid': True}, 'artifacts': [{
            'repository': 'central', 'maven_path': self.path,
            'blob_path': 'blobs/sha256/' + self.digest, 'sha256': self.digest}]}
        self.output = self.root / 'replay'

    def invoke(self, executor, stage='dependencies'):
        with patch('toolchain.verify_extracted', return_value={'verified': True}), \
             patch('replay_model.verify_custody', return_value=self.inventory), \
             patch('replay_model.execute', side_effect=executor):
            return replay_model.replay(self.root, self.custody, self.root / 'tool-custody',
                                       self.root / 'tools', self.output, stage=stage)

    def test_dependency_replay_uses_fresh_repository_without_model_parsing(self):
        def successful(cmd, cwd, env, output, timeout):
            self.assertIn(resolution.DEPENDENCIES, cmd)
            self.assertNotIn(resolution.HELP, cmd)
            self.assertFalse(any(arg.startswith('-Doutput=') for arg in cmd))
            self.assertEqual(cmd[cmd.index('-pl') + 1], resolution.TARGETS)
            self.assertIn('-am', cmd)
            self.assertIn('-DexcludeReactor=true', cmd)
            self.assertEqual(timeout, 3600)
            self.assertEqual(list((self.output / 'fresh-m2').iterdir()), [])
            self.assertEqual((self.output / 'retained-repository' / self.path).read_bytes(), self.data)
            self.assertIn((self.output / 'retained-repository').as_uri(),
                          (self.output / 'settings.xml').read_text())
            self.assertIn('offline_exec.py', cmd[1])
            self.assertEqual(env['MAVEN_BASEDIR'], str(self.root / 'source'))
            output.write('fixture dependency goal complete\n')
            return 0
        with patch('replay_model.validate_effective', side_effect=AssertionError('must not parse a model')):
            result = self.invoke(successful)
        self.assertEqual(result['stage'], 'dependencies')
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['result_exit_code'], 0)
        self.assertNotIn('effective_projects', result)
        self.assertFalse(result['transitive_closure_complete'])
        self.assertFalse(result['java_build_run'])
        self.assertFalse((self.output / 'effective-graph.json').exists())
        self.assertEqual(json.loads((self.output / 'result.json').read_text()), result)
        # The same explicit output can never reset the retained mirror or fresh repository.
        with self.assertRaises(FileExistsError):
            self.invoke(lambda *_: self.fail('reused replay executed'))
        self.assertEqual(json.loads((self.output / 'result.json').read_text()), result)

    def test_failed_dependency_goal_retains_its_actual_exit_status(self):
        result = self.invoke(lambda *_: 7)
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(result['result_exit_code'], 7)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('effective_projects', result)

    def test_dependency_timeout_retains_a_failure_receipt(self):
        def timeout(*args):
            raise subprocess.TimeoutExpired('fixture pinned goal', 3600)
        result = self.invoke(timeout)
        self.assertIsNone(result['exit_code'])
        self.assertEqual(result['result_exit_code'], 1)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error']['type'], 'TimeoutExpired')
        self.assertEqual(json.loads((self.output / 'result.json').read_text()), result)

    def test_lifecycle_stage_is_rejected_before_verification_or_output_creation(self):
        with patch('toolchain.verify_extracted') as verifier:
            with self.assertRaisesRegex(ValueError, 'only effective or dependencies'):
                replay_model.replay(self.root, self.custody, self.root / 'tool-custody',
                                    self.root / 'tools', self.output, stage='package')
        verifier.assert_not_called()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
