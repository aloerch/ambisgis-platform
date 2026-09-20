from pathlib import Path
import hashlib, json, sys, xml.etree.ElementTree as ET
sys.path.insert(0, 'build-support/java')
from compatibility import verify_network_receipt
out = Path('/tmp/ambisgis-pr57-review-20260920')
e = json.loads(Path('plan/verification/java-compatibility.json').read_text())
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
checks=[]
for entry in e['runs']:
    p=Path(entry['receipt']); r=json.loads(p.read_text()); issues=[]
    for name in ('receipt', 'retained_receipt'):
        if sha(entry[name]) != entry['receipt_sha256']:
            issues.append(name+' digest mismatch')
    if r['result_exit_code'] != entry['result_exit_code']:
        issues.append('result mismatch')
    if entry.get('log') and sha(entry['log']['path']) != entry['log']['sha256']:
        issues.append('log digest mismatch')
    totals={k:0 for k in ('tests','errors','failures','skipped')}
    for native in entry['native_report_manifest'] or []:
        f=p.parent/'work/source'/native['path']
        if sha(f) != native['sha256']:
            issues.append('native XML digest mismatch: '+native['path'])
        suite=ET.parse(f).getroot()
        for key in totals:
            actual=int(suite.get(key,'0')); totals[key]+=actual
            if actual!=native[key]:
                issues.append('native XML count mismatch: '+native['path']+' '+key)
    if entry.get('native_tests'):
        for key in totals:
            if totals[key]!=entry['native_tests'][key]:
                issues.append('total mismatch '+key)
    passed=r['result_exit_code']==0
    row={'run':entry['run'],'result_exit_code':r['result_exit_code'],'receipt_and_retained_copy_verified':True,'native_reports_rechecked':len(entry['native_report_manifest'] or []),'native_totals':totals,'issues':issues}
    if passed and entry['target']:
        for key in ('error','finalization_error','shutdown_error'):
            if r.get(key):
                issues.append('successful result contains '+key)
        if r.get('changed_original_source_files')!=[]:
            issues.append('source hash verification absent or changed')
        if r.get('source_maven_files_unchanged') is not True:
            issues.append('Maven source verification absent or changed')
        verify_network_receipt(p.parent/'network-denial.json',r['exit_code'])
        row['original_source_check_completed']=True
        row['network_denial_rechecked']=True
        if entry['target']=='geofence':
            if r.get('postgres_cluster_stopped') is not True:
                issues.append('cluster stop absent')
            f=r['postgres_fixture']; db=json.loads(Path(f['database_report']).read_text())
            if db.get('cluster_stopped') is not True:
                issues.append('cluster readback absent')
            row['cluster_stop_readback']=db.get('cluster_stopped')
    if passed and entry['run'].startswith('logging-'):
        for case in [r['compile'], *r['cases']]:
            args=case['command']; evidence=Path(args[args.index('--evidence')+1])
            verify_network_receipt(evidence,case['exit_code'])
        row['network_denial_rechecked']=True
        if not all(c['passed'] for c in r['cases']):
            issues.append('logging witness case failed')
    checks.append(row)
report={'scope':'read-only historical receipt/log/native XML revalidation; no Maven/native component execution','runs':checks,'run_count':len(checks),'native_report_count':sum(x['native_reports_rechecked'] for x in checks),'successful_native_runs':[x['run'] for x in checks if x.get('original_source_check_completed')],'issues':[{'run':r['run'],'issues':r['issues']} for r in checks if r['issues']]}
(out/'compatibility-historical-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='runs'},indent=2))
assert not report['issues']
