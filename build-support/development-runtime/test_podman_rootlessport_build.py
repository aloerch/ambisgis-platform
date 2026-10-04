# SPDX-License-Identifier: GPL-3.0-or-later
"""Inert producer/source guards; native AF_UNIX and Go checks are separate."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location("rootlessport_recipe",Path(__file__).with_name("podman_rootlessport_build.py"))
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)

class RootlessportProducer(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/"source";self.target=self.source/"cmd/rootlessport/main.go";self.target.parent.mkdir(parents=True)
        self.original=(recipe.PRIOR/"source/cmd/rootlessport/main.go").read_text()
        self.target.write_text(self.original)
        self.addCleanup(patch.stopall)
        patch.object(recipe.subprocess,"run",side_effect=AssertionError("native execution forbidden")).start()
        patch.object(recipe.subprocess,"Popen",side_effect=AssertionError("native execution forbidden")).start()
    def test_exact_patch_reversible(self):
        delta,baseline,selected=recipe.patch(self.source)
        changed=self.target.read_text();restored=changed
        for old,new in reversed(recipe.ANCHORS):restored=restored.replace(new,old)
        self.assertEqual(restored,self.original)
        self.assertEqual(selected["before_sha256"],recipe.SOURCE_SHA)
        self.assertIn("return directory, stateDir, nil",baseline)
        self.assertIn("cmd.ExtraFiles = []*os.File{stateDirectory}",delta)
        self.assertEqual(len(list(self.target.parent.iterdir())),3)
        recipe.source_contract(self.source)
    def test_unselected_source_and_vendor_unchanged(self):
        vendor=self.source/"vendor/unchanged";vendor.parent.mkdir();vendor.write_bytes(b"retained fixture")
        other=self.source/"other.go";other.write_bytes(b"unselected fixture")
        recipe.patch(self.source)
        self.assertEqual(vendor.read_bytes(),b"retained fixture");self.assertEqual(other.read_bytes(),b"unselected fixture")
    def test_source_drift_refused_before_write(self):
        self.target.write_text(self.original+"\n");before=self.target.read_bytes()
        with self.assertRaises(ValueError):recipe.patch(self.source)
        self.assertEqual(self.target.read_bytes(),before);self.assertEqual(len(list(self.target.parent.iterdir())),1)
    def test_preexisting_helper_refused(self):
        (self.target.parent/"ambisgis_rootlessport.go").write_text("collision")
        with self.assertRaises(ValueError):recipe.patch(self.source)
        self.assertEqual(self.target.read_text(),self.original)
    def test_repeated_patch_refused(self):
        recipe.patch(self.source);before={p.name:p.read_bytes() for p in self.target.parent.iterdir()}
        with self.assertRaises(ValueError):recipe.patch(self.source)
        self.assertEqual({p.name:p.read_bytes() for p in self.target.parent.iterdir()},before)
    def test_missing_production_callsite_rejected(self):
        recipe.patch(self.source);self.target.write_text(self.target.read_text().replace("statePath, 3)","statePath, 4)"))
        with self.assertRaises(AssertionError):recipe.source_contract(self.source)
    def test_changed_helper_rejected(self):
        recipe.patch(self.source);(self.target.parent/"ambisgis_rootlessport.go").write_text(recipe.HELPER+"\n")
        with self.assertRaises(AssertionError):recipe.source_contract(self.source)
    def output(self,baseline=False):
        cases={"TestAmbisGISRootlessportSocket":("parent_bind","child_descriptor","child_listener")}
        if not baseline:cases.update({"TestAmbisGISRootlessportInput":("symlink_rejected","regular_file_rejected","opaque_contract"),"TestAmbisGISRootlessportLifecycle":("early_error","early_nil","normal_eof","input_error","shutdown_bound")})
        status="FAIL" if baseline else "PASS"
        return "".join("=== RUN   "+name+"/"+case+"\n--- "+status+": "+name+"/"+case+" (0.01s)\n" for name,sub in cases.items() for case in sub)+status+"\n"
    def test_complete_outcome_projections(self):
        self.assertTrue(recipe.unit_result(self.output()));self.assertTrue(recipe.unit_result(self.output(True),baseline=True))
    def test_missing_duplicate_failed_or_skipped_case_rejected(self):
        value=self.output()
        for bad in (value.replace("=== RUN   TestAmbisGISRootlessportLifecycle/early_error\n",""),value+value,value.replace("--- PASS: TestAmbisGISRootlessportLifecycle/early_error","--- FAIL: TestAmbisGISRootlessportLifecycle/early_error"),value.replace("--- PASS: TestAmbisGISRootlessportLifecycle/early_error","--- SKIP: TestAmbisGISRootlessportLifecycle/early_error")):
            self.assertFalse(recipe.unit_result(bad))
    def test_baseline_must_actually_fail_long_paths(self):
        value=self.output(True)
        self.assertFalse(recipe.unit_result(value.replace("--- FAIL: TestAmbisGISRootlessportSocket/parent_bind","--- PASS: TestAmbisGISRootlessportSocket/parent_bind"),baseline=True))
    def test_finite_native_plan(self):
        commands=recipe.command_plan(Path("/private/fresh"))
        self.assertEqual([v[0] for v in commands],["inspect-compile","inspect-unit","baseline-compile","baseline-unit","rootlessport-compile","rootlessport-unit","podman-build","rootlessport-build"])
        self.assertEqual([v[2] for v in commands],[0,0,0,1,0,0,0,0])
        for name,args,_ in commands:
            if name in ("baseline-unit","rootlessport-unit"):self.assertIn("-test.timeout=15s",args)
            elif name=="inspect-unit":self.assertIn("-test.run=^TestAmbisGISInspectSysctls$",args)
            else:self.assertIn("-mod=vendor",args)
        self.assertTrue(all("./cmd/rootlessport" not in row[1] or row[0]=="rootlessport-build" for row in commands))

if __name__=="__main__":unittest.main()
