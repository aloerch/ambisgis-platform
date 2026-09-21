#!/usr/bin/env python3
"""Narrow authorized checkpoint publication; complete readback, no importer."""
from pathlib import Path
import argparse, importlib.util, json, hashlib, subprocess

REPO=Path('/home/revelberry/Projects/AmbisGIS/ambisgis-platform-geoserver-auth')
BRANCH='fnd-02/geoserver-configured-auth'
BASE='b68e3d59bafb4bbf7b2007c76e5e59a25b4139e7'
ROOT=Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/geoserver-auth')

def git(*args):
 return subprocess.check_output(['git','-C',str(REPO),*args],text=True).strip()
def require(value,message):
 if not value: raise ValueError(message)
def save(path,value):
 with path.open('x') as f: f.write(json.dumps(value,indent=2,sort_keys=True)+'\n')

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--pr',type=int,required=True);ap.add_argument('--head',required=True)
 ap.add_argument('--output',type=Path,required=True);ap.add_argument('--apply',action='store_true')
 args=ap.parse_args();out=args.output.resolve()
 require(out.parent==ROOT and not out.exists(),'Fresh task-owned output required')
 require(git('rev-parse','--show-toplevel')==str(REPO),'Worktree mismatch')
 require(git('remote','get-url','origin')=='https://github.com/aloerch/ambisgis-platform.git','Remote mismatch')
 require(git('branch','--show-current')==BRANCH and git('rev-parse','HEAD')==args.head,'Local branch/head mismatch')
 git('merge-base','--is-ancestor',BASE,'HEAD')
 require(not git('status','--porcelain'),'Publication requires clean worktree')
 source=REPO/'plan/verification/java-http/project/snapshot.py'
 spec=importlib.util.spec_from_file_location('snapshot',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 require(m.sha(REPO/m.ADAPTER_PATH)==m.ADAPTER_SHA256,'Reviewed adapter changed')
 out.mkdir();(out/'publication.py').write_bytes(Path(__file__).read_bytes())
 m.REPO_ROOT=REPO;m.ROOT=out;m.GH=Path('/usr/bin/gh');m.api=m.AuditedAPI(runner=m.runner,read_only=True)
 before=m.snapshot(args.pr);save(out/'before.json',before);save(out/'before-pagination.json',m.api.connections)
 pr=before['content_details'].get('p'+str(args.pr))
 require(pr and pr['number']==args.pr and pr['state']=='OPEN' and pr['author']['login']=='aloerch','PR identity/state mismatch')
 require(pr['baseRefName']=='ambisgis/main' and pr['headRefName']==BRANCH and pr['headRefOid']==args.head,'Remote PR ref mismatch')
 require(pr['headRepository']=={'id':'R_kgDOUhI-dw','nameWithOwner':'aloerch/ambisgis-platform'},'PR repository mismatch')
 project=before['project'];items=project['items']
 existing=[x for x in items if x['content'].get('id')==pr['id']]
 require(len(existing)<=1,'Duplicate PR identities')
 fields=[x for x in project['fields'] if x['name']=='Evidence' and x['dataType']=='TEXT']
 require(len(fields)==1,'Ambiguous Evidence field')
 parent=[x for x in items if x['values'].get('Task ID')=='FND-02']
 require(len(parent)==1 and parent[0]['values'].get('Delivery')=='In progress' and parent[0]['content'].get('id')==before['content_details']['i3']['id'],'Parent identity/status mismatch')
 evidence=pr['url']+' | FND-02: https://github.com/aloerch/ambisgis-platform/issues/3'
 if existing:
  item=existing[0]
  require(not item['isArchived'],'Preserve archived PR decision; do not unarchive')
  require(not any(k in item['values'] for k in ('Task ID','Delivery','Review gate')),'PR has manually assigned planning fields; preserve them')
  require(not item['values'].get('Evidence') or item['values']['Evidence']==evidence,'Preserve existing manual Evidence')
 planned=[]
 if not existing: planned.append('add actual PR content ID')
 if not existing or existing[0]['values'].get('Evidence')!=evidence: planned.append('set new PR Evidence to PR and parent issue URLs')
 save(out/'plan.json',{'pr':pr,'mutations':planned,'apply':args.apply,'preserve_existing_items':True})
 actions=[];mutation_error=None;allowed_requests=[]
 def journal(event):
  with (out/'mutation-events.jsonl').open('a') as f:
   f.write(json.dumps(event,sort_keys=True)+'\n');f.flush()
 def publication_runner(arguments,**kwargs):
  if not kwargs.get('input'): return m.runner(arguments,**kwargs)
  request=json.loads(kwargs['input'])
  if request['query'].lstrip().startswith('query '): return m.runner(arguments,**kwargs)
  require(args.apply and arguments[0]=='gh' and request in allowed_requests,'Mutation not explicitly authorized by this checkpoint plan')
  journal({'phase':'requested','request':request})
  result=subprocess.run([str(m.GH),*arguments[1:]],**kwargs)
  status,_,body=m.parse_response(result.stdout)
  journal({'phase':'response','http_status':status,'response':body})
  return result
 def authorize(operation,input_type,payload,result_field,selection):
  query='mutation Apply($input:'+input_type+'!) { '+operation+'(input:$input) { '+result_field+' { '+selection+' } } }'
  allowed_requests.append({'query':query,'variables':{'input':payload}})
 if args.apply:
  m.api=m.AuditedAPI(runner=publication_runner,read_only=False)
  try:
   if not existing:
    authorize('addProjectV2ItemById','AddProjectV2ItemByIdInput',{'projectId':m.PROJECT,'contentId':pr['id']},'item','id isArchived')
    item=m.api.add_item(m.PROJECT,pr['id']);actions.append({'operation':'add_item','content_id':pr['id'],'result':item})
    save(out/'mutation-1-completed.json',actions[-1])
    require(not item['isArchived'],'New PR item unexpectedly archived')
   if not existing or existing[0]['values'].get('Evidence')!=evidence:
    authorize('updateProjectV2ItemFieldValue','UpdateProjectV2ItemFieldValueInput',{'projectId':m.PROJECT,'itemId':item['id'],'fieldId':fields[0]['id'],'value':{'text':evidence}},'projectV2Item','id')
    result=m.api.set_field(m.PROJECT,item['id'],fields[0],evidence)
    actions.append({'operation':'set_field','item_id':item['id'],'field_id':fields[0]['id'],'value':evidence,'result':result})
    save(out/'mutation-2-completed.json',actions[-1])
  except Exception as error:
   mutation_error={'type':type(error).__name__,'message':str(error)}
   save(out/'mutation-failure.json',{'error':mutation_error,'completed_actions':actions,'readback_will_be_attempted':True})
  save(out/'mutations.json',actions)
 m.api=m.AuditedAPI(runner=m.runner,read_only=True)
 after=m.snapshot(args.pr);save(out/'after.json',after)
 old={x['id']:x for x in items};new={x['id']:x for x in after['project']['items']}
 wanted=[x for x in new.values() if x['content'].get('id')==pr['id']]
 changed=[key for key in old if old[key]!=new.get(key)]
 if existing and actions and all(a['operation']=='set_field' for a in actions):
  allowed=existing[0]['id'];require(set(changed)<={allowed},'Unexpected prior item mutation')
  prior={k:v for k,v in old[allowed].items() if k not in ('values','field_values')}
  current={k:v for k,v in new[allowed].items() if k not in ('values','field_values')}
  require(prior==current and {k:v for k,v in old[allowed]['values'].items() if k!='Evidence'}=={k:v for k,v in new[allowed]['values'].items() if k!='Evidence'},'Prior planning changed')
  changed=[]
 expected_added=1 if args.apply and not existing else 0
 checks={
  'mutation_sequence_complete':not mutation_error,
  'all_prior_item_values_and_archive_decisions_preserved':not changed,
  'only_expected_new_item':len(set(new)-set(old))==expected_added and not(set(old)-set(new)),
  'all_project_fields_repositories_views_preserved':all(project.get(k)==after['project'].get(k) for k in project if k not in ('items','updatedAt')),
  'all_view_configuration_and_order_preserved':before['view_configurations']==after['view_configurations'],
  'pr_identity_unique':len(wanted)==int(bool(existing or args.apply)),
  'pr_has_no_parent_planning_fields':all(not any(k in x['values'] for k in ('Task ID','Delivery','Review gate')) for x in wanted),
  'live_pr_still_open_at_exact_head':all(after['content_details']['p'+str(args.pr)].get(k)==pr.get(k) for k in ('id','state','baseRefName','headRefName','headRefOid','headRepository')),
  'pr_item_unarchived':all(not x['isArchived'] for x in wanted),
  'pr_linked_if_applied':not args.apply or len(wanted)==1 and wanted[0]['values'].get('Evidence')==evidence,
  'all_readback_pagination_complete':all(x.get('complete') and x['pages'][-1]['hasNextPage'] is False for x in m.api.connections),
 }
 selection=[]
 for x in new.values():
  if x['content'].get('__typename')=='PullRequest':
   require(x['content']['repository']['nameWithOwner']=='aloerch/ambisgis-platform','Unexpected repo in queue audit')
   n=x['content']['number'];selection.append(f'p{n}:pullRequest(number:{n}) {{ id number state url }}')
 states=m.api._graphql('query { repository(owner:"aloerch",name:"ambisgis-platform") { '+' '.join(selection)+' } }')['repository']
 queue=sorted(x['content']['number'] for x in new.values() if not x['isArchived'] and x['content'].get('__typename')=='PullRequest' and states['p'+str(x['content']['number'])]['state']=='OPEN')
 checks['pr_is_in_saved_open_queue']=not (args.apply or existing) or args.pr in queue
 save(out/'pagination.json',m.api.connections)
 save(out/'outcome.json',{'checks':checks,'all_passed':all(checks.values()),'mutations':actions,'items_before':len(old),'items_after':len(new),'queue_filter':'is:pr is:open','queue_membership':queue,'pr_states':states,'local_head':args.head,'scope':'New PR membership/Evidence only; FND-02 unchanged; API readback, no UI claim','adapter_limit':'Inherited adapter does not expand assignee/label values; no such fields are written.'})
 save(out/'manifest.json',[{'path':p.name,'sha256':m.sha(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()])
 require(all(checks.values()),'Publication preservation check failed')
 print(json.dumps({'all_passed':True,'mutations':len(actions),'items_before':len(old),'items_after':len(new),'queue_membership':queue,'output':str(out)}))
if __name__=='__main__':main()
