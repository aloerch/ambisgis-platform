"""Exact-source and middleware-scope guards; native HTTP acceptance is separate."""
import ast
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import roles_repair as repair
import verifier_repair


class RoleRepairGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(os.environ.get('AMBISGIS_GEONODE_SOURCE_REPO',
                                   '/home/revelberry/Projects/AmbisGIS/ambisgis-geonode'))
        if not (repo / '.git').exists():
            raise unittest.SkipTest('retained owned GeoNode source repository unavailable')
        cls.originals = {}
        for relative in verifier_repair.BASELINE:
            data = subprocess.check_output(['git', '-C', str(repo), 'show', repair.SOURCE_COMMIT + ':' + relative])
            cls.originals[relative] = verifier_repair.transform_existing(relative, data)
            if repair.sha(cls.originals[relative]) != repair.BASELINE[relative]:
                raise AssertionError('role repair does not start at exact tokeninfo repaired source')

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

    def test_exact_source_and_every_output_guard(self):
        result = repair.apply(self.root)
        self.assertTrue(result['applied'])
        self.assertFalse(result['default'])
        self.assertFalse(result['already_applied'])
        self.assertEqual({name: repair.sha(data) for name, data in self.snapshot().items()}, repair.expected_files())
        for name, data in self.snapshot().items():
            compile(data, name, 'exec')

    def test_repeat_preserves_bytes(self):
        repair.apply(self.root)
        before = self.snapshot()
        self.assertTrue(repair.apply(self.root)['already_applied'])
        self.assertEqual(self.snapshot(), before)

    def test_drift_guard_before_any_write(self):
        path = self.root / 'geonode/security/middleware.py'
        path.write_bytes(path.read_bytes() + b'# local drift\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'baseline mismatch'):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_helper_collision_before_any_write(self):
        (self.root / repair.HELPER_PATH).write_text('# unrelated helper\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'collision'):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_partial_repair_rejected(self):
        path = 'geonode/api/views.py'
        (self.root / path).write_bytes(repair.transform_existing(path, self.originals[path]))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'baseline mismatch'):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_helper_drift_is_not_silently_repaired(self):
        repair.apply(self.root)
        path = self.root / repair.HELPER_PATH
        path.write_bytes(path.read_bytes() + b'# drift\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            repair.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_symlink_rejected_without_touching_target(self):
        witness = Path(self.temporary.name) / 'witness'
        witness.write_text('unmodified')
        (self.root / repair.HELPER_PATH).symlink_to(witness)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            repair.apply(self.root)
        self.assertEqual(witness.read_text(), 'unmodified')

    def test_parent_symlink_rejected(self):
        directory = self.root / 'geonode/api'
        moved = self.root / 'geonode/api-original'
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            repair.apply(self.root)

    def test_root_symlink_rejected(self):
        alias = Path(self.temporary.name) / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            repair.apply(alias)

    def test_individual_transform_rejects_unrecognized_source(self):
        for name, data in self.originals.items():
            with self.subTest(path=name), self.assertRaises(ValueError):
                repair.transform_existing(name, data + b'\n')

    def test_tokeninfo_helper_untouched_and_default_off_preserved(self):
        repair.apply(self.root)
        settings = (self.root / 'geonode/settings.py').read_text()
        views = (self.root / 'geonode/api/views.py').read_text()
        self.assertEqual(settings.count('OAUTH2_ROLE_SERVICE_STRICT = False'), 1)
        self.assertEqual(settings.count('OAUTH2_BACKEND_TOKENINFO_STRICT = False'), 1)
        self.assertIn('return strict_verify_token(request)', views)
        self.assertIn('User.objects.filter(email=user_name)', views)
        self.assertNotIn(verifier_repair.HELPER_PATH, repair.expected_files())

    def test_only_two_middleware_methods_defer_exact_role_callbacks(self):
        repair.apply(self.root)
        tree = ast.parse((self.root / 'geonode/security/middleware.py').read_text())
        guarded = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and any(
                        isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                        and call.func.id == 'is_strict_role_request' for call in ast.walk(method)):
                        guarded.append((node.name, method.name))
        self.assertEqual(guarded, [('AuthenticateBasicAuthOrApiKeyMiddleware', 'process_request'),
                                 ('SessionControlMiddleware', 'process_request')])


if __name__ == '__main__':
    unittest.main()
