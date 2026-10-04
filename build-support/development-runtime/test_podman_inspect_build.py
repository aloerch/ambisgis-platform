"""Inert owned inspect repair checks. Never execute a compiler or engine."""
import ast
from pathlib import Path
import tempfile
import unittest
import podman_inspect_build as build


class InspectBuildTests(unittest.TestCase):
    def fixture(self, root):
        for name in build.SOURCE_HASHES:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((build.PRIOR/'source'/name).read_bytes())

    def test_actual_old_contract_fails_then_patch_is_exact(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            old={n:(root/n).read_bytes() for n in build.SOURCE_HASHES}
            with self.assertRaisesRegex(AssertionError,'projection is absent'):
                build.source_contract(root)
            delta, baseline, selection=build.patch(root)
            build.source_contract(root)
            self.assertEqual({n:t.encode() for n,t in baseline.items()},old)
            for name in old:
                self.assertEqual((root/name).read_text().replace(build.ADDITIONS[name],'',1).encode(),old[name])
            self.assertEqual({r['file'] for r in selection},set(old))
            self.assertEqual({str(p.relative_to(root)) for p in root.rglob('*.go')},set(old)|{'libpod/ambisgis_inspect_sysctls.go','libpod/ambisgis_inspect_sysctls_test.go'})
            self.assertIn('+++ b/libpod/define/container_inspect.go',delta)

    def test_each_wrong_source_or_existing_helper_rejects_before_writes(self):
        for case in (*build.SOURCE_HASHES,'ambisgis_inspect_sysctls.go','ambisgis_inspect_sysctls_test.go'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                root=Path(d);self.fixture(root)
                target=root/(case if case in build.SOURCE_HASHES else 'libpod/'+case)
                target.write_text(target.read_text()+'// drift' if target.exists() else 'preserve')
                old={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with self.assertRaises(ValueError):build.patch(root)
                self.assertEqual(old,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_revalidation_rejects_drift_in_both_native_files_and_new_files(self):
        for name in (*build.SOURCE_HASHES,'libpod/ambisgis_inspect_sysctls.go','libpod/ambisgis_inspect_sysctls_test.go'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                root=Path(d);self.fixture(root);build.patch(root)
                path=root/name;path.write_text(path.read_text()+'// drift')
                with self.assertRaises(AssertionError):build.source_contract(root)

    def test_future_commands_are_only_explicit_unit_and_binary_builds(self):
        plan=build.command_plan(Path('/fresh/job'))
        self.assertEqual([p[0] for p in plan],['inspect-compile','inspect-unit','podman-build','rootlessport-build'])
        self.assertEqual([p[2] for p in plan],[0,0,0,0])
        self.assertEqual(plan[0][1][-2:],['libpod/ambisgis_inspect_sysctls.go','libpod/ambisgis_inspect_sysctls_test.go'])
        self.assertEqual(plan[1][1][1:],['-test.run=^TestAmbisGISInspectSysctls$','-test.count=1','-test.v'])
        for _,argv,_ in plan:
            for forbidden in ('./libpod','./test','checkpoint','namespace','gitCommit','-ldflags'):
                self.assertNotIn(forbidden,' '.join(argv))
        for forbidden in ('exec.Command','ConnectToDBUS','NewConnection','net.Dial','os.StartProcess','package main','TestMain'):
            self.assertNotIn(forbidden,build.HELPER+build.TEST)
        self.assertIn('return maps.Clone(value.Linux.Sysctl)',build.HELPER)
        self.assertIn('parser.ParseFile',build.TEST)

    def test_native_log_oracle_rejects_missing_duplicate_failure_and_extra(self):
        lines=['=== RUN   TestAmbisGISInspectSysctls']
        for case in build.CASES:
            lines += ['=== RUN   TestAmbisGISInspectSysctls/'+case,'    --- PASS: TestAmbisGISInspectSysctls/'+case+' (0.00s)']
        good='\n'.join(lines)+'\n--- PASS: TestAmbisGISInspectSysctls (0.00s)\nPASS\n'
        self.assertTrue(build.unit_result(good))
        for bad in (good.replace('nil_spec','renamed'),good.replace('--- PASS:','--- FAIL:',1),good.replace(lines[1],lines[1]+'\n'+lines[1]),good.replace('PASS\n','=== RUN   Extra\nPASS\n'),'compile error\nFAIL\n'):
            self.assertFalse(build.unit_result(bad))

    def test_prior_pins_and_callsite_bytes_are_actual(self):
        for path,identity in build.PINS.items():self.assertEqual(build.sha(path),identity)
        for name,identity in build.SOURCE_HASHES.items():self.assertEqual(build.sha(build.PRIOR/'source'/name),identity)

    def test_no_predecessor_execution_dispatch_and_full_custody_remains(self):
        source=Path(build.__file__).read_text();tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id in ('previous','helper'):
                self.assertNotIn(node.func.attr,('prepare','execute','child','main'))
        for field in ('modifications_sha256','compiler_commands','host_compiler_support','supervisor','retained_toolchain_sources'):
            self.assertIn(field,source)
        self.assertIn("sha(output/'owned-source.patch')!=p['new_patch_sha256']",source)
        self.assertIn("source_contract(output/'source')",source)


if __name__=='__main__':unittest.main()
