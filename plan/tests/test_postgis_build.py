"""Tests for evidence-critical build-tooling failures, not GIS acceptance."""
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

RECIPE = Path(__file__).resolve().parents[2] / 'build-support/postgis/build.py'
spec = importlib.util.spec_from_file_location('postgis_build', RECIPE)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BuildRecipeTests(unittest.TestCase):
    def test_cunit_zero_exit_does_not_hide_assertion_failure(self):
        for output in ('', 'CUnit Internal Test Results\nTotal Number of Assertions: 0\nFailures: 0',
                       'CUnit Internal Test Results\nTotal Number of Assertions: 1200\nFailures: 1'):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                build.assert_cunit_internal_results(output)
        build.assert_cunit_internal_results(
            'intentional test diagnostic\nCUnit Internal Test Results\n'
            'Total Number of Assertions: 1200\nFailures: 0')

    def test_archive_integrity_checked_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'input.tar'
            archive.write_bytes(b'corrupt input')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                build.extract_verified(archive, '0'*64, root/'source')
            self.assertFalse((root/'source').exists())

    def test_archive_cannot_write_outside_source_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'input.tar'
            with tarfile.open(archive, 'w') as output:
                member = tarfile.TarInfo('../escaped')
                member.size = 3
                output.addfile(member, io.BytesIO(b'bad'))
            with self.assertRaises(tarfile.FilterError):
                build.extract_verified(archive, build.digest(archive), root/'source')
            self.assertFalse((root/'escaped').exists())

    def test_build_environment_excludes_host_database_and_fetch_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, {'PGHOST': 'user-service', 'PGPORT': '5432',
                                         'CFLAGS': '-I/unretained', 'GH_TOKEN': 'not-a-token'}):
                env = build.build_environment(root/'prefix', root)
            for key in ('PGHOST', 'PGPORT', 'GH_TOKEN'):
                self.assertNotIn(key, env)
            self.assertNotIn('/unretained', env['CFLAGS'])
            self.assertEqual(env['PROJ_NETWORK'], 'OFF')
            self.assertTrue(env['PATH'].startswith(str(root/'prefix/bin')))

    def test_changed_retained_input_rejected_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'input.tar'
            with tarfile.open(archive, 'w') as output:
                member = tarfile.TarInfo('source/file')
                member.size = 2
                output.addfile(member, io.BytesIO(b'ok'))
            manifest = {'inputs': [{'name': 'test', 'artifact': 'input.tar',
                                    'sha256': build.digest(archive)}]}
            builder = build.Builder(manifest, root, root/'run', 1)
            self.addCleanup(builder.close)
            builder.source('test')
            archive.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                builder.source('test')

    def test_failed_command_is_preserved_in_receipt(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = build.Builder({'inputs': []}, root, root/'run', 1)
            self.addCleanup(builder.close)
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                builder.command(['/bin/sh', '-c', 'exit 17'], root)
            receipt = json.loads(builder.receipts.read_text())
            self.assertEqual(receipt['exit_status'], 17)
            self.assertEqual(receipt['log_sha256'], build.digest(Path(receipt['log'])))

    def test_failed_start_records_error_and_reserves_log_number(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = build.Builder({'inputs': []}, root, root/'run', 1)
            self.addCleanup(builder.close)
            with self.assertRaises(FileNotFoundError):
                builder.command([str(root/'missing-program')], root)
            receipt = json.loads(builder.receipts.read_text())
            self.assertIsNone(receipt['exit_status'])
            self.assertIn('error', receipt)
            builder.close()
            resumed = build.Builder({'inputs': []}, root, root/'run', 1)
            self.addCleanup(resumed.close)
            self.assertEqual(resumed.sequence, 1)
            self.assertTrue((resumed.logs/'command-0001.json').exists())

    def test_recipe_identity_fixed_for_entire_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = build.Builder({'inputs': []}, root, root/'run', 1)
            self.addCleanup(builder.close)
            before = builder.recipe_sha256
            with patch.object(build, '__file__', str(root/'different-script')):
                builder.command(['/bin/true'], root)
            import json
            receipt = json.loads(builder.receipts.read_text())
            self.assertEqual(receipt['recipe_sha256'], before)
            self.assertEqual(build.digest(builder.logs/f'recipe-{before}.py'), before)

    def test_generator_zero_exit_requires_all_nonempty_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'unit.pb.h'
            with self.assertRaisesRegex(RuntimeError, 'omitted'):
                build.require_generated_files([output])
            output.touch()
            with self.assertRaisesRegex(RuntimeError, 'omitted'):
                build.require_generated_files([output])
            output.write_text('generated header')
            build.require_generated_files([output])

    def test_overlapping_build_cannot_mutate_same_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = build.Builder({'inputs': []}, root, root/'run', 1)
            self.addCleanup(builder.close)
            with self.assertRaises(BlockingIOError):
                build.Builder({'inputs': []}, root, root/'run', 1)


if __name__ == '__main__':
    unittest.main()
