"""Parsing regressions; real permissions are tested only against native runtime."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/control-plane'))
from ambisgis_policy.gateway import resource


class ClosedReadSurface(unittest.TestCase):
    query = 'service=WFS&version=1.0.0&request=GetFeature&typeName=fixture:private_points&outputFormat=application/json'

    def test_canonical_read(self):
        self.assertEqual(resource('/wfs',self.query,'GET'), 'fixture:private_points')

    def test_duplicate_case_aliases(self):
        for key in ('typename', 'TYPENAME', 'typeName', '%74ypeName'):
            with self.subTest(key=key):
                self.assertIsNone(resource('/wfs',self.query+'&'+key+'=fixture:public_points','GET'))

    def test_extra_parameters_cannot_change_target_or_operation(self):
        for key in ('authkey','viewparams','cql_filter','propertyName','srsName','format_options'):
            with self.subTest(key=key):
                self.assertIsNone(resource('/wfs',self.query+'&'+key+'=x','GET'))

    def test_no_mutating_or_alternate_routes(self):
        for path in ('/rest/workspaces','/web/','/ows','/fixture/wfs','/wfs/','//wfs','/%77fs','/wfs;sessionid=x'):
            self.assertIsNone(resource(path,self.query,'GET'))
        for method in ('POST','PUT','PATCH','DELETE','HEAD','OPTIONS'):
            self.assertIsNone(resource('/wfs',self.query,method))

    def test_no_multi_resource_or_function(self):
        for name in ('fixture:private_points,fixture:public_points','other:private_points','fixture:private_points(extra)','fixture:../x',''):
            self.assertIsNone(resource('/wfs',self.query.replace('fixture:private_points',name),'GET'))

    def test_no_request_parameter_smuggling(self):
        for query in ('', self.query+'&', self.query+'&missing', self.query.replace('GetFeature','Transaction'), self.query.replace('1.0.0','2.0.0'), self.query+'x'*2048):
            self.assertIsNone(resource('/wfs',query,'GET'))


if __name__ == '__main__': unittest.main()
