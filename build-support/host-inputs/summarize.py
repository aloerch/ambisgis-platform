#!/usr/bin/env python3
"""Project verified selected host receipts into a public inventory.

Full installed-package and payload observations remain in private custody. This
projection checks receipt bindings and complete selected sets; it does not
replace signature/payload verification or confer product/release acceptance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from retain import digest


def binding(path):
    return {'file': path.name, 'sha256': digest(path), 'bytes': path.stat().st_size}


def project(selection, binaries, sources, payload, replay):
    if not selection['packages'] or not selection['selection_paths']:
        raise ValueError('Empty selected input inventory')
    wanted = {Path(row['location']).name for row in selection['packages']}
    received = [Path(row['file']).name for row in binaries['results']]
    if binaries['failures'] or len(received) != len(set(received)) or set(received) != wanted:
        raise ValueError('Incomplete or failed selected binary custody')
    source_names = {row['source_rpm'] for row in selection['packages']}
    source_rows = sources['results']
    received_sources = [row['source_rpm'] for row in source_rows]
    if (sources['failures'] or len(received_sources) != len(set(received_sources))
            or set(received_sources) != source_names):
        raise ValueError('Incomplete or failed selected source custody')
    if any(not row['error'].startswith('No exact source RPM for ') for row in selection['unresolved']):
        raise ValueError('Unresolved selected binary identity or provider dependency')
    if (payload['status'] != 'selected-build-inputs-match' or payload['uncovered_selected_paths']
            or payload['blocking_build_input_differences']
            or payload['selected_paths'] != len(selection['selection_paths'])):
        raise ValueError('Incomplete selected payload correspondence')
    if (replay['network_calls'] != 0 or replay['all_binary_network_flags_false'] is not True
            or replay['all_obs_network_flags_false'] is not True
            or replay['binary_count'] != len(wanted) or replay['source_count'] != len(source_names)):
        raise ValueError('Incomplete retained no-network replay')
    by_file = {Path(row['file']).name: row for row in binaries['results']}
    packages = []
    for row in selection['packages']:
        retained = by_file[Path(row['location']).name]
        packages.append({**row, 'retained_sha256': retained['sha256'],
                         'signature_verification': retained['verification']})
    projected_sources = []
    for row in sorted(source_rows, key=lambda row: row['source_rpm']):
        item = {'source_rpm': row['source_rpm'], 'kind': row['kind']}
        if row['kind'] == 'retained-source-rpm':
            item.update(sha256=row['sha256'], verification=row['verification'])
        elif row['kind'] == 'exact-obs-build-sources':
            item.update({key: row[key] for key in ('disturl', 'source_package', 'multibuild_flavor',
                        'listing_url', 'listing_sha256', 'source_rpm_not_retained', 'scope')})
            item['files'] = [{key: entry[key] for key in ('name', 'url', 'sha256', 'bytes', 'publisher_md5')}
                             for entry in row['files']]
        else:
            raise ValueError('Unknown source custody form')
        projected_sources.append(item)
    return {
        'schema_version': 1,
        'scope': 'Selected openSUSE Tumbleweed x86_64 development-host build/runtime inputs; no clean installation or source-bootstrap acceptance',
        'packages': packages, 'source_groups': projected_sources,
        'selected_files': selection['selected_file_observations'],
        'explicit_build_support': selection['explicit_packages'],
        'metadata_catalogs': [{key: row[key] for key in ('kind', 'repository_url', 'sha256')}
                              for row in selection['metadata_catalogs']],
        'generated_host_resources': [{key: row[key] for key in ('path', 'sha256', 'bytes', 'disposition')}
                                     for row in selection['generated_host_resources']],
        'generated_package_links': payload['generated_package_links'],
        'limits': selection['limits'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('selection', 'binaries', 'sources', 'payload', 'replay', 'observation'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name) for name in ('selection', 'binaries', 'sources', 'payload', 'replay', 'observation')}
    records = {name: json.loads(path.read_text()) for name, path in paths.items()}
    selected_sha = digest(args.selection)
    if any(records[name]['manifest_sha256'] != selected_sha for name in ('binaries', 'sources', 'payload', 'replay')):
        raise ValueError('Receipt selection binding differs')
    extra = records.pop('observation')
    observed = {row['path']: row['sha256'] for row in records['selection']['selected_file_observations']}
    for row in extra['paths']:
        if row['resolved'].startswith(('/usr/', '/bin/', '/sbin/', '/lib/', '/lib64/')):
            if observed.get(row['resolved']) != row['sha256']:
                raise ValueError('Missing or changed additional system observation')
    public = project(**records)
    evidence = {
        'task': 'FND-08', 'full_fnd08_acceptance': False,
        'receipts': {name: binding(path) for name, path in paths.items()},
        'tool_observation_sha256': records['selection']['observation_sha256'],
        'qgis_runtime_observation_sha256': records['selection']['runtime_observation_sha256'],
        'counts': {'binary_packages': len(public['packages']), 'source_groups': len(public['source_groups']),
                   'source_forms': dict(Counter(row['kind'] for row in public['source_groups'])),
                   'selected_files': len(public['selected_files']), 'payload_files': records['payload']['file_counts']},
        'payload_observed_at': {key: records['payload'][key] for key in ('started_at', 'finished_at')},
        'historical_source_metadata_diagnostics': [{'package': row['installed']['name'], 'error': row['error']}
                                                  for row in records['selection']['unresolved']],
        'limits': ['OBS source directories are distinct from retained original source RPMs.',
                   'Observations are not backdated to previous build starts.',
                   str(records['payload']['file_counts'].get('unreadable', 0)) + ' unreadable package files outside the selected build-input set remain explicit.',
                   'Generated host caches, compiler bootstrap, clean supported installation, full rights/security review and OWN-02 remain open.',
                   'No whole-host package inventory or home/configuration contents are projected.'],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    lock = args.output / 'selected-inputs.json'
    with lock.open('x') as stream:
        json.dump(public, stream, indent=2); stream.write('\n')
    evidence['public_selected_input_lock'] = binding(lock)
    with (args.output / 'evidence.json').open('x') as stream:
        json.dump(evidence, stream, indent=2); stream.write('\n')
    print(json.dumps(evidence['counts']))


if __name__ == '__main__':
    main()
