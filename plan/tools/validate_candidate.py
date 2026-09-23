#!/usr/bin/env python3
"""Read-only FND-02 integrity and separately recorded owner-decision linkage.

Reports existing acceptance only; never grants rights or changes historical inputs.

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
ACCEPTANCE = 'plan/verification/fnd-02-owner-acceptance/acceptance.json'
ACCEPTED_MANIFEST_SHA256 = '0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99'
ACCEPTED_COMMENT_BODY_SHA256 = '4c8286ad42e8bb7a234c50337507aea690e8d92316fef34b0ebdf7c438b051af'


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


def render_report(document, manifest_name='fnd-02-candidate.json'):
    require(manifest_name not in ('.', '..') and Path(manifest_name).name == manifest_name and bool(re.fullmatch(r'[A-Za-z0-9_.-]+', manifest_name)), 'Unsafe report manifest name')
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
           'Generated from [the authoritative internal manifest](../candidates/'+manifest_name+'). Edit that manifest and regenerate.',
           'Candidate: `'+document['candidate_id']+'`. Manifest schema version: '+str(document['schema_version'])+'.',
           'Full hashes, individual member paths and retained locations are in its `affected`, `records` and linked evidence fields. The summaries below do not replace those identities.',
           'Inventory validity, candidate selection and owner/distribution acceptance are separate. Findings apply to this candidate; historical tests do not establish acceptance of changed artifacts.','',
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


def validate_acceptance(record_path, manifest_path, document, platform_root):
    """Check only the recorded September 22 decision; no live approval inference.

    The body digest pins the exact separately reviewed human decision. An owner
    login, merged PR, closed issue, or editable boolean alone cannot pass this
    narrow linkage check. A later decision needs a new reviewed record/change.
    """
    record = read_json(record_path)
    require(record['schema_version'] == 1 and
            record['record_kind'] == 'separate-final-owner-acceptance' and
            record['task'] == 'FND-02', 'Wrong owner acceptance record')
    candidate = record['candidate']
    require(document == read_json(manifest_path), 'Owner acceptance document differs from manifest bytes')
    require(candidate['sha256'] == sha(manifest_path) == ACCEPTED_MANIFEST_SHA256,
            'Owner acceptance manifest hash mismatch')
    require(candidate['candidate_id'] == document['candidate_id'] == 'fnd-02-json-nojpeg2000-proposal-4'
            and candidate['candidate_revision'] == document['candidate_revision'] == 4
            and candidate['schema_version'] == document['schema_version'] == 1,
            'Owner acceptance candidate identity mismatch')

    def retained(ref):
        path = resolve({'root': 'platform', 'path': ref['path']}, {'platform': platform_root})
        require(not path.is_symlink() and path.is_file() and sha(path) == ref['sha256'],
                'Changed owner acceptance evidence: ' + ref['path'])
        return path

    require(retained(candidate).resolve() == Path(manifest_path).resolve(),
            'Owner acceptance points to another manifest')
    ref = record['comment']
    comment = read_json(retained(ref))
    expected_url = 'https://github.com/aloerch/ambisgis-platform/issues/3#issuecomment-5785944488'
    require(ref['url'] == comment['html_url'] == expected_url and
            ref['id'] == comment['id'] == 5785944488 and
            comment['issue_url'] == 'https://api.github.com/repos/aloerch/ambisgis-platform/issues/3',
            'Wrong owner acceptance comment')
    require(ref['author'] == comment['user']['login'] == 'aloerch' and
            ref['author_id'] == comment['user']['id'] == 15285626 and
            comment['user']['type'] == 'User' and comment['author_association'] == 'OWNER' and
            comment['performed_via_github_app'] is None, 'Wrong owner acceptance author')
    require(ref['created_at'] == comment['created_at'] == ref['updated_at'] ==
            comment['updated_at'] == '2026-09-22T23:20:02Z', 'Owner acceptance date mismatch')
    require(hashlib.sha256(comment['body'].encode()).hexdigest() ==
            ref['body_sha256'] == ACCEPTED_COMMENT_BODY_SHA256,
            'Owner acceptance decision text changed')
    pr = read_json(retained(record['merged_pr']))
    require(pr['repository'] == {'full_name': 'aloerch/ambisgis-platform', 'id': 1376927351}
            and pr['number'] == 68 and pr['state'] == 'closed' and pr['merged'] is True
            and pr['base_ref'] == 'ambisgis/main', 'Wrong accepted merge identity')
    require(record['reviewed_head'] == pr['head_sha'] == '7c4c6a6ddbc364e520911e06b9a97a7c10bdcfcf'
            and record['merge_commit'] == pr['merge_commit_sha'] == '973a5ef383687cd00143c679f832cfb006a57cf0',
            'Owner acceptance head or merge mismatch')
    war = index(document['records'], 'record')[record['war']['record_id']]
    require(war['kind'] == 'artifact' and war['sha256'] == record['war']['sha256'] ==
            '90493ef3e96016bd150439d07b2e0adbcd2ec4292bd648f29c246e18422eebe1',
            'Owner acceptance WAR mismatch')
    require(record['replacement_inputs']['sha256'] ==
            '194139a86bb3640d991b4c23bc55b02d66526127bdea6c3d6f025216d41f87f5',
            'Owner acceptance replacement input mismatch')
    retained(record['replacement_inputs'])
    retained(record['existing_combination_evidence'])
    require(record['accepted_criteria'] == ['C1', 'C2', 'C3', 'C4'] and
            record['accepted_internal_steps'] == ['F02-06', 'F02-07', 'F02-08'] and
            record['accepted_profile_limits'] == ['NO-ORACLE', 'headless-Temurin17', 'NO-JPEG2000'],
            'Owner acceptance scope mismatch')
    excluded = ['FND-03', 'FND-05', 'FND-07', 'FND-08', 'P0', 'distribution', 'release',
                'production-deployment', 'future-PR-merges', 'source-notice-security-licensing-operational-gates']
    require(record['not_accepted'] == excluded, 'Owner acceptance later gates changed')
    return {'status': 'accepted-for-development', 'owner_acceptance': True,
            'distribution_permission': False, 'owner_comment': expected_url,
            'owner_comment_id': comment['id'], 'owner': ref['author'], 'owner_id': ref['author_id'],
            'decision_date': ref['created_at'], 'record_sha256': sha(record_path),
            'accepted_criteria': record['accepted_criteria'], 'not_accepted': excluded,
            'verification': 'Offline hash/linkage check of the separately reviewed decision; no live API or new approval.'}


def render_acceptance(acceptance):
    return ('\n\n## Separately recorded current owner decision\n\n'
            'The [explicit owner decision](' + acceptance['owner_comment'] + ') of '
            + acceptance['decision_date'] + ' accepts this exact candidate for subsequent engineering, '
            'all four FND-02 criteria, F02-06/F02-07/F02-08 and the stated profile/maintenance limits. '
            'The manifest and generated finding register above remain the immutable review-time record. '
            'This later governance linkage changes no historical approval field or tested input.\n\n'
            'Distribution permission remains false. FND-03/FND-05/FND-07/FND-08, P0, source/notices, '
            'security/licensing/operations, release/deployment and future merges remain unaccepted; '
            'eligibility remains exit 2. Full decision: '
            '[governance sidecar](../verification/fnd-02-owner-acceptance/acceptance.json).')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',nargs='?',type=Path,default=MANIFEST)
    parser.add_argument('--workspace-root',type=Path,required=True,help='Retained AmbisGIS directory; never inferred from old absolute paths')
    parser.add_argument('--platform-root',type=Path,default=PLATFORM)
    parser.add_argument('--eligibility',action='store_true')
    parser.add_argument('--acceptance-record',type=Path,help='Verify a separately reviewed decision; defaults to the bound sidecar only for the exact accepted manifest')
    parser.add_argument('--report',action='store_true',help='Print deterministic Markdown after successful integrity validation')
    args=parser.parse_args(argv)
    try:
        document=read_json(args.manifest)
        result=validate(document,{'platform':args.platform_root,'workspace':args.workspace_root})
        result['manifest_sha256']=sha(args.manifest)
        acceptance_path = args.acceptance_record
        if acceptance_path is None and result['manifest_sha256'] == ACCEPTED_MANIFEST_SHA256:
            acceptance_path = args.platform_root / ACCEPTANCE
        if acceptance_path is not None:
            result['acceptance'] = validate_acceptance(acceptance_path, args.manifest, document, args.platform_root)
            require(not result['selection']['blockers'], 'Accepted selection has new adoption blockers')
            result['selection']['status'] = 'selected-for-development'
        if args.report:
            report = render_report(document, args.manifest.name)
            if result['acceptance']['owner_acceptance']:
                report += render_acceptance(result['acceptance'])
            print(report)
        else: print(json.dumps(result,indent=2,sort_keys=True))
        return 2 if args.eligibility else 0
    except Exception as exc:
        detail=(str(exc.json_path)+': '+exc.message) if hasattr(exc,'json_path') else str(exc)
        print(json.dumps({'inventory':{'status':'unsuccessful','error':detail[:2400]},
                          'selection':{'status':'not-assessed'},'acceptance':{'status':'not-granted'}}),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
