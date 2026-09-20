"""Protect case evidence against disappeared, duplicated, skipped and masked tests."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import native_case_evidence as evidence


def case(classname, name, outcome='passed'):
    return {'classname': classname, 'name': name, 'outcome': outcome}


def baseline(target):
    if target == 'mapfish':
        rows = [case(name, method, 'error') for name, methods in evidence.MAPFISH_FAILURES.items() for method in methods]
    else:
        rows = [case(evidence.SCHEMA_CLASS, '', 'error')]
    return {'cases': rows}


def repaired(target):
    old = baseline(target)
    if target == 'mapfish':
        return {'cases': [{**row, 'outcome': 'passed'} for row in old['cases']]}
    return {'cases': [case(evidence.SCHEMA_CLASS, method) for method in evidence.SCHEMA_METHODS]}


class CaseEvidenceTests(unittest.TestCase):
    def report(self, root, records, counts=None, extra=None, encoding='utf-8'):
        name = 'org.mapfish.print.PDFUtilsTest'
        directory = root / evidence.MODULES['mapfish'] / 'target/surefire-reports'
        directory.mkdir(parents=True, exist_ok=True)
        actual = {'tests': str(len(records)), 'failures': str(sum(row['outcome'] == 'failure' for row in records)),
                  'errors': str(sum(row['outcome'] == 'error' for row in records)),
                  'skipped': str(sum(row['outcome'] == 'skipped' for row in records))}
        if counts:
            actual.update(counts)
        suite = ET.Element('testsuite', {'name': name, **actual})
        for row in records:
            element = ET.SubElement(suite, 'testcase', {'classname': row['classname'], 'name': row['name']})
            if row['outcome'] != 'passed':
                ET.SubElement(element, row['outcome'], {'message': 'original failure'}).text = 'original traceback'
            if extra:
                ET.SubElement(element, extra)
        path = directory / ('TEST-' + name + '.xml')
        path.write_bytes(ET.tostring(suite, encoding=encoding, xml_declaration=True))
        return path

    def test_duplicate_setup_teardown_rows_preserve_counts_and_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            row = case('org.mapfish.print.PDFUtilsTest', 'testPlaceholder', 'error')
            path = self.report(root, [row, row])
            parsed = evidence.report_cases(root, 'mapfish')
            self.assertEqual(parsed['totals']['errors'], 2)
            self.assertEqual(parsed['unique_identities'], 1)
            self.assertEqual(parsed['duplicate_records'][0]['records'], 2)
            self.assertEqual(parsed['reports'][0]['sha256'], evidence.sha(path))
            self.assertEqual([row['record_index'] for row in parsed['cases']], [0, 1])

    def test_suite_success_cannot_mask_case_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.report(root, [case('org.mapfish.print.PDFUtilsTest', 'a', 'error')], {'errors': '0'})
            with self.assertRaisesRegex(ValueError, 'counters disagree'):
                evidence.report_cases(root, 'mapfish')

    def test_contradictory_or_retry_outcomes_are_rejected(self):
        for extra in ('failure', 'flakyFailure', 'rerunError'):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.report(root, [case('org.mapfish.print.PDFUtilsTest', 'a', 'error')], extra=extra)
                with self.assertRaises(ValueError):
                    evidence.report_cases(root, 'mapfish')

    def test_malformed_counts_reports_and_empty_directory_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, 'no native'):
                evidence.report_cases(root, 'mapfish')
            path = self.report(root, [], {'tests': '-1'})
            with self.assertRaisesRegex(ValueError, 'malformed'):
                evidence.report_cases(root, 'mapfish')
            path.write_text('<testsuite>')
            with self.assertRaises(Exception):
                evidence.report_cases(root, 'mapfish')

    def test_encoded_xml_declarations_are_not_expanded(self):
        for encoding in ('utf-8', 'utf-16', 'utf-32'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = self.report(root, [])
                path.write_bytes(('<?xml version="1.0" encoding="' + encoding + '"?>'
                                  '<!DOCTYPE testsuite [<!ENTITY x "expanded">]><testsuite/>').encode(encoding))
                with self.assertRaises(Exception):
                    evidence.report_cases(root, 'mapfish')

    def test_all_17_historical_failures_must_be_accounted_for(self):
        before, after = baseline('mapfish'), repaired('mapfish')
        before['cases'].append(deepcopy(before['cases'][0]))
        result = evidence.compare_cases(before, after, 'mapfish')
        self.assertTrue(result['verified'])
        self.assertEqual(result['historical_failed_unique_identities'], 17)
        self.assertEqual(result['historical_failed_records'], 18)
        self.assertTrue(any(len(row['historical_records']) == 2 for row in result['case_mappings']))

    def test_missing_historical_baseline_case_cannot_shrink_scope(self):
        before, after = baseline('mapfish'), repaired('mapfish')
        before['cases'].pop()
        result = evidence.compare_cases(before, after, 'mapfish')
        self.assertFalse(result['verified'])
        self.assertEqual(result['problems'][0]['kind'], 'historical-failure-identities-differ')

    def test_hidden_xml_class_rule_record_maps_to_five_methods(self):
        result = evidence.compare_cases(baseline('xml'), repaired('xml'), 'xml')
        self.assertTrue(result['verified'])
        self.assertEqual(result['case_mappings'][0]['hidden_class_rule_methods'], 5)
        self.assertEqual(len(result['case_mappings'][0]['current_cases']), 5)

    def test_missing_failed_hidden_or_previously_passing_case_fails(self):
        for target in ('xml', 'mapfish'):
            for hidden in (True, False):
                with self.subTest(target=target, hidden=hidden):
                    before, after = baseline(target), repaired(target)
                    if hidden:
                        after['cases'].pop()
                    else:
                        before['cases'].append(case('previous.PassingTest', 'mustRemain'))
                    result = evidence.compare_cases(before, after, target)
                    self.assertFalse(result['verified'])
                    self.assertTrue(any(row['kind'] == 'missing-case' for row in result['problems']))

    def test_new_errors_skips_or_duplicate_passes_cannot_be_success(self):
        for outcome in ('error', 'failure', 'skipped', 'duplicate'):
            with self.subTest(outcome=outcome):
                before, after = baseline('mapfish'), repaired('mapfish')
                if outcome == 'duplicate':
                    after['cases'].append(deepcopy(after['cases'][0]))
                else:
                    after['cases'][0]['outcome'] = outcome
                self.assertFalse(evidence.compare_cases(before, after, 'mapfish')['verified'])

    def test_inherited_skips_remain_visible_and_cannot_disappear(self):
        before, after = baseline('mapfish'), repaired('mapfish')
        skipped = case('org.mapfish.InheritedTest', 'a', 'skipped')
        before['cases'].append(skipped)
        after['cases'].append(skipped)
        self.assertTrue(evidence.compare_cases(before, after, 'mapfish')['verified'])
        after['cases'].pop()
        self.assertFalse(evidence.compare_cases(before, after, 'mapfish')['verified'])


if __name__ == '__main__':
    unittest.main()
