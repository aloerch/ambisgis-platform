from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.validate_package import validate_contract_package

ROOT = Path(__file__).resolve().parent.parent


class TraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((ROOT / 'contracts/contract-package.json').read_text())

    def test_all_required_scope_is_preserved(self):
        validate_contract_package(package=self.package)

    def test_missing_requirement_or_required_test_rejected(self):
        for i in range(24):
            candidate = deepcopy(self.package)
            candidate['requirements'].pop(i)
            with self.assertRaises(ValueError):
                validate_contract_package(package=candidate)
            candidate = deepcopy(self.package)
            candidate['requirements'][i]['tests'].pop()
            with self.assertRaises(ValueError):
                validate_contract_package(package=candidate)

    def test_missing_phase_or_weakened_exit_rejected(self):
        for i in range(8):
            candidate = deepcopy(self.package)
            candidate['phase_gates'].pop(i)
            with self.assertRaises(ValueError):
                validate_contract_package(package=candidate)
            candidate = deepcopy(self.package)
            candidate['phase_gates'][i]['exit_evidence'] = 'A passing scaffold is enough.'
            with self.assertRaises(ValueError):
                validate_contract_package(package=candidate)

    def test_contract_validation_cannot_claim_product_acceptance(self):
        for mutation in ['product', 'phase', 'test']:
            candidate = deepcopy(self.package)
            if mutation == 'product':
                candidate['product_accepted'] = True
            elif mutation == 'phase':
                candidate['phase_gates'][0]['accepted'] = True
            else:
                candidate['requirements'][0]['product_test_status'] = 'passed'
            with self.assertRaises(ValueError):
                validate_contract_package(package=candidate)

    def test_missing_task_and_nonlocal_contract_rejected(self):
        candidate = deepcopy(self.package)
        candidate['requirements'][0]['tasks'].pop()
        with self.assertRaises(ValueError):
            validate_contract_package(package=candidate)
        candidate = deepcopy(self.package)
        candidate['contracts']['query'] = '../README.md'
        with self.assertRaises(ValueError):
            validate_contract_package(package=candidate)
