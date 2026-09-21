#!/usr/bin/env python3
"""Read-only FND-02 inventory integrity; never grants rights or owner acceptance.

Exit 0: requested inventory/report operation succeeded (blockers may remain).
Exit 1: syntax/schema/reference/integrity/unavailable-input failure.
Exit 2: --eligibility requested and selection/acceptance gates remain open.
No downloads, hooks, archive extraction, builds, repository or Project writes.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import subprocess
import zipfile

sys.dont_write_bytecode = True
PLATFORM = Path(__file__).resolve().parents[2]
SCHEMA = PLATFORM / 'plan/contracts/fnd-02-candidate.schema.json'
MANIFEST = PLATFORM / 'plan/candidates/fnd-02-candidate.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-JSON number: '+x)))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(value):
    require(isinstance(value, str) and value and '\\' not in value and '\x00' not in value,
            'Unsafe or empty relative path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')),
            'Unsafe relative path: ' + value)
    return path


def resolve(location, mappings):
    require(location['root'] in mappings, 'Unavailable workspace mapping: '+location['root'])
    base = mappings[location['root']].resolve(strict=True)
    path = base / relative(location['path'])
    require(path.resolve(strict=True).is_relative_to(base), 'Path escapes mapped root: '+str(path))
    return path


def pointer(document, value):
    require(value == '' or value.startswith('/'), 'Invalid JSON pointer: '+value)
    for part in value.split('/')[1:]:
        require(not re.search(r'~(?![01])', part), 'Invalid JSON pointer escape')
        key = part.replace('~1','/').replace('~0','~')
        if isinstance(document, list):
            require(bool(re.fullmatch(r'0|[1-9][0-9]*',key)), 'Invalid array index')
            document = document[int(key)]
        else:
            document = document[key]
    return document


def index(rows, name):
    result = {}
    for row in rows:
        require(row['id'] not in result, 'Duplicate '+name+' identity: '+row['id'])
        result[row['id']] = row
    return result


def refs(values, target, label, nonempty=True):
    require(not nonempty or bool(values), 'Missing references: '+label)
    require(len(values) == len(set(values)), 'Duplicate reference: '+label)
    require(set(values) <= target.keys(), 'Broken references: '+label+' '+str(set(values)-target.keys()))


def inventory_check(spec, paths, mappings):
    manifest = read_json(paths[spec['record_id']])
    rows = pointer(manifest, spec['pointer'])
    require(isinstance(rows,list) and rows, 'Empty inventory: '+spec['id'])
    root = resolve(spec['location'], mappings)
    require(root.is_dir(), 'Inventory root is not a directory')
    seen = set()
    for row in rows:
        rel = str(relative(row['path']))
        require(rel not in seen, 'Duplicate inventory path: '+rel)
        seen.add(rel)
        file = root / rel
        require(file.resolve(strict=True).is_relative_to(root.resolve()), 'Inventory target escapes tree: '+rel)
        if 'link' in row:
            require(file.is_symlink() and os.readlink(file) == row['link'], 'Symlink identity changed: '+rel)
        else:
            require(not file.is_symlink() and file.is_file(), 'Unexpected symlink/type: '+rel)
    # Only this fixed reviewed helper is imported, never a manifest-supplied hook.
    # It checks exact file membership, sizes, hashes, modes and link identities.
    source = PLATFORM / 'build-support/qgis/common.py'
    module_spec = importlib.util.spec_from_file_location('candidate_qgis_integrity', source)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    if spec['helper'] == 'frontend':
        require('dist/js/gn-map.js' in seen, 'Missing integrated map entry')
        # Frontend helper compares hashes, not byte counts; supply actual sizes
        # only when the retained frontend manifest does not record them.
    rows = [row if 'link' in row else dict(row, bytes=row.get('bytes',row.get('size',(root/row['path']).stat().st_size))) for row in rows]
    module.verify_inventory(root, rows)
    return len(rows)


def validate(document, mappings, repository_manifest=None):
    from jsonschema import Draft202012Validator
    schema = read_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)
    roots = index(document['roots'], 'root')
    records = index(document['records'], 'record')
    profiles = index(document['profiles'], 'profile')
    combinations = index(document['combinations'], 'combination')
    findings = index(document['findings'], 'finding')
    inventories = index(document.get('inventories',[]), 'inventory')
    members = index(document.get('archive_members',[]), 'archive member')
    if repository_manifest is None:
        repository_manifest = read_json(PLATFORM/'plan/repositories.json')
    approved = {r['name'] for r in repository_manifest['repositories'] if r['kind']=='fork'}
    selected = [row['repository'].removeprefix('aloerch/') for row in roots.values()]
    require(len(selected)==len(set(selected)) and set(selected)==approved,
            'Selected roots must equal the eleven approved source forks')
    source_checks=0
    for root in roots.values():
        if 'git_location' in root:
            checkout=resolve(root['git_location'], mappings)
            def git(*args):
                env=dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1')
                return subprocess.check_output(['git','--no-replace-objects','-C',str(checkout),*args],env=env,text=True,stderr=subprocess.PIPE).strip()
            expected='https://github.com/aloerch/'+root['repository'].removeprefix('aloerch/')+'.git'
            require(git('remote','get-url','origin')==expected, 'Owned repository remote mismatch: '+root['id'])
            require(git('cat-file','-t',root['commit'])=='commit', 'Missing owned source commit')
            if root.get('tag'):
                require(not root['tag'].startswith('-') and '..' not in root['tag'], 'Unsafe tag')
                ref='refs/tags/'+root['tag']
                require(git('rev-parse','--verify',ref+'^{commit}')==root['commit'], 'Tag/peeled commit mismatch: '+root['id'])
                if root.get('tag_object'):
                    require(git('rev-parse','--verify',ref)==root['tag_object'], 'Tag object mismatch')
            source_checks+=1
        refs(root['record_ids'],records,root['id'])
        if root.get('source_binding'): require(root['source_binding']['record_id'] in root['record_ids'], 'Unlinked source identity binding')
        require(any(records[r]['kind'] in ('source','evidence','inventory') for r in root['record_ids']),
                'Root lacks immutable source evidence: '+root['id'])
    for root in roots.values():
        if root.get('gitlink'):
            link=root['gitlink']; require(link['root_id'] in roots, 'Unknown gitlink parent')
            parent=roots[link['root_id']]
            checkout=resolve(parent['git_location'],mappings)
            rel=str(relative(link['path']))
            value=subprocess.check_output(['git','--no-replace-objects','-C',str(checkout),'ls-tree',parent['commit'],'--',rel],text=True).strip()
            require(value=='160000 commit '+root['commit']+'\t'+rel and link['commit']==root['commit'], 'Gitlink mismatch')
    for profile in profiles.values():
        require(all(not re.search(r'(?i)\b(latest|master|main|head|unknown|unresolved)\b',v) for v in profile['versions'].values()), 'Unresolved active floating version: '+profile['id'])
        refs(profile['root_ids'],roots,profile['id'])
        refs(profile['record_ids'],records,profile['id'])
        steps=profile.get('ordered_steps',[])
        require([s['order'] for s in steps]==list(range(1,len(steps)+1)), 'Non-contiguous recipe order: '+profile['id'])
        for step in steps:
            refs(step['record_ids'],records,profile['id']+' step')
    require({r for p in profiles.values() for r in p['root_ids']}==roots.keys(), 'Profile source coverage incomplete')
    for combo in combinations.values():
        refs(combo['profile_ids'],profiles,combo['id'])
        refs(combo['artifact_ids'],records,combo['id'])
        refs(combo['evidence_ids'],records,combo['id'])
        require(all(records[r]['kind'] in ('artifact','inventory') for r in combo['artifact_ids']),
                'Combination artifact has wrong kind: '+combo['id'])
        require(all(records[r]['kind'] in ('evidence','inventory','lock') for r in combo['evidence_ids']),
                'Combination evidence has wrong kind: '+combo['id'])
        require(bool(combo.get('bindings')), 'Missing immutable evidence binding: '+combo['id'])
        bound={b['equals_record_sha256'] for b in combo['bindings']+document.get('bindings',[]) if 'equals_record_sha256' in b}
        require(set(combo['artifact_ids'])<=bound, 'Unbound selected artifact: '+combo['id'])
    require({p for c in combinations.values() for p in c['profile_ids']}==profiles.keys(),
            'Untested profile has no scoped combination')
    for finding in findings.values():
        refs(finding['record_ids'],records,finding['id'])
        require(bool(finding.get('evidence')), 'Finding lacks evidence: '+finding['id'])
        for ref in finding['evidence']:
            require(ref['record_id'] in finding['record_ids'], 'Unlinked finding evidence: '+finding['id'])
        require((finding['classification']=='selection-blocker')==finding['blocks']['candidate_adoption'], 'Contradictory adoption blocker disposition: '+finding['id'])
        if finding['classification']=='selection-blocker':
            require(finding['owner_action'] and finding['closure'] and finding['preferred'], 'Unactionable blocker')
    locations={}; paths={}; total_bytes=0
    for rid, record in records.items():
        key=(record['location']['root'],record['location']['path'])
        require(key not in locations or locations[key]==record['sha256'], 'Contradictory selected records: '+rid)
        locations[key]=record['sha256']
        path=resolve(record['location'], mappings)
        require(path.is_file(), 'Unavailable file: '+rid)
        require(not path.is_symlink() or ('link' in record and os.readlink(path)==record['link']),
                'Unrecorded symlink: '+rid)
        require(sha(path)==record['sha256'], 'Changed bytes: '+rid)
        if 'bytes' in record:
            require(path.stat().st_size==record['bytes'], 'Changed size: '+rid)
        paths[rid]=path; total_bytes+=path.stat().st_size
        for refkey in ('record_ids','source_ids','evidence_ids','recipe_ids','producing_record_ids','smoke_record_ids'):
            if refkey in record: refs(record[refkey], records, rid+' '+refkey, nonempty=False)
    bindings=[*({'record_id':r['source_binding']['record_id'],'pointer':r['source_binding']['pointer'],'equals':r['commit']} for r in roots.values() if r.get('source_binding')), *document.get('bindings',[]),*(b for c in combinations.values() for b in c['bindings'])]
    for binding in bindings:
        require(binding['record_id'] in paths, 'Unknown binding record')
        expected=binding.get('equals')
        if 'equals_record_sha256' in binding:
            require(binding['equals_record_sha256'] in records, 'Unknown bound artifact')
            expected=records[binding['equals_record_sha256']]['sha256']
        actual=pointer(read_json(paths[binding['record_id']]),binding['pointer'])
        require(type(actual)==type(expected) and actual==expected, 'Evidence binding mismatch: '+str(binding))
    for finding in findings.values():
        for ref in finding['evidence']:
            if 'pointer' in ref: pointer(read_json(paths[ref['record_id']]),ref['pointer'])
    entry_count=0
    for spec in inventories.values():
        require(spec['record_id'] in paths, 'Unknown inventory manifest')
        entry_count+=inventory_check(spec, paths, mappings)
    for spec in members.values():
        refs(spec.get('finding_ids',[]),findings,spec['id'],nonempty=False)
        require(spec['archive_id'] in paths, 'Unknown archive')
        relative(spec['member'])
        with zipfile.ZipFile(paths[spec['archive_id']]) as archive:
            matches=[i for i in archive.infolist() if i.filename==spec['member']]
            require(len(matches)==1, 'Missing/duplicate claimed archive member: '+spec['member'])
            with archive.open(matches[0]) as stream:
                require(hashlib.file_digest(stream,'sha256').hexdigest()==spec['sha256'], 'Changed archive member')
    blockers=[f['id'] for f in findings.values() if f['blocks']['candidate_adoption']]
    unknowns={p['id']:p['unknowns'] for p in profiles.values() if p.get('unknowns')}
    return {'inventory':{'status':'valid','roots':len(roots),'profiles':len(profiles),
                'combinations':len(combinations),'source_repositories_checked':source_checks,'records_hashed':len(paths),'record_bytes_hashed':total_bytes,
                'bindings_checked':len(bindings),'inventory_entries_checked':entry_count,
                'archive_members_checked':len(members),'coverage':'Only listed records, bindings, archive members and complete inventory trees; linked transitive locks are not recursively certified.'},
            'selection':{'status':'blocked' if blockers else 'review-required','blockers':blockers,
                         'findings':len(findings),'profile_unknowns':unknowns},
            'acceptance':{'status':'not-granted','owner_acceptance':False,'distribution_permission':False},
            'execution':'Read-only integrity verification; no historical runtime/build test was reexecuted.'}


def render_report(document):
    records={r['id']:r for r in document['records']}
    boundaries=list(dict.fromkeys(f['approval_excludes'] for f in document['findings']))
    def prose(value):
        if isinstance(value,dict):
            return '; '.join(k.replace('_',' ')+': '+prose(v) for k,v in value.items())
        if isinstance(value,list): return '; '.join(prose(v) for v in value)
        return str(value)
    def affected(value):
        if not isinstance(value,list): return prose(value)
        out=[]
        for item in value:
            if not isinstance(item,dict): out.append(str(item)); continue
            if item.get('coordinate'): out.append('`'+item['coordinate']+'`'); continue
            if item.get('name'):
                out.append('`'+item['name']+'` '+str(item.get('version','')))
                continue
            # Version-specific resource notice paths stay visible; large member
            # and hash lists remain in the authoritative manifest/evidence index.
            reduced={k:v for k,v in item.items() if k not in ('sha256','bytes','native_members','source_refs')}
            if 'notice_paths_hashes' in reduced:
                reduced['notice_paths']=[v['source_path'] for v in reduced.pop('notice_paths_hashes')]
            out.append(prose(reduced))
        return '; '.join(out)
    def evidence(ref):
        r=records[ref['record_id']];loc=r['location'];name=ref['record_id']
        if loc['root']=='platform':
            link='../'+loc['path'].removeprefix('plan/') if loc['path'].startswith('plan/') else '../../'+loc['path']
            label='['+name+']('+link+')'
        else: label='`'+name+'` (workspace:'+loc['path']+')'
        return label+(' at `'+ref['pointer']+'`' if 'pointer' in ref else '')
    lines=['# FND-02 owner-decision register','',
           'Generated from [the authoritative internal manifest](../candidates/fnd-02-candidate.json). Edit that manifest and regenerate.',
           'Full hashes, individual member paths and retained locations are in its `affected`, `records` and linked evidence fields. The summaries below do not replace those identities.',
           'Inventory validity, candidate selection and owner/distribution acceptance are separate. All proposed binary/resource changes are unexecuted variants.','',
           '| Finding | Disposition | Blocks adoption | Blocks distribution | Gate |', '|---|---|---|---|---|']
    for f in document['findings']:
        lines.append('| '+f['id']+' | '+f['classification']+' | '+str(f['blocks']['candidate_adoption']).lower()+' | '+str(f['blocks']['distribution']).lower()+' | '+f['gate'].replace('|','/')+' |')
    lines += ['','## Shared approval boundaries','']
    for i,boundary in enumerate(boundaries,1): lines += ['**B'+str(i)+':** '+boundary,'']
    for f in document['findings']:
        lines += ['## '+f['id']+' — '+f.get('component',f['id']), '',
                  '**Disposition:** '+f['classification']+' · **Gate:** '+f['gate']+' · **Criteria:** '+', '.join(f['criteria']),
                  '**Effect:** adoption '+('blocked' if f['blocks']['candidate_adoption'] else 'not blocked by this finding')+'; independent engineering '+('blocked' if f['blocks']['independent_engineering'] else 'can continue')+'; distribution '+('gated' if f['blocks']['distribution'] else 'not independently gated by this finding')+'. Approval boundary **B'+str(boundaries.index(f['approval_excludes'])+1)+'** applies.','',
                  '**Exact scope:** '+affected(f['affected']),'']
        for key,title in [('usage','Membership / consumers'),('established','Evidence establishes'),('unknown','Still unknown'),('preferred','Recommended course'),('alternatives','Alternatives and required tests'),('owner_action','Owner action / effect'),('closure','Closing evidence')]:
            lines += ['**'+title+':** '+prose(f[key]),'']
        lines += ['**Original evidence:** '+'; '.join(evidence(r) for r in f['evidence']), '']
    return '\n'.join(lines).rstrip()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',nargs='?',type=Path,default=MANIFEST)
    parser.add_argument('--workspace-root',type=Path,required=True,help='Retained AmbisGIS directory; never inferred from old absolute paths')
    parser.add_argument('--platform-root',type=Path,default=PLATFORM)
    parser.add_argument('--eligibility',action='store_true')
    parser.add_argument('--report',action='store_true',help='Print deterministic Markdown after successful integrity validation')
    args=parser.parse_args(argv)
    try:
        document=read_json(args.manifest)
        result=validate(document,{'platform':args.platform_root,'workspace':args.workspace_root})
        result['manifest_sha256']=sha(args.manifest)
        if args.report: print(render_report(document))
        else: print(json.dumps(result,indent=2,sort_keys=True))
        return 2 if args.eligibility else 0
    except Exception as exc:
        detail=(str(exc.json_path)+': '+exc.message) if hasattr(exc,'json_path') else str(exc)
        print(json.dumps({'inventory':{'status':'unsuccessful','error':detail[:2400]},
                          'selection':{'status':'not-assessed'},'acceptance':{'status':'not-granted'}}),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
