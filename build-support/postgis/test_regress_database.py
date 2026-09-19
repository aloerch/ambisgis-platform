"""Evidence parser tests: incomplete/skipped runs must never become passing counts."""
import unittest
from regress_database import parse_results


class RegressionEvidenceTests(unittest.TestCase):
    def test_combined_normal_and_self_upgrade_counts(self):
        result = parse_results('a ok\nRun tests: 20\nFailed: 0\n\nother ok\nRun tests: 21\nFailed: 0\n')
        self.assertEqual(result['tests_run'], 41)
        self.assertEqual(result['tests_passed'], 41)
        self.assertTrue(result['complete'])

    def test_missing_summary_is_not_zero_failures_pass(self):
        result = parse_results('Creating database\nCould not connect\n')
        self.assertFalse(result['complete'])
        self.assertIsNone(result['tests_passed'])

    def test_failed_summary_does_not_invent_pass_count(self):
        result = parse_results('Run tests: 20\nFailed: 3\n')
        self.assertEqual(result['failure_events'], 3)
        self.assertIsNone(result['tests_passed'])

    def test_skipped_test_deducted_and_retained(self):
        result = parse_results("foo ... skipped (can't read any foo.sql)\nRun tests: 3\nFailed: 0\n")
        self.assertEqual(result['test_skips'], 1)
        self.assertEqual(result['tests_passed'], 2)
        self.assertEqual(len(result['skip_messages']), 1)

    def test_control_flow_skip_is_not_missing_sql_test(self):
        result = parse_results('Skipping upgrade test as RUNTESTFLAGS already requested upgrades\nRun tests: 3\nFailed: 0\n')
        self.assertEqual(result['test_skips'], 0)
        self.assertEqual(len(result['skip_messages']), 1)

    def test_empty_summary_does_not_establish_execution(self):
        self.assertFalse(parse_results('Run tests: 0\nFailed: 0\n')['complete'])


if __name__ == '__main__':
    unittest.main()
