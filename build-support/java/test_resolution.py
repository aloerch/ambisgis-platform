"""Resolution safety contracts: no lifecycle goals or inherited credentials."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
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


if __name__ == '__main__':
    unittest.main()
