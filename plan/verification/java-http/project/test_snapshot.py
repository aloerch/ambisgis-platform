"""Offline comparator/transport regression tests; no GitHub requests."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publication_snapshot', Path(__file__).with_name('snapshot.py'))
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.prior = json.loads(snapshot.BASE_PATH.read_bytes())
        self.current = deepcopy(self.prior)

    def add_pr(self):
        self.current['content_details']['p58'] = {
            'id': 'PR_owned_new', 'number': 58, 'state': 'OPEN', 'author': {'login': 'aloerch'},
            'baseRefName': 'ambisgis/main', 'headRefName': snapshot.EXPECTED_BRANCH,
            'headRepository': {'id': 'R_kgDOUhI-dw', 'nameWithOwner': snapshot.REPO},
            'headRefOid': 'a' * 40, 'url': 'https://github.com/aloerch/ambisgis-platform/pull/58'}
        item = {'id': 'ITEM_owned_new', 'isArchived': False,
                'content': {'id': 'PR_owned_new', '__typename': 'PullRequest', 'number': 58},
                'values': {'Title': 'new incremental review', 'Status': 'Todo',
                           'Evidence': 'https://github.com/aloerch/ambisgis-platform/pull/58 ; parent task https://github.com/aloerch/ambisgis-platform/issues/3'}}
        self.current['project']['items'].append(item)
        return item

    def test_reconciled_baseline_preserves_human_view_order(self):
        result = snapshot.compare(self.prior, self.current)
        self.assertTrue(all(result['checks'].values()))
        self.assertEqual(result['queue_membership'], [])
        self.assertEqual(result['total_items'], 70)

    def test_only_new_linked_pr_is_allowed(self):
        self.add_pr()
        result = snapshot.compare(self.prior, self.current, 58, 'a' * 40)
        self.assertTrue(all(result['checks'].values()))
        self.assertEqual(result['queue_membership'], [58])
        self.assertEqual(result['total_items'], 71)
        self.assertEqual(result['changed_prior_items'], [])

    def test_parent_acceptance_cannot_be_copied_to_pr(self):
        item = self.add_pr()
        item['values']['Delivery'] = 'Verified'
        result = snapshot.compare(self.prior, self.current, 58, 'a' * 40)
        self.assertFalse(result['checks']['no_parent_acceptance_fields_on_pr_items'])

    def test_existing_task_change_is_reported_without_correction(self):
        task = next(item for item in self.current['project']['items'] if item['values'].get('Task ID') == 'FND-02')
        task['values']['Delivery'] = 'Verified'
        before = deepcopy(self.current)
        result = snapshot.compare(self.prior, self.current)
        self.assertFalse(result['checks']['all_task_fields_preserved'])
        self.assertFalse(result['checks']['all_prior_items_preserved'])
        self.assertEqual(len(result['changed_prior_items']), 1)
        self.assertEqual(self.current, before)

    def test_view_reorder_is_reported_without_reset(self):
        view = next(view for view in self.current['view_configurations'] if view['number'] == 2)
        view['configuration']['visibleFields'].reverse()
        result = snapshot.compare(self.prior, self.current)
        self.assertFalse(result['checks']['all_view_configuration_and_human_order_preserved'])

    def test_other_head_is_not_the_expected_review(self):
        self.add_pr()
        result = snapshot.compare(self.prior, self.current, 58, 'b' * 40)
        self.assertFalse(result['checks']['expected_pr_identity'])

    def test_transport_refuses_mutations_before_subprocess(self):
        with patch.object(snapshot.subprocess, 'run') as execute:
            with self.assertRaisesRegex(ValueError, 'refuses mutations'):
                snapshot.runner(['gh', 'api', '--method', 'POST', 'graphql'], input=json.dumps({'query': 'mutation { createProjectV2 }'}))
            with self.assertRaisesRegex(ValueError, 'non-GET'):
                snapshot.runner(['gh', 'api', '--method', 'PATCH', 'repos/aloerch/ambisgis-platform/issues/3'])
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
