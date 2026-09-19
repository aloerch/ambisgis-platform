from copy import deepcopy
import json
from pathlib import Path
import unittest
from tools.validate_package import validate_plan,validate_examples
ROOT=Path(__file__).resolve().parent.parent
try:
    from jsonschema import Draft202012Validator,FormatChecker,ValidationError
    HAVE_SCHEMAS=True
except ImportError:
    HAVE_SCHEMAS=False

class PlanTests(unittest.TestCase):
    def test_dependency_and_requirement_traceability(self):
        result=validate_plan()
        self.assertEqual(result['tasks'],66)
        self.assertEqual(result['requirements'],24)
        self.assertEqual(result['repositories'],15)

@unittest.skipUnless(HAVE_SCHEMAS,'Optional jsonschema validation dependency unavailable')
class ContractTests(unittest.TestCase):
    def validator(self,name):
        schema=json.loads((ROOT/'contracts'/f'{name}.schema.json').read_text())
        return Draft202012Validator(schema,format_checker=FormatChecker())
    def example(self,name):
        return json.loads((ROOT/'examples'/f'{name}.json').read_text())
    def test_all_examples(self):
        self.assertEqual(validate_examples(),4)
    def test_unknown_publication_output_fails(self):
        obj=self.example('publication');obj['outputs']=['knowledge_server']
        with self.assertRaises(ValidationError):self.validator('publication').validate(obj)
    def test_embedded_source_password_field_fails(self):
        obj=self.example('publication');obj['source']['password']='do-not-accept'
        with self.assertRaises(ValidationError):self.validator('publication').validate(obj)
    def test_group_sharing_requires_group(self):
        obj=self.example('publication');obj['sharing']['visibility']='groups'
        with self.assertRaises(ValidationError):self.validator('publication').validate(obj)
    def test_update_requires_expected_feature_revision(self):
        obj=self.example('edit-request');del obj['operations'][0]['expected_feature_revision']
        with self.assertRaises(ValidationError):self.validator('edit-request').validate(obj)
    def test_invalid_uuid_fails(self):
        obj=self.example('post-request');obj['expected_target_head']='not-a-uuid'
        with self.assertRaises(ValidationError):self.validator('post-request').validate(obj)
    def test_arbitrary_script_widget_type_fails(self):
        obj=self.example('application');obj['widgets'][0]['type']='arbitrary-javascript'
        with self.assertRaises(ValidationError):self.validator('application').validate(obj)

if __name__=='__main__':unittest.main()
