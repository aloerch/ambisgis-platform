from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,subprocess,sys
sys.dont_write_bytecode=True
sys.path.insert(0,'/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-closure/plan/tools')
from github_project_api import GitHubProjectAPI,parse_response,PAGE_INFO
ROOT=Path(__file__).resolve().parent
GH=Path('/tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh')
PROJECT='PVT_kwHOAOk9es4Bj_k-'
REPO='aloerch/ambisgis-platform'
QUEUE='PVTV_lAHOAOk9es4Bj_k-zgLu0DU'
FIELD='... on ProjectV2FieldCommon { id name dataType }'
FCON='nodes { '+FIELD+' } '+PAGE_INFO
SCON='nodes { direction field { '+FIELD+' } } '+PAGE_INFO
mode='readback'
assert not (ROOT/'readback.json').exists(), 'Refuse overwriting prior readback'
assert not (ROOT/'readback-requests.jsonl').exists(), 'Refuse overwriting request evidence'
assert hashlib.sha256(GH.read_bytes()).hexdigest()=='ea857a3f0f7d4276cf5848b236542c5048e2eaa7bdd1b6ddec238f8793e74bff'
log=ROOT/(mode+'-requests.jsonl')
def save(name,obj):
 (ROOT/name).write_text(json.dumps(obj,indent=2)+'\n')
def runner(args,**kwargs):
 assert args[0]=='gh'
 if kwargs.get('input'):
  assert json.loads(kwargs['input'])['query'].lstrip().startswith('query'), 'Read-only audit refuses mutations'
 else:
  assert args[args.index('--method')+1]=='GET'
 result=subprocess.run([str(GH),*args[1:]],**kwargs)
 try:
  status,_,body=parse_response(result.stdout)
  event={'at':datetime.now(timezone.utc).isoformat(),'request':json.loads(kwargs['input']) if kwargs.get('input') else args[-1], 'http_status':status,'response':body}
  with log.open('a') as f:f.write(json.dumps(event)+'\n')
 except Exception: pass
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
   assert entry['pages'] and entry['pages'][-1]['hasNextPage'] is False
   return result
  finally:
   self.connection_stack.pop();self.connections.append(entry)
api=AuditedAPI(runner=runner)
def identity():
 u=api.identity();r=api.repository(REPO)
 assert (u['login'],u['id'],u['node_id'])==('aloerch',15285626,'MDQ6VXNlcjE1Mjg1NjI2')
 assert (r['id'],r['node_id'],r['full_name'])==(1376927351,'R_kgDOUhI-dw',REPO)
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
def snapshot():
 u,r=identity();p=api.project(PROJECT)
 assert p['number']==2 and p['owner']['login']=='aloerch' and p['public'] and not p['closed'] and p['viewerCanUpdate']
 details=api._graphql('query { repository(owner:"aloerch",name:"ambisgis-platform") { id databaseId nameWithOwner p54:pullRequest(number:54) { id number url state mergedAt mergedBy { login } mergeCommit { oid } headRefOid baseRefName } p55:pullRequest(number:55) { id number url state mergedAt mergedBy { login } mergeCommit { oid } headRefOid baseRefName } p56:pullRequest(number:56) { id number url state mergedAt mergedBy { login } mergeCommit { oid } headRefOid baseRefName } p57:pullRequest(number:57) { id number url state mergedAt mergedBy { login } mergeCommit { oid } headRefOid baseRefName } i3:issue(number:3) { id number url title body state } i9:issue(number:9) { id number url title body state } } }')['repository']
 assert details['id']==r['node_id'] and details['databaseId']==r['id']
 for n,task in [(3,'FND-02'),(9,'GOV-02')]:
  issue=details['i'+str(n)];assert issue['number']==n and '<!-- ambisgis:task:'+task+' -->' in issue['body']
 v=views(); queue=[x for x in v if x['id']==QUEUE];assert len(queue)==1 and queue[0]['filter']=='is:pr is:open'
 ids=[x['values']['Task ID'] for x in p['items'] if x['values'].get('Task ID')]
 assert len(ids)==len(set(ids))==66
 return {'captured_at':datetime.now(timezone.utc).isoformat(),'identity':u,'repository':r,'project':p,'view_configurations':v,'content_details':details}


