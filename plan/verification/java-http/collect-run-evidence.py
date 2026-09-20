#!/usr/bin/env python3
"""Summarize retained runs without overwriting their actual evidence."""
import argparse, hashlib, json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--runs',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
rows=[]
for receipt in sorted(a.runs.glob('*/result.json')):
    data=json.loads(receipt.read_text())
    row={'run':receipt.parent.name,'receipt':str(receipt.resolve()),'receipt_sha256':digest(receipt)}
    for key in ('status','started_at','result_exit_code','exit_code','build_exit_code','target','stage','test_selection','runner_sha256','source_manifest_sha256','input_manifest_sha256','log_sha256','build_log_sha256','error','finalization_error','source_maven_files_unchanged','changed_original_source_files','retained_tooling_unchanged','target_executed_tests','acceptance_build','full_source_closure','http_fixture_finalization'):
        if key in data: row[key]=data[key]
    native=data.get('native_tests')
    if native:
        row['native_tests']={k:v for k,v in native.items() if k!='suites'}
        row['native_tests']['suite_reports']=len(native.get('suites',[]))
        row['nonpassing_suites']=[s for s in native.get('suites',[]) if s['failures'] or s['errors'] or s['skipped']]
    network=data.get('runtime_network_verified')
    if network:
        row['runtime_network']={k:network[k] for k in ('runner_sha256','network_probes','datagram_packets_received','broker_sockets_closed','task_process_group_stopped','result_exit_code')}
    row['evidence_files']=[{'name':f.name,'sha256':digest(f),'size':f.stat().st_size} for f in sorted(receipt.parent.iterdir()) if f.is_file() and f.suffix in ('.json','.log','.jsonl','.txt')]
    rows.append(row)
with a.output.open('x') as stream:
    json.dump({'schema_version':1,'purpose':'retained observed run index; no acceptance claim','runs':rows},stream,indent=2)
    stream.write('\n')
print(json.dumps({'runs':len(rows),'output':str(a.output),'sha256':digest(a.output)}))
