"""Inert preparation/source contracts only; never compile Go or connect to systemd."""
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import podman_health_timer_build as build


class HealthTimerTests(unittest.TestCase):
    def fixture(self,root):
        path=root/'libpod/healthcheck_linux.go';path.parent.mkdir(parents=True)
        path.write_bytes((build.PRIOR/'source/libpod/healthcheck_linux.go').read_bytes())
        return path

    def test_same_source_contract_fails_before_and_passes_after_patch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=self.fixture(root);original=target.read_text()
            with self.assertRaisesRegex(AssertionError,'Finite owned timer path is absent'):build.source_contract(root)
            delta,baseline,selection=build.patch(root)
            build.source_contract(root)
            self.assertEqual(baseline,original)
            self.assertEqual(target.read_text().replace(build.BRANCH,''),original)
            self.assertEqual(target.read_text().split('func systemdOpSuccessful',1)[1],original.split('func systemdOpSuccessful',1)[1])
            self.assertTrue(selection['unselected_start_cleanup_unchanged'])
            self.assertEqual(sorted(str(p.relative_to(root)) for p in root.rglob('*.go')),['libpod/ambisgis_health_timer.go','libpod/ambisgis_health_timer_test.go','libpod/healthcheck_linux.go'])
            self.assertIn('+++ b/libpod/ambisgis_health_timer.go',delta)

    def test_wrong_source_or_existing_repair_preserves_all_bytes(self):
        for case in ('changed','helper','test'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
                root=Path(d);target=self.fixture(root)
                if case=='changed':target.write_text(target.read_text()+'\n// changed\n')
                else:(target.parent/('ambisgis_health_timer.go' if case=='helper' else 'ambisgis_health_timer_test.go')).write_text('preserve')
                old={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with self.assertRaises(ValueError):build.patch(root)
                self.assertEqual(old,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_explicit_marker_precedes_all_profile_validation(self):
        helper=build.HELPER
        self.assertLess(helper.index('if profile == "" { return nil, nil }'),helper.index('profile != "development-v1"'))
        for code in ('!rootless','startup','interval != "15s"','filepath.Clean(path) != path','^/[A-Za-z0-9_./-]+$','reflect.DeepEqual(global, expected)'):
            self.assertIn(code,helper)
        self.assertNotIn('os.Getenv',helper)
        self.assertLess(build.BRANCH.index('if err != nil'),build.BRANCH.index('ConnectToDBUS'))
        self.assertIn('if plan != nil {',build.BRANCH)

    def test_wire_membership_types_and_job_order_are_bound(self):
        for code in ('"TimersMonotonic", []ambisgisMonotonicTimer{{"OnUnitInactiveSec",15000000}}','"AccuracyUSec",uint64(1000000)','"RemainAfterElapse",false','"LogLevelMax",int32(5)','"StartLimitIntervalUSec",uint64(0)','dbus.PropExecStart(command,false)','make(chan string,1)','case <-ctx.Done():','reconcile exact timer and service before retry'):
            self.assertIn(code,build.HELPER)
        self.assertIn('context.WithTimeout(context.Background(), ambisgisHealthTimerTimeout)',build.BRANCH)
        self.assertIn('conn.StartTransientUnitAux(ctx, plan.UnitName+".timer", "fail", plan.Timer, plan.Aux, job)',build.BRANCH)
        self.assertIn('defer conn.Close()',build.BRANCH)
        self.assertNotIn('StopUnit',build.BRANCH+build.HELPER)
        self.assertNotIn('ResetFailed',build.BRANCH+build.HELPER)
        self.assertIn('const ambisgisHealthTimerTimeout = 30 * time.Second',build.HELPER)

    def test_future_native_test_compiles_only_two_new_pure_files(self):
        plan=build.command_plan(Path('/fresh/job'))
        self.assertEqual([r[0] for r in plan],['timer-compile','timer-unit','podman-build','rootlessport-build'])
        self.assertEqual([r[2] for r in plan],[0,0,0,0])
        self.assertEqual(plan[0][1][-2:],['libpod/ambisgis_health_timer.go','libpod/ambisgis_health_timer_test.go'])
        self.assertEqual(plan[1][1][1:],['-test.run=^TestAmbisGISHealthTimer$','-test.count=1','-test.v'])
        for name,argv,_ in plan:
            for forbidden in ('./libpod','./test','checkpoint','namespace','gitCommit','-ldflags'):
                self.assertNotIn(forbidden,' '.join(argv))
            if name!='timer-unit':
                for flag in ('-mod=vendor','-buildvcs=false','-trimpath','-p=2'):self.assertIn(flag,argv)
        for forbidden in ('exec.Command','ConnectToDBUS','NewConnection','net.Dial','os.StartProcess','package main','TestMain'):
            # Comment's explicit absence statement is not executable code.
            actual='\n'.join(l for l in (build.HELPER+build.TEST).splitlines() if not l.lstrip().startswith('//'))
            self.assertNotIn(forbidden,actual)

    def test_native_log_oracle_rejects_missing_duplicate_failure_or_wrong_cases(self):
        lines=[]
        for case in build.CASES:lines+=['=== RUN   TestAmbisGISHealthTimer/'+case,'    --- PASS: TestAmbisGISHealthTimer/'+case+' (0.00s)']
        good='\n'.join(lines)+'\nPASS\n';self.assertTrue(build.unit_result(good))
        for bad in (good.replace('wire_properties','renamed'),good.replace('--- PASS:','--- FAIL:',1),good+lines[0]+'\n',good.replace(lines[0],lines[0]+'\n'+lines[0]),'compile error\nFAIL\n'):
            self.assertFalse(build.unit_result(bad))

    def test_prior_producer_pins_match_exact_actual_receipts(self):
        for path,identity in build.PINS.items():self.assertEqual(build.sha(path),identity)
        self.assertEqual(build.sha(build.PRIOR/'source/libpod/healthcheck_linux.go'),build.SOURCE_SHA)
        self.assertEqual(build.retained_predecessor().sha(build.PRIOR/'build-executed.py'),build.PINS[build.PRIOR/'build-executed.py'])

    def test_no_predecessor_execution_dispatch_is_reused(self):
        source=Path(build.__file__).read_text();tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id in ('previous','helper'):
                self.assertNotIn(node.func.attr,('prepare','execute','child','main'))
        for field in ('modifications_sha256','compiler_commands','host_compiler_support','supervisor','retained_toolchain_sources'):
            self.assertIn(field,source)
        self.assertIn("sha(output/'owned-source.patch')!=p['new_patch_sha256']",source)


if __name__=='__main__':unittest.main()