BASE_REPO=Path('/home/revelberry/Projects/AmbisGIS/ambisgis-platform-java-closure')
BASE_COMMIT='8bf1217c8c078c26558da4b3318feda07a9c4ce1'
BASE_PATH='plan/verification/pr57-review/project/readback.json'
BASE_SHA256='5893ca7e32130960bea596af73260ee505efc54fcfa0dd035b453a5d1c09231e'
ADAPTER_PATH='plan/tools/github_project_api.py'
ADAPTER_SHA256='2285d2ba5eb367df7f8e641399011bed237d60febb8dc1393f96d653f197cfd9'
assert hashlib.sha256((BASE_REPO/ADAPTER_PATH).read_bytes()).hexdigest()==ADAPTER_SHA256
prior_bytes=subprocess.run(['git','-C',str(BASE_REPO),'show',BASE_COMMIT+':'+BASE_PATH],capture_output=True,check=True).stdout
assert hashlib.sha256(prior_bytes).hexdigest()==BASE_SHA256
prior=json.loads(prior_bytes)
data=snapshot();save('readback.json',data);save('pagination.json',api.connections)
old={x['id']:x for x in prior['project']['items']};new={x['id']:x for x in data['project']['items']}
tasks=[x for x in new.values() if x['values'].get('Task ID')]
prs=[]
for x in new.values():
 if x['content'].get('__typename')=='PullRequest':
  details=data['content_details']['p'+str(x['content']['number'])]
  prs.append({'number':details['number'],'content_id':details['id'],'item_id':x['id'],'state':details['state'],'archived':x['isArchived'],'values':x['values'],'pr_details':details})
expected_parents={54:3,55:3,56:9,57:3}
checks={
 '66_unique_tasks':len(tasks)==len({x['values']['Task ID'] for x in tasks})==66,
 'four_unique_pr_contents':len(prs)==len({x['content_id'] for x in prs})==4,
 'total_items_70':len(new)==70,
 'all_item_identities_unchanged':set(new)==set(old),
 'all_archive_decisions_unchanged':all(k in new and old[k]['isArchived']==new[k]['isArchived'] for k in old),
 'all_task_fields_unchanged':all(old.get(x['id'])==x for x in tasks),
 'views_fields_repository_links_unchanged':all(prior['project'][k]==data['project'][k] for k in ('fields','repositories','views')) and prior['view_configurations']==data['view_configurations'],
 'no_parent_acceptance_on_pr_items':all(not any(k in x['values'] for k in ('Task ID','Delivery','Review gate')) for x in prs),
 'parent_evidence_unchanged':all(data['content_details']['i'+str(expected_parents[x['number']])]['url'] in x['values']['Evidence'] and old[x['item_id']]['values']['Evidence']==x['values']['Evidence'] for x in prs),
 'all_pagination_complete':all(c.get('complete') and c['pages'][-1]['hasNextPage'] is False for c in api.connections),
 'fnd02_in_progress_gov02_merged':{x['values']['Task ID']:x['values']['Delivery'] for x in tasks if x['values']['Task ID'] in ('FND-02','GOV-02')}=={'FND-02':'In progress','GOV-02':'Merged'},
 'pr57_owner_merged_at_verified_commit':data['content_details']['p57']['state']=='MERGED' and data['content_details']['p57']['mergedBy']['login']=='aloerch' and data['content_details']['p57']['mergeCommit']['oid']==BASE_COMMIT,
 'pr56_open_at_expected_head':data['content_details']['p56']['state']=='OPEN' and data['content_details']['p56']['headRefOid']=='28c9d79757b98bdedd44b5d7486835f9e4b71e63',
}
changes=[]
for item_id in sorted(set(old)|set(new)):
 before=old.get(item_id);after=new.get(item_id)
 if before!=after:
  changes.append({'item_id':item_id,'content':(after or before)['content'],'changed_keys':[k for k in sorted(set(before or {})|set(after or {})) if (before or {}).get(k)!=(after or {}).get(k)],'old_values':before['values'] if before else None,'new_values':after['values'] if after else None,'old_archive':before['isArchived'] if before else None,'new_archive':after['isArchived'] if after else None})
summary={
 'captured_at':data['captured_at'],'read_only':True,'mutation_count':0,
 'immutable_baseline':{'commit':BASE_COMMIT,'path':BASE_PATH,'sha256':BASE_SHA256,'captured_at':prior['captured_at'],'copied_to_audit':False},
 'adapter':{'commit':BASE_COMMIT,'path':ADAPTER_PATH,'sha256':ADAPTER_SHA256},
 'checks':checks,'all_checks_passed':all(checks.values()),
 'task_count':len(tasks),'pr_item_count':len(prs),'total_items':len(new),'archived_item_count':sum(x['isArchived'] for x in new.values()),
 'field_count':len(data['project']['fields']),'view_count':len(data['view_configurations']),'repository_link_count':len(data['project']['repositories']),
 'queue_filter':'is:pr is:open','queue_membership':sorted(x['number'] for x in prs if x['state']=='OPEN' and not x['archived']),
 'queue_membership_method':'Fully paginated Project content plus live PR state and saved filter; not browser inspection',
 'pr_items':prs,'item_changes_from_pr57':changes,
 'delivery':{x['values']['Task ID']:x['values']['Delivery'] for x in tasks if x['values']['Task ID'] in ('FND-02','GOV-02')},
 'pagination':{'connections':len(api.connections),'pages':sum(len(c['pages']) for c in api.connections),'terminal_connections':sum(c['pages'][-1]['hasNextPage'] is False for c in api.connections),'archive_query':'archivedStates:[ARCHIVED,NOT_ARCHIVED]'},
}
save('outcome.json',summary)
print(json.dumps(summary,indent=2))
if not summary['all_checks_passed']:sys.exit(1)
