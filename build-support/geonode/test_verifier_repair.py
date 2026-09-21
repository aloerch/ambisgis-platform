"""Offline source-transform guards; these are not native verifier acceptance."""
import ast
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import verifier_repair as repair


class RepairGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(os.environ.get('AMBISGIS_GEONODE_SOURCE_REPO',
                                   '/home/revelberry/Projects/AmbisGIS/ambisgis-geonode'))
        if not (repo / '.git').exists():
            raise unittest.SkipTest('retained owned GeoNode source repository unavailable')
        cls.originals = {}
        for relative in repair.BASELINE:
            data = subprocess.check_output(['git', '-C', str(repo), 'show', repair.SOURCE_COMMIT + ':' + relative])
            if repair.sha(data) != repair.BASELINE[relative]:
                raise AssertionError('owned source fixture differs from declared baseline guard')
            cls.originals[relative] = data

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'source'
        self.root.mkdir()
        for name, data in self.originals.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file() and not path.is_symlink()}

    def test_exact_source_transforms_to_declared_full_allowlist(self):
        result = repair.apply(self.root)
        self.assertTrue(result['applied'])
        self.assertFalse(result['default'])
        self.assertFalse(result['already_applied'])
        self.assertEqual({name: repair.sha(data) for name, data in self.snapshot().items()}, repair.expected_files())
        self.assertEqual(len(result['files']), 5)
        for name, data in self.snapshot().items():
            compile(data, name, 'exec')

    def test_repeat_is_idempotent_and_preserves_bytes(self):
        repair.apply(self.root)
        before = self.snapshot()
        repeated = repair.apply(self.root)
        self.assertTrue(repeated['already_applied'])
        self.assertEqual(before, self.snapshot())

    def test_guard_failure_happens_before_any_source_write(self):
        path = self.root / 'geonode/security/middleware.py'
        path.write_bytes(path.read_bytes() + b'\n# independently changed\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'baseline mismatch'):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_unknown_existing_helper_is_not_overwritten(self):
        (self.root / repair.HELPER_PATH).write_text('# unrelated existing module\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'collision'):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_partial_repair_is_not_assumed_authorized(self):
        name = 'geonode/api/views.py'
        (self.root / name).write_bytes(repair.transform_existing(name, self.originals[name]))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'baseline mismatch'):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_repaired_helper_drift_is_not_silently_fixed(self):
        repair.apply(self.root)
        path = self.root / repair.HELPER_PATH
        path.write_text(path.read_text() + '# changed\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_target_symlink_is_rejected_without_following_it(self):
        outside = Path(self.temporary.name) / 'outside.py'
        outside.write_text('outside witness')
        (self.root / repair.HELPER_PATH).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            repair.apply(self.root)
        self.assertEqual(outside.read_text(), 'outside witness')

    def test_parent_symlink_is_rejected(self):
        directory = self.root / 'geonode/api'
        moved = self.root / 'geonode/api-original'
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            repair.apply(self.root)

    def test_source_directory_symlink_is_rejected(self):
        alias = Path(self.temporary.name) / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            repair.apply(alias)

    def test_individual_transform_rejects_unrecognized_revision(self):
        for name, original in self.originals.items():
            with self.subTest(path=name), self.assertRaises(ValueError):
                repair.transform_existing(name, original + b'\n')

    def test_default_false_and_legacy_branch_remain_in_source(self):
        repair.apply(self.root)
        settings = (self.root / 'geonode/settings.py').read_text()
        views = (self.root / 'geonode/api/views.py').read_text()
        self.assertEqual(settings.count('OAUTH2_BACKEND_TOKENINFO_STRICT = False'), 1)
        self.assertIn('return strict_verify_token(request)', views)
        self.assertIn('"access_token": access_token', views)
        self.assertIn('token = get_token_object_from_session(request.session)', views)

    def test_middleware_guard_is_limited_to_two_native_methods(self):
        repair.apply(self.root)
        tree = ast.parse((self.root / 'geonode/security/middleware.py').read_text())
        guarded = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and any(isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Name) and call.func.id == 'is_strict_backend_request'
                        for call in ast.walk(method)):
                        guarded.append((node.name, method.name))
        self.assertEqual(guarded, [('AuthenticateBasicAuthOrApiKeyMiddleware', 'process_request'),
                                   ('SessionControlMiddleware', 'process_request')])


if __name__ == '__main__':
    unittest.main()
