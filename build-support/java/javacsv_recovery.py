#!/usr/bin/env python3
"""Recover the exact JavaCSV 2.0 source revisions from its publisher CVS snapshot.

This is a narrowly pinned RCS trunk reader, not a general CVS implementation.
The recovered publisher JAR must equal the already retained Maven artifact.
No network request, donor build script or repository configuration is executed.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile

SNAPSHOT_SHA256 = '608624c41a5b499e7f0085854fb39e359c1e34a133506ddf16c86331703263d3'
ARTIFACT_SHA256 = 'c287e9d431e4e05a0f7c9c023d133edf8a40112885cdb6e81b07773eee4680ed'
SOURCE_URL = 'https://sourceforge.net/code-snapshots/cvs/j/ja/javacsv.zip'
SELECTED = {
    'src/com/csvreader/CsvReader.java': ('1.9', '659de2080f9641e3d0ee3446eaa9b4ea1a8b3c30a3a6c470fcddcce7646867b4'),
    'src/com/csvreader/CsvWriter.java': ('1.8', 'adc1bb26bec625bb661d8e5902daaa98f69b8c10d7160e5531bbf41ad727b977'),
    'src/AllTests.java': ('1.4', 'f51edc54a4679ffd3ec1a09b6d3ce37971d1ba0e2b038f818c5fd4d0942c90fe'),
    'build.xml': ('1.3', 'e13866b5101f12cfbaffa77d76cb4dc90d32cb2ae9fd3819b95bb772dcd20866'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def lf_lines(data):
    # RCS diff-n counts LF only, including inside a binary file.
    return re.findall(rb'[^\n]*\n|[^\n]+$', data)


def reverse_delta(original, patch):
    old = lf_lines(original)
    commands = lf_lines(patch)
    result, position, index = [], 0, 0
    while index < len(commands):
        match = re.fullmatch(rb'([ad])(\d+) (\d+)\n?', commands[index])
        if match is None:
            raise ValueError('Invalid RCS reverse-delta command')
        operation, start, count = match.group(1), int(match.group(2)), int(match.group(3))
        index += 1
        boundary = start - 1 if operation == b'd' else start
        if count <= 0 or not position <= boundary <= len(old):
            raise ValueError('RCS delta references an invalid line range')
        result.extend(old[position:boundary])
        if operation == b'd':
            if boundary + count > len(old):
                raise ValueError('RCS deletion exceeds original file')
            position = boundary + count
        else:
            if index + count > len(commands):
                raise ValueError('RCS insertion is truncated')
            result.extend(commands[index:index + count])
            index += count
            position = boundary
    result.extend(old[position:])
    return b''.join(result)


def revision(rcs, wanted):
    head = re.search(rb'^head\s+(\d+\.\d+);', rcs)
    if head is None:
        raise ValueError('Expected an RCS trunk head')
    pattern = rb'\n(\d+\.\d+)\nlog\n@((?:[^@]|@@)*)@\ntext\n@((?:[^@]|@@)*)@'
    parts = list(re.finditer(pattern, rcs))
    if not parts or parts[0].group(1) != head.group(1):
        raise ValueError('RCS head text is missing or ambiguous')
    content, seen = None, set()
    for part in parts:
        number = part.group(1).decode('ascii')
        if number in seen:
            raise ValueError('Duplicate RCS revision')
        seen.add(number)
        text = part.group(3).replace(b'@@', b'@')
        content = text if content is None else reverse_delta(content, text)
        if number == wanted:
            date = re.search(rb'\n' + re.escape(part.group(1)) + rb'\ndate\s+([^;]+);', rcs)
            if date is None:
                raise ValueError('RCS revision date is missing')
            return content, date.group(1).decode('ascii')
    raise ValueError('Selected RCS revision is absent')


def capsule(files):
    output = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(files.items()):
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
                archive.addfile(entry, io.BytesIO(data))
    return output.getvalue()


def recover(snapshot, artifact, output):
    raw, binary = snapshot.read_bytes(), artifact.read_bytes()
    if digest(raw) != SNAPSHOT_SHA256 or digest(binary) != ARTIFACT_SHA256:
        raise ValueError('Retained snapshot or selected Maven artifact hash differs')
    files, selected = {}, []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        recovered, date = revision(archive.read('javacsv/javacsv/javacsv.jar,v'), '1.2')
        if recovered != binary:
            raise ValueError('Publisher CVS binary differs from selected Maven artifact')
        for name, (number, expected) in SELECTED.items():
            data, source_date = revision(archive.read('javacsv/javacsv/' + name + ',v'), number)
            if digest(data) != expected or source_date > date:
                raise ValueError('Selected source hash/date does not match recorded release provenance')
            files[name] = data
            selected.append({'path': name, 'revision': number, 'date': source_date,
                             'sha256': expected, 'size': len(data)})
    evidence = {'coordinate': 'net.sourceforge.javacsv:javacsv:2.0',
                'publisher_url': SOURCE_URL, 'snapshot_sha256': SNAPSHOT_SHA256,
                'publisher_binary': {'revision': '1.2', 'date': date, 'sha256': ARTIFACT_SHA256,
                                     'byte_equal_selected_artifact': True},
                'selected_sources': selected,
                'license_evidence': 'CsvReader.java and CsvWriter.java retain original LGPL-2.1-or-later headers. Historical AllTests.java has no file header; final license review remains open.',
                'limitations': 'Contemporaneous publisher source recovery and exact binary identity; no byte-identical rebuild or product acceptance claimed.'}
    files['DERIVATION.json'] = (json.dumps(evidence, indent=2, sort_keys=True) + '\n').encode()
    packed = capsule(files)
    # All validation completes before creating output; never replace a prior run.
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    path = output / 'javacsv-2.0-recovered-sources.tar.gz'
    path.write_bytes(packed)
    evidence['source_capsule'] = {'path': str(path), 'sha256': digest(packed), 'size': len(packed),
                                  'url': SOURCE_URL, 'revision': 'CVS CsvReader.java 1.9; CsvWriter.java 1.8; AllTests.java 1.4; build.xml 1.3'}
    (output / 'recovery.json').write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(recover(args.snapshot, args.artifact, args.output), indent=2))


if __name__ == '__main__':
    main()
