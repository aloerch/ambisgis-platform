#!/usr/bin/env python3
"""Verify an explicit supplement to frozen Java source custody.

No network, lifecycle execution, license approval or source-to-binary claim.
Class-file SourceFile attributes tie each binary class to a retained Java source
path; this establishes structural source coverage only. A matching release name
or matching Java filename alone cannot establish byte-for-byte reproducibility.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tarfile
import zipfile
import xml.etree.ElementTree as ET

from resolution_inventory import read_file, checked_path, unique_object

MAX_MEMBER = 32 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
SHA = re.compile(r'[0-9a-f]{64}\Z')
NOTICE = re.compile(r'(^|/)(license[^/]*|notice[^/]*|copying[^/]*|copyright[^/]*|lgpl[^/]*|gpl[^/]*)$', re.I)

class ClosureError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def member_path(name):
    if (not isinstance(name, str) or not name or '\\' in name or '\x00' in name
            or name.startswith('/') or any(p in ('', '.', '..') for p in name.rstrip('/').split('/'))
            or re.match(r'^[A-Za-z]:', name)):
        raise ClosureError('unsafe archive member path')
    return name.rstrip('/')


def archive_members(data):
    """Read regular files only, retaining names; never extract or execute code."""
    result, seen, total = {}, set(), 0
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for entry in archive.infolist():
                name = member_path(entry.filename)
                if name in seen: raise ClosureError('duplicate archive path')
                seen.add(name)
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode): raise ClosureError('archive symlink')
                if entry.is_dir(): continue
                if entry.file_size > MAX_MEMBER: raise ClosureError('archive member too large')
                total += entry.file_size
                if total > MAX_TOTAL: raise ClosureError('archive expansion too large')
                result[name] = archive.read(entry)
    else:
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
                for entry in archive:
                    name = member_path(entry.name)
                    if name in seen: raise ClosureError('duplicate archive path')
                    seen.add(name)
                    if entry.isdir(): continue
                    if not entry.isfile(): raise ClosureError('nonregular tar member')
                    if entry.size > MAX_MEMBER: raise ClosureError('archive member too large')
                    total += entry.size
                    if total > MAX_TOTAL: raise ClosureError('archive expansion too large')
                    result[name] = archive.extractfile(entry).read()
        except tarfile.TarError as exc:
            raise ClosureError('not a source archive') from exc
    return result


def class_source(data):
    """Return this_class and SourceFile without invoking a JVM on external code."""
    stream = io.BytesIO(data)
    def get(n):
        b = stream.read(n)
        if len(b) != n: raise ClosureError('truncated class file')
        return b
    def u1(): return get(1)[0]
    def u2(): return struct.unpack('>H', get(2))[0]
    def u4(): return struct.unpack('>I', get(4))[0]
    if get(4) != b'\xca\xfe\xba\xbe': raise ClosureError('invalid class magic')
    get(4)
    count, cp, i = u2(), {}, 1
    while i < count:
        tag = u1()
        if tag == 1: cp[i] = get(u2()).decode('utf-8', errors='replace')
        elif tag in (7, 8, 16, 19, 20): cp[i] = u2()
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18): get(4)
        elif tag in (5, 6): get(8); i += 1
        elif tag == 15: get(3)
        else: raise ClosureError('unknown class constant tag')
        i += 1
    get(2)
    name_index = cp.get(u2())
    classname = cp.get(name_index)
    if not isinstance(classname, str): raise ClosureError('invalid class identity')
    member_path(classname)
    get(2)
    get(2 * u2())
    def attributes():
        values = []
        for _ in range(u2()):
            attr = cp.get(u2()); size = u4(); values.append((attr, get(size)))
        return values
    for _ in range(2):
        for _ in range(u2()): get(6); attributes()
    source = None
    for key, value in attributes():
        if key == 'SourceFile':
            if source is not None or len(value) != 2: raise ClosureError('invalid SourceFile attribute')
            source = cp.get(struct.unpack('>H', value)[0])
            if not isinstance(source, str) or '/' in source or '\\' in source or source in ('', '.', '..'):
                raise ClosureError('invalid SourceFile value')
    if stream.read(1): raise ClosureError('trailing class bytes')
    return classname, source


def source_index(members):
    result = {}
    for path, data in members.items():
        if not path.endswith(('.java', '.java.in', '.aj', '.groovy', '.scala')): continue
        text = data.decode('utf-8', errors='replace')
        text = re.sub(r'''//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''', '', text, flags=re.S | re.X)
        package = re.search(r'^\s*package\s+([\w.]+)\s*;', text, re.M)
        basename = path.rsplit('/', 1)[-1]
        name = (package[1].replace('.', '/') + '/' if package else '') + (basename[:-3] if basename.endswith('.java.in') else basename)
        reference = {'path': path, 'sha256': digest(data), 'size': len(data), 'source_kind': 'generation-template' if path.endswith('.java.in') else 'source-text'}
        result.setdefault(name, []).append(reference)
        # Stripped class files lack SourceFile. Record a weaker declaration mapping
        # for top-level types, including secondary types whose name differs from
        # the filename. Strings/comments do not contribute brace nesting.
        syntax = text
        depth = 0
        for token in re.finditer(r'[{}]|\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)', syntax):
            if token[0] == '{': depth += 1
            elif token[0] == '}': depth -= 1
            elif depth == 0:
                typename = (package[1].replace('.', '/') + '/' if package else '') + token[1]
                result.setdefault(typename + '.class-declaration', []).append(reference)
    return result


def coverage(binary, sources):
    index = source_index(sources)
    mapped, missing = [], []
    for path, data in sorted(binary.items()):
        if not path.endswith('.class'): continue
        classname, source = class_source(data)
        normal_path = re.sub(r'^META-INF/versions/[0-9]+/', '', path)
        if normal_path != classname + '.class': raise ClosureError('class path/identity mismatch')
        expected = classname.rsplit('/', 1)[0] + '/' + source if source and '/' in classname else source
        candidates = index.get(expected, [])
        method = 'classfile-SourceFile-attribute'
        if not source:
            candidates = index.get(classname.split('$', 1)[0] + '.class-declaration', [])
            method = 'inferred-top-level-source-declaration; debug attribute absent'
        item = {'class': classname, 'source_file': source, 'mapping_method': method}
        if candidates: mapped.append({**item, 'candidates': candidates})
        else: missing.append(item)
    return {'class_count': len(mapped) + len(missing), 'mapped_class_count': len(mapped),
            'unmapped': missing, 'mappings': mapped, 'source_file_count': len({r['path'] for v in index.values() for r in v})}


def read_json(path):
    return json.loads(read_file(path.absolute()), object_pairs_hook=unique_object)


def checked_blob(root, reference):
    path = reference['path']
    member_path(path)
    expected = reference['sha256']
    if not isinstance(expected, str) or not SHA.fullmatch(expected): raise ClosureError('invalid SHA256')
    data = read_file(root / path)
    if digest(data) != expected or len(data) != reference['size']: raise ClosureError('retained input hash/size mismatch')
    return data


def notices(members):
    return [{'path': name, 'sha256': digest(data), 'size': len(data)}
            for name, data in sorted(members.items()) if NOTICE.search(name)]


def investigation_receipts(supplement, paths):
    result = []
    for name in paths:
        member_path(name)
        data = read_file(supplement / name)
        receipt = json.loads(data, object_pairs_hook=unique_object)
        result.append({'path':name, 'sha256':digest(data), 'size':len(data),
                       'observation':{k:receipt[k] for k in ('url','status','error','sha256','size') if k in receipt}})
    return result


def summarize(gap, frozen, supplement, candidate):
    if not SHA.fullmatch(gap['binary_sha256']):raise ClosureError('invalid binary hash')
    for observation in candidate.get('observed_use', []):
        if observation.get('artifact_sha256') != gap['binary_sha256'] or observation.get('gav') != gap['gav']:
            raise ClosureError('observed classpath identity mismatch')
    binary_path = frozen / 'blobs/sha256' / gap['binary_sha256']
    binary_data = read_file(binary_path)
    if digest(binary_data) != gap['binary_sha256']: raise ClosureError('binary hash mismatch')
    binary = archive_members(binary_data)
    pom_path = gap['binary_path'][:-4] + '.pom'
    record = read_json(frozen / 'records' / gap['repository'] / (pom_path + '.json'))
    if record['maven_path'] != pom_path or record['repository'] != gap['repository']:
        raise ClosureError('POM identity mismatch')
    pom_data = checked_blob(frozen, {'path': 'blobs/sha256/' + record['sha256'], **{k:record[k] for k in ('sha256','size')}})
    if b'<!DOCTYPE' in pom_data or b'<!ENTITY' in pom_data: raise ClosureError('POM DTD/entity forbidden')
    pom = ET.fromstring(pom_data)
    license_nodes = [node for node in pom.iter() if node.tag.rsplit('}', 1)[-1] == 'license']
    licenses = [{c.tag.rsplit('}',1)[-1]:c.text for c in node} for node in license_nodes]
    sources = {name: data for name, data in binary.items() if name.endswith('.java')}
    source_notices, retained, all_source_members = notices(binary), [], {}
    for reference in candidate.get('sources', []):
        if not reference.get('revision') or not reference.get('identity_evidence'):
            raise ClosureError('source revision and identity evidence required')
        if reference.get('derived_from'):
            checked_blob(supplement, reference['derived_from'])
        source = archive_members(checked_blob(supplement, reference))
        prefix = reference['sha256'] + '/'
        all_source_members.update({prefix + name:data for name,data in source.items()})
        sources.update({prefix + name:data for name,data in source.items()})
        source_notices.extend({**n,'archive_sha256':reference['sha256']} for n in notices(source))
        retained.append(reference)
    observed = coverage(binary, sources)
    generated = []
    rules = candidate.get('generated_classes', {})
    missing = {item['class']:item for item in observed['unmapped']}
    for classname, rule in rules.items():
        if classname not in missing:raise ClosureError('generated rule must name an actually unmapped class')
        for kind in ('source', 'recipe'):
            path = rule[kind + '_member']
            member_path(path)
            data = all_source_members.get(path)
            if data is None or digest(data) != rule[kind + '_sha256']:
                raise ClosureError('generated source/recipe evidence mismatch')
        if not rule.get('mechanism'):raise ClosureError('generated class requires explicit mechanism')
        generated.append({**missing[classname], **rule})
    observed['generated_class_inputs'] = generated
    observed['generated_input_count'] = len(generated)
    observed['unmapped'] = [x for x in observed['unmapped'] if x['class'] not in rules]
    observed['template_mapping_count'] = sum(any(r['source_kind']=='generation-template' for r in x['candidates']) for x in observed['mappings'])
    if observed['class_count'] == 0:
        # Empty marker/aggregator packages must contain only Maven/JAR metadata.
        group, artifact, _ = gap['gav'].split(':')
        metadata = {'META-INF/MANIFEST.MF', f'META-INF/maven/{group}/{artifact}/pom.xml', f'META-INF/maven/{group}/{artifact}/pom.properties'}
        bad = [n for n in binary if n not in metadata and not (NOTICE.search(n) and ('.' not in n.rsplit('/',1)[-1] or n.lower().endswith(('.txt','.md','.html','.htm'))))]
        if bad: raise ClosureError('classless archive contains unreviewed executable/resource payload')
        disposition = 'metadata-only-no-java-classes'
    elif observed['mapped_class_count'] + observed['generated_input_count'] == observed['class_count']:
        disposition = 'embedded-source-coverage' if not retained else ('generated-source-input-coverage' if observed['generated_input_count'] or observed['template_mapping_count'] else 'retained-source-coverage')
    elif observed['mapped_class_count']:
        disposition = 'partial-source-coverage'
    else:
        disposition = 'unresolved-source'
    return {'gav':gap['gav'],'repository':gap['repository'],'binary_path':gap['binary_path'],
            'binary_sha256':gap['binary_sha256'],'binary_size':len(binary_data),
            'use':{'direct_declarations':gap['direct_effective_declarations'],
                   'plugin_matches':gap['direct_effective_plugin_matches'],
                   'observed_test_classpaths':candidate.get('observed_use',[]),
                   'retained_pom_examples':gap['retained_pom_examples'],
                   'resolved_plugin_log_examples':gap['resolved_plugin_log_examples'],
                   'limitation':'Declarations/acquisition observations do not prove selected runtime use; no gap is declared unused.'},
            'sources':retained,'source_coverage':observed,'disposition':disposition,
            'license_evidence':{'pom_sha256':record['sha256'],'pom_declarations':licenses,'notice_members':source_notices,
                                'source_header_evidence':[{'path':n,'sha256':digest(b),'size':len(b)} for n,b in sorted(sources.items()) if n.endswith(('.java','.aj','.scala','.groovy')) and re.search(rb'copyright|license|licence',b[:8192],re.I)][:20],
                                'approval':'pending; inventory is not final legal approval'},
            'investigation':investigation_receipts(supplement,candidate.get('investigation',[])),
            'remaining':candidate.get('remaining', 'Source-to-binary rebuild and full build/test/native inputs remain unverified.'),
            'source_binary_correspondence_established':False}


def build_report(triage, manifest, frozen, supplement):
    gaps = triage['gaps']
    candidates = manifest['artifacts']
    wanted = {g['gav'] for g in gaps}
    if len(wanted) != len(gaps): raise ClosureError('duplicate inventory coordinate')
    if set(candidates) != wanted: raise ClosureError('supplement must account for every exact inventory coordinate')
    records = [summarize(gap, frozen, supplement, candidates[gap['gav']]) for gap in gaps]
    counts = {}
    for record in records: counts[record['disposition']] = counts.get(record['disposition'],0)+1
    return {'schema_version':1,'scope':'Supplemental structural source inventory; not build/runtime/release acceptance',
            'artifact_count':len(records),'dispositions':counts,'build_ready':False,
            'source_binary_correspondence_established':False,'artifacts':records}


def restore_sources(manifest, supplement, fetch):
    """Restore only explicit, hash-locked missing sources; never overwrite bytes."""
    supplement = supplement.absolute()
    supplement.mkdir(parents=True, exist_ok=True)
    checked_path(supplement, directory=True)
    result = []
    unique = {}
    for candidate in manifest['artifacts'].values():
        for reference in candidate.get('sources', []):
            member_path(reference['path'])
            if not SHA.fullmatch(reference['sha256']): raise ClosureError('invalid expected hash')
            if reference['path'] != 'blobs/sha256/' + reference['sha256']:
                raise ClosureError('source restore requires content addressed path')
            previous = unique.setdefault(reference['sha256'], reference)
            if any(previous[k] != reference[k] for k in ('size','path','url')):
                raise ClosureError('inconsistent duplicate source declaration')
    for reference in unique.values():
        path = supplement / reference['path']
        if path.exists() or path.is_symlink():
            checked_blob(supplement, reference)
            result.append({'sha256':reference['sha256'],'restored':False})
            continue
        if reference.get('derived_from'):
            raise ClosureError('derived source archive must be reconstructed with its recorded derivation recipe before verification')
        data = fetch(reference['url'])
        if digest(data) != reference['sha256'] or len(data) != reference['size']:
            raise ClosureError('download differs from retained source lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        checked_path(path.parent, directory=True)
        with path.open('xb') as stream:stream.write(data)
        result.append({'sha256':reference['sha256'],'restored':True})
    return result


def fetch_https(url):
    from urllib.parse import urlsplit
    from urllib.request import Request, urlopen
    def validate(value):
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment:
            raise ClosureError('source restore requires public HTTPS URL without credentials/fragment')
    validate(url)
    with urlopen(Request(url, headers={'User-Agent':'AmbisGIS-source-closure/1'}), timeout=60) as response:
        validate(response.url)
        data = response.read(MAX_TOTAL + 1)
    if len(data) > MAX_TOTAL:raise ClosureError('download too large')
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--triage',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--frozen-maven',type=Path,required=True)
    parser.add_argument('--supplement',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--restore-sources',action='store_true', help='Explicitly restore missing hash-locked source archives over HTTPS')
    args=parser.parse_args()
    try:
        frozen = args.frozen_maven.absolute()
        supplement = args.supplement.absolute()
        if frozen == supplement or frozen in supplement.parents or supplement in frozen.parents:
            raise ClosureError('supplement must be separate from frozen custody')
        manifest = read_json(args.manifest)
        restore = restore_sources(manifest, supplement, fetch_https) if args.restore_sources else []
        result=build_report(read_json(args.triage),manifest,frozen,supplement)
        result['source_restore'] = restore
        result['inputs']={k:{'path':str(p),'sha256':digest(read_file(p.absolute()))} for k,p in [('triage',args.triage),('manifest',args.manifest)]}
        with args.output.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
        print(json.dumps({k:result[k] for k in ('artifact_count','dispositions','build_ready')}))
        return 2 if any(a['disposition'] in ('partial-source-coverage','unresolved-source') for a in result['artifacts']) else 0
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile,ET.ParseError) as exc:
        print(str(exc));return 1

if __name__=='__main__':raise SystemExit(main())
