"""Adversarial boundary guards; real DB/HTTP evidence is the separate runtime."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from native import ContractError, Provider, c1_request, keyset, predicate, where_filter
from native_contracts import ROOT, validate_query


class NativeBoundaryGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layer = json.loads((ROOT / 'examples/layer.json').read_text())

    def params(self, **extra):
        return {'serviceRevision': self.layer['service_revision'], 'dataRevision': self.layer['data_revision'], **extra}

    def test_where_values_remain_parameters(self):
        value = "O'Neil; DROP TABLE addresses --"
        node = where_filter("name = 'O''Neil; DROP TABLE addresses --'")
        parameters = []
        sql = predicate(node, parameters)
        self.assertEqual(parameters, [value])
        self.assertNotIn(value, sql)
        self.assertEqual(sql, '"name" COLLATE "C" = %s')

    def test_unsupported_where_never_broadens(self):
        for text in ('1=1 OR name IS NULL', 'population + 1 > 2', 'lower(name) = \'x\'', 'name = NULL',
                     'name = \'x\'; SELECT 1', 'missing = 1', 'name LIKE \'x%\''):
            with self.subTest(text=text), self.assertRaises(ContractError):
                c1_request(self.params(where=text), self.layer)

    def test_false_booleans_are_feature_mode(self):
        query, offset = c1_request(self.params(returnCountOnly='false', returnExtentOnly='false'), self.layer)
        self.assertEqual(query['mode'], 'features')
        self.assertEqual(offset, 0)

    def test_ambiguous_aggregate_rejected(self):
        with self.assertRaises(ContractError):
            c1_request(self.params(returnCountOnly='true', returnExtentOnly='true'), self.layer)

    def test_offset_requires_exact_immutable_revision(self):
        for params in ({'resultOffset': '2'}, self.params(resultOffset='2', dataRevision='20000000-0000-4000-8000-000000000006')):
            with self.assertRaises(ContractError): c1_request(params, self.layer)

    def test_budgets_and_unknown_formats_rejected(self):
        for params in ({'resultRecordCount': '1001'}, {'resultOffset': '-1'}, {'f': 'pbf'}, {'f': 'geojson'},
                       {'outStatistics': '[]'}, {'where': '(' * 9 + 'object_id = 1' + ')' * 9},
                       {'where': 'elevation = 0.0001'}, {'where': 'object_id = 2147483648'}):
            with self.subTest(params=params), self.assertRaises(ContractError):
                c1_request(self.params(**params), self.layer)

    def test_keyset_desc_null_then_tie_is_parameterized(self):
        values = []
        sql = keyset([{'field': 'name', 'direction': 'desc'}, {'field': 'object_id', 'direction': 'asc'}],
                     [None, {'type': 'int32', 'value': 3}], values)
        self.assertEqual(values, [3])
        self.assertIn('"name" COLLATE "C" IS NULL', sql)
        self.assertIn('"object_id" > %s', sql)

    def test_malformed_credentials_fail_before_http(self):
        provider = Provider({'layer': self.layer, 'cursor_key': 'ab' * 32}, None, lambda row: None)
        for credential in ('Bearer bad\r\nX-Foo: value', 'Bearer ' + 'a' * 513, 'Basic abc', None):
            with self.subTest(credential_type=type(credential).__name__), self.assertRaises(ContractError) as error:
                provider.authorize('public_points', credential)
            self.assertEqual(error.exception.code, 'NOT_FOUND_OR_FORBIDDEN')

    def test_row_field_restrictions_not_implied_by_projection(self):
        for mode in ('row', 'field'):
            layer = deepcopy(self.layer); layer['policy_mode'] = mode
            request = {'schema_version': 1, **{key: layer[key] for key in ('layer_id', 'service_revision', 'data_revision')},
                       'mode': 'features', 'fields': ['name']}
            with self.assertRaises(ContractError): validate_query(request, layer)


if __name__ == '__main__':
    unittest.main()
