from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,subprocess,sys
sys.dont_write_bytecode=True
sys.path.insert(0,'/home/revelberry/Projects/AmbisGIS/ambisgis-platform-pr-review/plan/tools')
from github_project_api import GitHubProjectAPI,parse_response,PAGE_INFO
ROOT=Path('/tmp/ambisgis-pr57-review-20260920/project')
GH=Path('/tmp/ambisgis-gh-067dpbju/gh_2.101.0_linux_amd64/bin/gh')
PROJECT='PVT_kwHOAOk9es4Bj_k-'
REPO='aloerch/ambisgis-platform'
QUEUE='PVTV_lAHOAOk9es4Bj_k-zgLu0DU'
FIELD='... on ProjectV2FieldCommon { id name dataType }'
FCON='nodes { '+FIELD+' } '+PAGE_INFO
SCON='nodes { direction field { '+FIELD+' } } '+PAGE_INFO
mode='readback'
ROOT.mkdir(exist_ok=False)
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
api=GitHubProjectAPI(runner=runner)
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

data=snapshot();save('readback.json',data)
prior_bytes=subprocess.run(['git','show','origin/ambisgis/main:plan/verification/pr55-review/project/after.json'],capture_output=True,check=True).stdout
(ROOT/'prior-pr55-after.json').write_bytes(prior_bytes)
prior=json.loads(prior_bytes)
old={x['id']:x for x in prior['project']['items']};new={x['id']:x for x in data['project']['items']}
changed=[]
for item_id,x in old.items():
 y=new.get(item_id)
 if y!=x:
  changed.append({'item_id':item_id,'content':x['content'],'old_values':x['values'],'new_values':y['values'] if y else None,'old_archive':x['isArchived'],'new_archive':y['isArchived'] if y else None,'old_raw_values':x['field_values'],'new_raw_values':y['field_values'] if y else None})
tasks=[x for x in new.values() if x['values'].get('Task ID')]
prs=[]
for x in new.values():
 if x['content'].get('__typename')=='PullRequest':
  details=data['content_details']['p'+str(x['content']['number'])]
  prs.append({'number':details['number'],'content_id':details['id'],'item_id':x['id'],'state':details['state'],'archived':x['isArchived'],'values':x['values'],'pr_details':details})
expected_parents={54:3,55:3,56:9,57:3}
for x in prs:
 assert not any(k in x['values'] for k in ('Task ID','Delivery','Review gate'))
 assert data['content_details']['i'+str(expected_parents[x['number']])]['url'] in x['values']['Evidence']
 assert old[x['item_id']]['values']['Evidence']==x['values']['Evidence']
assert len(tasks)==66 and len(prs)==4 and len(new)==70
assert all(old[x['id']]==x for x in tasks)
assert set(new)==set(old)
assert all(old[k]['isArchived']==new[k]['isArchived'] for k in old)
assert prior['view_configurations']==data['view_configurations']
assert all(prior['project'][k]==data['project'][k] for k in ('fields','repositories','views'))
summary={'captured_at':data['captured_at'],'read_only':True,'mutation_count':0,'task_count':len(tasks),'distinct_task_ids':len({x['values']['Task ID'] for x in tasks}),'pr_item_count':len(prs),'total_items':len(new),'archived_item_count':sum(x['isArchived'] for x in new.values()),'queue_filter':'is:pr is:open','queue_membership':sorted(x['number'] for x in prs if x['state']=='OPEN' and not x['archived']),'queue_membership_method':'Fully paginated Project content plus live PR state and saved filter; not browser inspection','pr_items':prs,'task_fields_unchanged_from_pr55':True,'all_item_identities_archive_states_and_parent_evidence_unchanged':True,'views_fields_repository_links_unchanged':True,'field_count':len(data['project']['fields']),'view_count':len(data['view_configurations']),'repository_link_count':len(data['project']['repositories']),'item_changes_from_pr55':changed,'delivery':{x['values']['Task ID']:x['values']['Delivery'] for x in tasks if x['values']['Task ID'] in ('FND-02','GOV-02')},'prior_receipt_source':'origin/ambisgis/main:plan/verification/pr55-review/project/after.json','prior_receipt_sha256':hashlib.sha256(prior_bytes).hexdigest()}
save('outcome.json',summary)
print(json.dumps(summary,indent=2))
