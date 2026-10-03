#!/usr/bin/env python3
"""Compare two real fresh successor builds; diagnostics never replace raw hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from common import require, sha, save
from successor_stage import verify_build


def read(path):
    return json.loads(path.read_text())


def selected_inputs(attempt):
    result = read(attempt/'result.json')
    authority = read(attempt/'authority.json')
    receipt = read(attempt/'compile/receipt.json')
    return {'commit':result['commit'],'tree':result['tree'],
            'archive_sha256':authority['archive']['sha256'],
            'historical_producer_sha256':result['historical_producer_sha256'],
            'adapter_sha256':result['adapter_sha256'],
            'publication_receipt_sha256':result['publication_receipt_sha256'],
            'support_inventory_sha256':receipt['support_inventory_sha256'],
            'spatial_manifest_sha256':receipt['spatial_manifest_sha256'],
            'selected_profile':receipt['selected_profile'], 'xml_profile':receipt['xml_profile'],
            'native_inventory':receipt['base_inventory'], 'tools':receipt['tools'],
            'configure_extra_flags':authority['configure_extra_flags']}


def input_digest(inputs):
    return hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_network(proof, command):
    require(proof.get('command_exit_code') == 0 and proof.get('status') == 'completed'
            and proof.get('command') == command and proof.get('kernel_state',{}).get('no_new_privs') == 1
            and proof.get('kernel_state',{}).get('seccomp_mode') == 2
            and [p.get('family') for p in proof.get('probes',[])] == ['AF_INET','AF_INET6','AF_UNIX','AF_UNIX']
            and all(p.get('passed') is True for p in proof['probes']),
            'missing successful no-socket network receipt')


def path_diagnostic(first, second, first_root, second_root):
    """Explain exact path/build-ID differences, leaving original files untouched."""
    left, right = first.read_bytes(), second.read_bytes()
    result = {'raw_bytes_equal':left == right, 'first_bytes':len(left),'second_bytes':len(right)}
    old, new = str(first_root).encode(), str(second_root).encode()
    count = left.count(old)
    adjusted = left.replace(old,new)
    result['first_attempt_path_occurrences'] = count
    # Qt QStringLiteral stores the same absolute path in UTF-16. Attribute only
    # complete exact attempt roots, never arbitrary numeric or text changes.
    encoded_counts = {}
    for encoding in ('utf-16-le','utf-16-be'):
        old, new = str(first_root).encode(encoding), str(second_root).encode(encoding)
        encoded_counts[encoding] = adjusted.count(old)
        adjusted = adjusted.replace(old,new)
    result['utf16_attempt_path_occurrences'] = encoded_counts
    count += sum(encoded_counts.values())
    if adjusted == right:
        result['diagnostic_only_equivalence'] = 'attempt absolute path' if count else 'identical'
        return result
    if left.startswith(b'\x7fELF') and right.startswith(b'\x7fELF'):
        offsets = []
        for path in (first,second):
            completed = subprocess.run(['readelf','-SW',str(path)],text=True,capture_output=True,check=True)
            matches = re.findall(r'\.note\.gnu\.build-id\s+NOTE\s+[0-9a-f]+\s+([0-9a-f]+)\s+([0-9a-f]+)',completed.stdout)
            offsets.append([(int(start,16),int(size,16)) for start,size in matches])
        result['build_id_sections'] = offsets
        if len(offsets[0]) == 1 and offsets[0] == offsets[1] and len(adjusted) == len(right):
            start,size = offsets[0][0]
            adjusted = adjusted[:start]+b'\0'*size+adjusted[start+size:]
            stripped = right[:start]+b'\0'*size+right[start+size:]
            if adjusted == stripped:
                result['diagnostic_only_equivalence'] = 'attempt absolute path and GNU build ID'
                return result
    result['diagnostic_only_equivalence'] = None
    result['unexplained_difference'] = True
    return result


def chronology(first, second, drift, fixture):
    baseline = Path(fixture.get('baseline_receipt',str(drift.parent/'before.json')))
    require(read(baseline) == fixture['fixture_before'], 'fixture baseline receipt changed')
    sequence = [baseline,first/'started.json',first/'result.json',drift,
                second/'started.json',second/'result.json']
    rows = [{'path':str(path),'sha256':sha(path),'mtime_ns':path.stat().st_mtime_ns} for path in sequence]
    require([row['mtime_ns'] for row in rows] == sorted(row['mtime_ns'] for row in rows),
            'fixture must precede first build and drift must occur between completed builds')
    return {'ordered':True,'basis':'original local receipt mtimes; observations, not signed timestamps','events':rows}


def compare(first, second, drift, output):
    require(first != second and not output.exists(), 'two distinct attempts and fresh comparison required')
    prefix1, manifest1 = verify_build(first)
    prefix2, manifest2 = verify_build(second)
    inputs1, inputs2 = selected_inputs(first), selected_inputs(second)
    require(inputs1 == inputs2, 'selected build inputs changed')
    fixture = read(drift)
    timeline = chronology(first,second,drift,fixture)
    require(fixture['floating_positive_control']['changed'] is True and
            fixture['fixture_before']['commit'] != fixture['fixture_after']['commit'] and
            fixture['fixture_before']['api_sha256'] != fixture['fixture_after']['api_sha256'],
            'actual synthetic drift and positive control required')
    by1 = {row['path']:row for row in manifest1['files']}
    by2 = {row['path']:row for row in manifest2['files']}
    changed = []
    for path in sorted(set(by1) | set(by2)):
        if path not in by1 or path not in by2:
            changed.append({'path':path,'first':by1.get(path),'second':by2.get(path),
                'diagnostic':{'raw_bytes_equal':False,'unexplained_difference':True,
                              'scope':'output membership changed'}})
            continue
        if by1[path] == by2[path]: continue
        row = {'path':path,'first':by1[path],'second':by2[path]}
        if 'sha256' in by1[path] and 'sha256' in by2[path]:
            row['diagnostic'] = path_diagnostic(prefix1/path,prefix2/path,first,second)
        else:
            row['diagnostic'] = {'raw_bytes_equal':False,'unexplained_difference':True,
                                 'scope':'symlink changes require manual attribution'}
        changed.append(row)
    network = []
    for attempt in (first,second):
        for name in ('configure','compile','stage','staged-crs-sync','native-test-compile',
                     'desktop-linkage','server-linkage','generated-source-reproduce'):
            path = attempt/'compile'/(name+'-network.json')
            proof = read(path)
            command_path = attempt/'compile'/(name+'-command.json')
            command = read(command_path)
            argv = command['argv']
            require(command['exit_code'] == 0 and command['log_sha256'] == sha(attempt/'compile'/(name+'.log')),
                    'build command/log evidence changed')
            verify_network(proof, argv[argv.index('--')+1:])
            network.append({'path':str(path),'sha256':sha(path),'command_sha256':sha(command_path)})
    report = {**fixture,'chronology':timeline,'product':{'selected_roots':{'qgis':inputs1['commit']},
              'input_manifest_sha256_before':input_digest(inputs1),'input_manifest_sha256_after':input_digest(inputs2),
              'selected_inputs_unchanged':True,'first_attempt':str(first),'second_attempt':str(second),
              'source_archive_bytes_equal':True,'output_comparison':{'entries':len(set(by1)|set(by2)),
                 'first_entries':len(by1),'second_entries':len(by2),
                 'unchanged_entries':len(set(by1)|set(by2))-len(changed),
                 'raw_bytes_identical':not changed,'changed_entries':len(changed),'differences':changed,
                 'added_paths':sorted(set(by2)-set(by1)),'removed_paths':sorted(set(by1)-set(by2)),
                 'unexplained_entries':sum(bool(row['diagnostic'].get('unexplained_difference')) for row in changed)}},
              'network_receipts':network,'scope':'Actual fresh builds of exact source; raw equality and diagnostic equivalence are distinct. No canonical diagnostic is advertised as byte identity.',
              'network_scope':'Actual seccomp kernel probes and command-bound receipts, not an every-syscall trace. AF_UNIX remains available; trusted builds only. Producer resolves complete exact Git objects locally and uses retained inputs; no donor API/default ref is a product input.',
              'recipe_sha256':sha(Path(__file__))}
    save(output,report)
    require(not report['product']['output_comparison']['unexplained_entries'],
            'unexplained output differences; diagnostic report retained')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('first','second','drift','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    report = compare(args.first.resolve(),args.second.resolve(),args.drift.resolve(),args.output.resolve())
    print(json.dumps({k:v for k,v in report['product']['output_comparison'].items() if k != 'differences'}))
