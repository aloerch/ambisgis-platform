#!/usr/bin/env python3
"""Read-only publication snapshot; preserve complete Phase B Project baseline.

Uses the same read-only adapter and full-pagination query helpers as the initial
Phase B audit. The original audit and retained project-before remain unchanged.
No importer, add/update operation, correction, or permission escalation exists.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import subprocess
import sys

sys.dont_write_bytecode = True
REPO = 'aloerch/ambisgis-platform'
EXPECTED_ROOT = Path('/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-http')
EXPECTED_BRANCH = 'fnd-02/java-http-auth-compatibility'
PROJECT = 'PVT_kwHOAOk9es4Bj_k-'
QUEUE = 'PVTV_lAHOAOk9es4Bj_k-zgLu0DU'
ADAPTER_PATH = 'plan/tools/github_project_api.py'
ADAPTER_SHA256 = '2285d2ba5eb367df7f8e641399011bed237d60febb8dc1393f96d653f197cfd9'
BASE_PATH = Path('/home/revelberry/Projects/AmbisGIS/source-archives/java-http-auth/project-before/readback.json')
BASE_SHA256 = 'dd75e6b79f60a333230313babaf66fcb3ca4377339ca8b84c4cf7cb79852c9e3'
INTEGRATION_COMMIT = 'a9ec191658be027b40118fd35e145729202fe55d'
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'plan/tools'))
from github_project_api import GitHubProjectAPI, parse_response, PAGE_INFO
FIELD = '... on ProjectV2FieldCommon { id name dataType }'
FCON = 'nodes { ' + FIELD + ' } ' + PAGE_INFO
SCON = 'nodes { direction field { ' + FIELD + ' } } ' + PAGE_INFO


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments):
    return subprocess.run(['git', '-C', str(REPO_ROOT), *arguments],
                          capture_output=True, check=True, text=True).stdout.strip()


def save(name, value):
    with (ROOT / name).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def runner(arguments, **kwargs):
    require(arguments[0] == 'gh', 'Unexpected transport executable')
    if kwargs.get('input'):
        request = json.loads(kwargs['input'])
        require(re.match(r'^query\b', request['query'].lstrip()) is not None,
                'Read-only snapshot refuses mutations')
    else:
        require(arguments[arguments.index('--method') + 1] == 'GET',
                'Read-only snapshot refuses non-GET REST requests')
        request = arguments[-1]
    result = subprocess.run([str(GH), *arguments[1:]], **kwargs)
    status, _, body = parse_response(result.stdout)
    event = {'at': datetime.now(timezone.utc).isoformat(), 'request': request,
             'http_status': status, 'response': body}
    with (ROOT / 'readback-requests.jsonl').open('a') as stream:
        stream.write(json.dumps(event) + '\n')
    return result


class AuditedAPI(GitHubProjectAPI):
 def __init__(self, **kwargs):
  super().__init__(**kwargs);self.connections=[];self.connection_stack=[]
 def _graphql(self,query,variables=None,**kwargs):
  result=super()._graphql(query,variables,**kwargs)
  if self.connection_stack:
   entry=self.connection_stack[-1];value=result
   for part in entry['path']:value=value[part]
   entry['pages'].append({'after':(variables or {}).get('after'),'node_count':len(value['nodes']),**value['pageInfo']})
  return result
 def _connection(self,query,variables,path,*,initial=None):
  entry={'path':list(path),'variables':variables,'pages':[]}
  if initial is not None:entry['pages'].append({'initial_nested_page':True,'node_count':len(initial['nodes']),**initial['pageInfo']})
  self.connection_stack.append(entry)
  try:
   result=super()._connection(query,variables,path,initial=initial)
   entry.update(node_count=len(result),complete=True)
   require(entry['pages'] and entry['pages'][-1]['hasNextPage'] is False, 'Incomplete connection pagination')
   return result
  finally:
   self.connection_stack.pop();self.connections.append(entry)
def identity():
 u=api.identity();r=api.repository(REPO)
 require((u['login'],u['id'],u['node_id'])==('aloerch',15285626,'MDQ6VXNlcjE1Mjg1NjI2'), 'Authenticated owner identity mismatch')
 require((r['id'],r['node_id'],r['full_name'])==(1376927351,'R_kgDOUhI-dw',REPO), 'Repository identity mismatch')
 return {'login':u['login'],'id':u['id'],'node_id':u['node_id']},{k:r[k] for k in ('id','node_id','full_name')}
def views():
 sel='id number name layout filter updatedAt fields(first:100) { '+FCON+' } configuration { visibleFields(first:100) { '+FCON+' } } groupByFields(first:100) { '+FCON+' } verticalGroupByFields(first:100) { '+FCON+' } sortByFields(first:100) { '+SCON+' }'
 q='query Views($id:ID!,$after:String) { node(id:$id) { ... on ProjectV2 { views(first:100,after:$after) { nodes { '+sel+' } '+PAGE_INFO+' } } } }'
 out=api._connection(q,{'id':PROJECT},('node','views'))
 for v in out:
  for name in ('fields','groupByFields','verticalGroupByFields','sortByFields','visibleFields'):
   container=v['configuration'] if name=='visibleFields' else v
   selection=SCON if name=='sortByFields' else FCON
   nested=name+'(first:100,after:$after) { '+selection+' }'
   path=('node','configuration',name) if name=='visibleFields' else ('node',name)
   if name=='visibleFields': nested='configuration { '+nested+' }'
   q='query ViewFields($id:ID!,$after:String) { node(id:$id) { ... on ProjectV2View { '+nested+' } } }'
   container[name]=api._connection(q,{'id':v['id']},path,initial=container[name])
 return out

def snapshot(expected_pr_number=None):
    user, repository = identity()
    project = api.project(PROJECT)
    require(project['number'] == 2 and project['owner']['login'] == 'aloerch'
            and project['owner']['id'] == user['node_id'] and project['public']
            and not project['closed'], 'Project identity/visibility mismatch')
    selections = []
    numbers = sorted({54, 55, 56, 57} | ({expected_pr_number} if expected_pr_number else set()))
    for number in numbers:
        selections.append('p%d:pullRequest(number:%d) { id number url state isDraft mergedAt mergedBy { login } mergeCommit { oid } headRefName headRefOid baseRefName author { login } headRepository { id nameWithOwner } }' % (number, number))
    for number in (3, 9):
        selections.append('i%d:issue(number:%d) { id number url title body state }' % (number, number))
    query = 'query { repository(owner:"aloerch",name:"ambisgis-platform") { id databaseId nameWithOwner ' + ' '.join(selections) + ' } }'
    details = api._graphql(query)['repository']
    require(details['id'] == repository['node_id'] and details['databaseId'] == repository['id'],
            'Content repository identity mismatch')
    for number, task in ((3, 'FND-02'), (9, 'GOV-02')):
        issue = details['i' + str(number)]
        require(issue['number'] == number and '<!-- ambisgis:task:' + task + ' -->' in issue['body'],
                'Parent issue marker mismatch')
    configurations = views()
    queue = [view for view in configurations if view['id'] == QUEUE]
    require(len(queue) == 1 and queue[0]['filter'] == 'is:pr is:open', 'Saved PR queue changed')
    return {'captured_at': datetime.now(timezone.utc).isoformat(), 'identity': user,
            'repository': repository, 'project': project, 'view_configurations': configurations,
            'content_details': details}


def compare(prior, current, expected_pr_number=None, local_head=None):
    old = {item['id']: item for item in prior['project']['items']}
    new = {item['id']: item for item in current['project']['items']}
    added = [new[key] for key in sorted(set(new) - set(old))]
    removed = [old[key] for key in sorted(set(old) - set(new))]
    changed = [{'item_id': key, 'before': old[key], 'after': new[key]}
               for key in sorted(set(old) & set(new)) if old[key] != new[key]]
    tasks = [item for item in new.values() if item['values'].get('Task ID')]
    prs = [item for item in new.values() if item['content'].get('__typename') == 'PullRequest']
    wanted = current['content_details'].get('p' + str(expected_pr_number)) if expected_pr_number else None
    wanted_items = [item for item in added if wanted and item['content'].get('id') == wanted['id']]
    parent_url = 'https://github.com/' + REPO + '/issues/3'
    checks = {
        'all_prior_items_preserved': not removed and not changed,
        'prior_archive_decisions_preserved': all(key in new and old[key]['isArchived'] == new[key]['isArchived'] for key in old),
        '66_unique_task_ids': len(tasks) == len({item['values']['Task ID'] for item in tasks}) == 66,
        'all_task_fields_preserved': all(old.get(item['id']) == item for item in tasks),
        'project_identity_and_configuration_preserved': all(prior['project'].get(key) == current['project'].get(key)
            for key in ('id', 'number', 'url', 'title', 'public', 'closed', 'shortDescription', 'readme', 'owner', 'fields', 'repositories', 'views')),
        'all_view_configuration_and_human_order_preserved': prior['view_configurations'] == current['view_configurations'],
        'fnd02_in_progress_gov02_merged': {item['values']['Task ID']: item['values'].get('Delivery') for item in tasks
            if item['values']['Task ID'] in ('FND-02', 'GOV-02')} == {'FND-02': 'In progress', 'GOV-02': 'Merged'},
        'no_parent_acceptance_fields_on_pr_items': all(not any(key in item['values'] for key in ('Task ID', 'Delivery', 'Review gate')) for item in prs),
        'unique_item_and_pr_content_ids': len(new) == len(current['project']['items']) and len(prs) == len({item['content']['id'] for item in prs}),
        'expected_total_and_pr_counts': len(new) == 70 + bool(expected_pr_number) and len(prs) == 4 + bool(expected_pr_number),
        'only_expected_new_item': len(added) == bool(expected_pr_number) and (not expected_pr_number or len(wanted_items) == 1),
    }
    if expected_pr_number:
        checks['expected_pr_identity'] = bool(wanted and wanted['number'] == expected_pr_number
            and wanted['state'] == 'OPEN' and wanted['author']['login'] == 'aloerch'
            and wanted['baseRefName'] == 'ambisgis/main' and wanted['headRefName'] == EXPECTED_BRANCH
            and wanted['headRepository'] == {'id': 'R_kgDOUhI-dw', 'nameWithOwner': REPO}
            and wanted['headRefOid'] == local_head)
        checks['expected_pr_item_unarchived_and_parent_linked'] = len(wanted_items) == 1 and not wanted_items[0]['isArchived'] and bool(wanted and wanted['url'] in wanted_items[0]['values'].get('Evidence', '') and parent_url in wanted_items[0]['values'].get('Evidence', ''))
    return {'checks': checks, 'added_items': added, 'removed_items': removed,
            'changed_prior_items': changed, 'expected_pr': wanted,
            'task_count': len(tasks), 'pr_item_count': len(prs), 'total_items': len(new),
            'archived_item_count': sum(item['isArchived'] for item in new.values()),
            'queue_membership': sorted(item['content']['number'] for item in prs if not item['isArchived']
                and current['content_details'].get('p' + str(item['content']['number']), {}).get('state') == 'OPEN')}


def main():
    global ROOT, REPO_ROOT, GH, api
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--gh', type=Path, required=True)
    parser.add_argument('--ghhash', '--gh-sha256', required=True, help='Explicit reviewed SHA-256 of gh executable')
    parser.add_argument('--output', type=Path, required=True, help='Fresh retained directory outside Git')
    parser.add_argument('--expected-pr-number', type=int)
    args = parser.parse_args()
    REPO_ROOT, GH, ROOT = args.repository.resolve(), args.gh.resolve(), args.output.resolve()
    require(REPO_ROOT == EXPECTED_ROOT.resolve(), 'Unexpected worktree directory')
    require(re.fullmatch(r'[0-9a-f]{64}', args.ghhash) is not None and sha(GH) == args.ghhash, 'GitHub CLI hash mismatch')
    require(sha(REPO_ROOT / ADAPTER_PATH) == ADAPTER_SHA256, 'Read-only adapter hash mismatch')
    require(sha(BASE_PATH) == BASE_SHA256, 'Retained Phase B baseline changed')
    require(not ROOT.exists() and not ROOT.is_relative_to(REPO_ROOT), 'Output must be fresh and outside worktree')
    require(ROOT.is_relative_to(BASE_PATH.parent.parent), 'Output must remain in the authorized Phase B source archive')
    existing = ROOT.parent
    while not existing.exists():
        existing = existing.parent
    git_probe = subprocess.run(['git', '-C', str(existing), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    require(git_probe.returncode != 0, 'Raw output must be outside every Git worktree')
    require(git('rev-parse', '--show-toplevel') == str(REPO_ROOT), 'Worktree root mismatch')
    require(git('remote', 'get-url', 'origin') in ('https://github.com/aloerch/ambisgis-platform.git', 'git@github.com:aloerch/ambisgis-platform.git'), 'Origin mismatch')
    require(git('branch', '--show-current') == EXPECTED_BRANCH, 'Worktree branch mismatch')
    git('merge-base', '--is-ancestor', INTEGRATION_COMMIT, 'HEAD')
    head = git('rev-parse', 'HEAD')
    require(args.expected_pr_number is None or (args.expected_pr_number > 0 and args.expected_pr_number not in (54, 55, 56, 57)), 'Expected PR must be a new positive number')
    prior = json.loads(BASE_PATH.read_bytes())
    ROOT.mkdir(parents=True, exist_ok=False)
    (ROOT / 'snapshot.py').write_bytes(Path(__file__).read_bytes())
    api = AuditedAPI(runner=runner, read_only=True)
    data = snapshot(args.expected_pr_number)
    save('readback.json', data)
    save('pagination.json', api.connections)
    outcome = compare(prior, data, args.expected_pr_number, head)
    outcome['checks']['all_pagination_complete'] = bool(api.connections) and all(
        connection.get('complete') and connection['pages'][-1]['hasNextPage'] is False for connection in api.connections)
    outcome.update(captured_at=data['captured_at'], read_only=True, mutation_count=0,
        all_checks_passed=all(outcome['checks'].values()),
        baseline={'path': str(BASE_PATH), 'sha256': BASE_SHA256},
        local={'repository': str(REPO_ROOT), 'branch': EXPECTED_BRANCH, 'head': head},
        gh_sha256=args.ghhash, adapter_sha256=ADAPTER_SHA256,
        queue_filter='is:pr is:open',
        queue_membership_method='Fully paginated API content plus live PR state and saved filter; not browser inspection',
        pagination={'connections': len(api.connections), 'pages': sum(len(entry['pages']) for entry in api.connections),
                    'archive_query': 'archivedStates:[ARCHIVED,NOT_ARCHIVED]'},
        limitations=['Inherited adapter does not expand assignee/label values.',
                     'Comparison never writes or resets human planning changes.',
                     'Human view ordering is compared to the reconciled project-before, not the older PR56 preparation.'])
    save('outcome.json', outcome)
    save('manifest.json', [{'path': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path)}
                          for path in sorted(ROOT.iterdir()) if path.is_file()])
    print(json.dumps({'all_checks_passed': outcome['all_checks_passed'],
        'failed_checks': [key for key, passed in outcome['checks'].items() if not passed],
        'queue_membership': outcome['queue_membership'], 'expected_pr_number': args.expected_pr_number,
        'evidence_directory': str(ROOT)}, indent=2))
    return 0 if outcome['all_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
