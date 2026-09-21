import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime_inputs


class RuntimeInputTests(unittest.TestCase):
    def test_checked_path_rejects_escape_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / 'input.jar'
            real.write_bytes(b'input')
            (root / 'link.jar').symlink_to(real)
            for relative in ('../input.jar', '/input.jar', 'a\\b', 'link.jar'):
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    runtime_inputs.checked_path(root, relative)
            self.assertEqual(runtime_inputs.checked_path(root, 'input.jar'), real)

    def test_classpath_detects_changed_or_additional_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'lib').mkdir()
            library = root / 'lib/runtime.jar'
            library.write_bytes(b'fixed runtime')
            digest = hashlib.sha256(library.read_bytes()).hexdigest()
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'artifacts': [{'binary': {
                'maven_path': 'org/example/runtime.jar', 'sha256': digest}}]}))
            (root / 'staged.json').write_text(json.dumps({
                'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                'libraries': [{'name': library.name, 'sha256': digest}]}))
            with patch.object(runtime_inputs, 'MANIFEST', manifest):
                self.assertEqual(runtime_inputs.classpath(root), str(library))
                extra = root / 'lib/extra.jar'
                extra.write_bytes(b'app leak')
                with self.assertRaisesRegex(ValueError, 'unexpected'):
                    runtime_inputs.classpath(root)
                extra.unlink()
                library.write_bytes(b'replaced')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    runtime_inputs.classpath(root)

    def test_launcher_rejects_failed_compile_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'result.json').write_text(json.dumps({'result_exit_code': 1, 'exit_code': 0}))
            with self.assertRaisesRegex(ValueError, 'successful'):
                runtime_inputs.launcher_command(root, root, root, root, root, root)

    def test_inventory_cannot_replace_pinned_runtime_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'artifacts': [{'binary': {
                'maven_path': 'org/example/runtime.jar', 'sha256': 'pinned'}}]}))
            (root / 'staged.json').write_text(json.dumps({
                'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                'libraries': [{'name': 'runtime.jar', 'sha256': 'replacement'}]}))
            with patch.object(runtime_inputs, 'MANIFEST', manifest):
                with self.assertRaisesRegex(ValueError, 'inventory differs'):
                    runtime_inputs.classpath(root)


if __name__ == '__main__':
    unittest.main()
