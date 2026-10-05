"""Inert source and command guards; no compiler, engine or Go test execution."""
from pathlib import Path
import tempfile
import unittest

import podman_env_build as build


class OrdinaryEnvironmentTests(unittest.TestCase):
    def fixture(self, root):
        folder=root/'libpod';folder.mkdir()
        target=folder/'oci_conmon_common.go'
        target.write_bytes((build.PRIOR/'source/libpod/oci_conmon_common.go').read_bytes())
        return target

    def test_only_six_callsite_environments_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=self.fixture(root);before=target.read_text()
            delta,baseline,callsites=build.patch(root);after=target.read_text()
            self.assertEqual([row['method'] for row in callsites],list(build.METHODS))
            self.assertEqual(after.count(build.CALL),6)
            # Reverse only the authorized replacements; everything else must be
            # identical, including conmon configuration and excluded methods.
            reverted=after
            for name in build.METHODS:
                segment=build.method(reverted,name)
                expected=build.WITH_PATH if name in build.METHODS[:2] else build.ASSIGNMENT
                self.assertEqual(segment.count(build.CALL),1)
                reverted=reverted.replace(segment,segment.replace(build.CALL,expected))
            self.assertEqual(reverted,before)
            for name in ('CheckpointContainer','configureConmonEnv','KillContainer'):
                self.assertEqual(build.method(after,name),build.method(before,name))
            self.assertEqual((root/'libpod/ambisgis_oci_environment.go').read_text(),build.HELPER)
            self.assertIn(build.WITH_PATH.replace('os.LookupEnv','lookup'),baseline)
            self.assertNotIn('LD_LIBRARY_PATH',baseline)
            self.assertIn('+++ b/libpod/ambisgis_oci_environment_test.go',delta)
            with self.assertRaises(ValueError):build.patch(root)

    def test_changed_source_and_existing_helpers_reject_before_write(self):
        for variant in ('changed','already_present'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);target=self.fixture(root)
                if variant=='changed':target.write_text(target.read_text()+'\n// changed\n')
                else:(root/'libpod/ambisgis_oci_environment.go').write_text('preserve')
                before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with self.assertRaises(ValueError):build.patch(root)
                self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_only_new_standalone_unit_and_two_producers_are_planned(self):
        plan=build.command_plan(Path('/fresh/job'))
        self.assertEqual([row[0] for row in plan],['baseline-compile','baseline-unit','environment-compile','environment-unit','podman-build','rootlessport-build'])
        self.assertEqual([row[2] for row in plan],[0,1,0,0,0,0])
        for name,command,_ in plan:
            joined=' '.join(command)
            for forbidden in ('./libpod','./test','specgen','checkpoint','native_tests.py','gitCommit','-ldflags'):
                self.assertNotIn(forbidden,joined)
            if name.endswith('-unit'):
                self.assertEqual(command[1:],['-test.run=^TestAmbisGISOrdinaryOCIEnvironment$','-test.count=1','-test.v'])
            else:
                self.assertIn('-mod=vendor',command);self.assertIn('-buildvcs=false',command)
        self.assertEqual(plan[2][1][-2:],['libpod/ambisgis_oci_environment.go','libpod/ambisgis_oci_environment_test.go'])

    def test_source_inventory_rejects_escaping_links_and_specials(self):
        helper=build.retained_helper()
        for variant in ('link','fifo'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)/'source';root.mkdir()
                if variant=='link':(root/'bad').symlink_to('/etc/passwd')
                else:
                    import os
                    os.mkfifo(root/'bad')
                with self.assertRaises(ValueError):build.inventory(helper,root)

    def test_signed_toolchain_dangling_targets_remain_contained(self):
        helper=build.retained_helper()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'toolchain';root.mkdir()
            link=root/'cache';link.symlink_to('var/cache')
            with self.assertRaises(FileNotFoundError):build.inventory(helper,root)
            self.assertEqual(build.inventory(helper,root,retained_toolchain=True),{'cache':{'kind':'symlink','target':'var/cache'}})
            link.unlink();link.symlink_to('../outside')
            with self.assertRaises(ValueError):build.inventory(helper,root,retained_toolchain=True)


if __name__=='__main__':unittest.main()
