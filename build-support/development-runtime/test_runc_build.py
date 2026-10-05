"""Source/archives only; native execution is confined to the reviewed producer."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

import runc_build as build


class RuncSourceTests(unittest.TestCase):
    def test_exact_repair_preserves_init_and_excludes_other_environment(self):
        self.assertEqual(build.sha(build.ARCHIVE), build.PINS[build.ARCHIVE])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build.extract(build.ARCHIVE, root)
            original = (root / 'libcontainer/container_linux.go').read_text()
            before = {str(p.relative_to(root)): build.sha(p) for p in root.rglob('*') if p.is_file()}
            patch = build.patch(root)
            changed = (root / 'libcontainer/container_linux.go').read_text()
            self.assertIn('cmd.Env = ambisgisInitEnvironment(os.Getenv)', changed)
            self.assertNotIn('ambisgisInitEnvironment', original)
            self.assertIn('getenv("LD_LIBRARY_PATH")', build.HELPER)
            self.assertNotIn('os.Environ', build.HELPER)
            self.assertNotIn('LD_PRELOAD', build.HELPER)
            self.assertEqual(build.sha(root / 'libcontainer/init_linux.go'), build.INIT_SHA)
            after = {str(p.relative_to(root)): build.sha(p) for p in root.rglob('*') if p.is_file()}
            self.assertEqual(set(after) - set(before), {'libcontainer/ambisgis_environment_test.go'})
            self.assertEqual([p for p in before if before[p] != after[p]], ['libcontainer/container_linux.go'])
            self.assertIn('-\tcmd.Env = append(cmd.Env, "GOMAXPROCS="+os.Getenv("GOMAXPROCS"))', patch)
            with self.assertRaises(ValueError): build.patch(root)

    def test_changed_input_is_rejected_before_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); build.extract(build.ARCHIVE, root)
            target = root / 'libcontainer/container_linux.go'
            target.write_text(target.read_text() + '\n// changed\n')
            before = target.read_bytes()
            with self.assertRaises(ValueError): build.patch(root)
            self.assertEqual(target.read_bytes(), before)
            self.assertFalse((root / 'libcontainer/ambisgis_environment_test.go').exists())

    def test_archive_rejects_links_traversal_duplicates_and_specials(self):
        for variant in ('parent', 'absolute', 'link', 'fifo', 'duplicate'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); archive = root / 'bad.tar'; output = root / 'output'; output.mkdir()
                with tarfile.open(archive, 'w') as tar:
                    name = {'parent':'runc-1.5.1/../outside', 'absolute':'/outside'}.get(variant, 'runc-1.5.1/file')
                    member = tarfile.TarInfo(name)
                    if variant == 'link': member.type=tarfile.SYMTYPE; member.linkname='/outside'
                    elif variant == 'fifo': member.type=tarfile.FIFOTYPE
                    tar.addfile(member, io.BytesIO())
                    if variant == 'duplicate': tar.addfile(member, io.BytesIO())
                with self.assertRaises(ValueError): build.extract(archive, output)
                self.assertFalse((root / 'outside').exists())


if __name__ == '__main__': unittest.main()
