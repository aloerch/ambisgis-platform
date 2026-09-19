from copy import deepcopy
import random
import unittest
from tools.merge_reference import merge_feature


class MergeTests(unittest.TestCase):
    def test_branch_unchanged_takes_target(self):
        self.assertEqual(merge_feature({'a':1},{'a':1},{'a':2}).candidate, {'a':2})
    def test_target_unchanged_takes_branch(self):
        self.assertEqual(merge_feature({'a':1},{'a':2},{'a':1}).candidate, {'a':2})
    def test_disjoint_attribute_edits(self):
        r=merge_feature({'a':1,'b':1},{'a':2,'b':1},{'a':1,'b':3})
        self.assertEqual((r.candidate,r.conflicts),({'a':2,'b':3},()))
    def test_same_field_conflict_has_no_candidate(self):
        r=merge_feature({'a':1},{'a':2},{'a':3})
        self.assertIsNone(r.candidate); self.assertEqual(r.conflicts,('a',))
    def test_equal_concurrent_edit(self):
        self.assertEqual(merge_feature({'a':1},{'a':2},{'a':2}).candidate, {'a':2})
    def test_delete_unchanged(self):
        self.assertEqual(merge_feature({'a':1},None,{'a':1}).conflicts,())
        self.assertIsNone(merge_feature({'a':1},None,{'a':1}).candidate)
    def test_delete_update_conflict(self):
        self.assertEqual(merge_feature({'a':1},None,{'a':2}).conflicts,('delete/update',))
    def test_both_delete(self):
        self.assertEqual(merge_feature({'a':1},None,None).conflicts,())
    def test_distinct_insert_same_uuid_conflict(self):
        self.assertEqual(merge_feature(None,{'a':1},{'b':2}).conflicts,('insert/insert',))
    def test_equal_insert_coalesces(self):
        self.assertEqual(merge_feature(None,{'a':1},{'a':1}).candidate,{'a':1})
    def test_null_and_missing_are_distinct(self):
        self.assertEqual(merge_feature({'a':0},{'a':None},{}).conflicts,('a',))
    def test_geometry_is_atomic(self):
        r=merge_feature({'geometry':'base-z-m'},{'geometry':'new-z'},{'geometry':'new-m'})
        self.assertEqual(r.conflicts,('geometry',))
    def test_inputs_and_outputs_do_not_alias(self):
        b={'a':[1]}; old=deepcopy(b);r=merge_feature(b,b,{'a':[2]})
        r.candidate['a'].append(3)
        self.assertEqual(b,old)
    def test_bad_type_rejected(self):
        with self.assertRaises(TypeError): merge_feature([],{}, {})
    def test_randomized_symmetry_and_unchanged_side(self):
        rng=random.Random(20260919)
        states=[None]+[{'a':a,'b':b} for a in [None,0,1,2] for b in [None,0,1,2]]
        for _ in range(1000):
            b,o,t=(deepcopy(rng.choice(states)) for _ in range(3))
            self.assertEqual(merge_feature(b,o,t),merge_feature(b,t,o))
            self.assertEqual(merge_feature(b,b,t).candidate,t)
            self.assertEqual(merge_feature(b,o,b).candidate,o)


if __name__=='__main__':unittest.main()
