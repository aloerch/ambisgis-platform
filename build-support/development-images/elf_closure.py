#!/usr/bin/env python3
"""Read ELF headers from assembled archives; never execute an image member.

This detects missing direct SONAME/interpreter paths, not symbol-version or ABI
compatibility. Real relocation and ordinary installation tests remain required.
"""
import argparse
import io
import json
from pathlib import Path
import posixpath
import struct
import tarfile

import assemble as a


def elf(raw):
    if raw[:4] != b'\x7fELF': return None
    if raw[4:7] != b'\x02\x01\x01' or len(raw) < 64: raise ValueError('expected ELF64 little-endian')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', raw)
    if header[2] != 62: return {'other_machine': header[2]}
    offset, size, count = header[5], header[9], header[10]
    if size != 56 or count > 1024: raise ValueError('unexpected ELF program header table')
    segments = [struct.unpack_from('<IIQQQQQQ', raw, offset + i * size) for i in range(count)]
    def string(start):
        end = raw.find(b'\0', start)
        if not 0 <= start <= end < len(raw): raise ValueError('unterminated ELF string')
        return raw[start:end].decode('utf-8')
    interpreter = None; values = []; table = None
    for kind, flags, file_offset, address, physical, file_size, memory_size, align in segments:
        if file_offset + file_size > len(raw): raise ValueError('ELF segment exceeds member')
        if kind == 3: interpreter = string(file_offset)
        if kind == 2:
            if file_size % 16: raise ValueError('invalid ELF dynamic table')
            for position in range(file_offset, file_offset + file_size, 16):
                tag, value = struct.unpack_from('<qQ', raw, position)
                if tag == 0: break
                values.append((tag, value))
                if tag == 5: table = value
    base = None
    if table is not None:
        for segment in segments:
            if segment[0] == 1 and segment[3] <= table < segment[3] + segment[5]:
                base = segment[2] + table - segment[3]; break
        if base is None: raise ValueError('ELF dynamic string table is unmapped')
    strings = lambda tag: [string(base + value) for key, value in values if key == tag] if base is not None else []
    return {'interpreter': interpreter, 'needed': strings(1), 'soname': strings(14),
            'rpath': strings(15), 'runpath': strings(29)}


def inspect(path):
    with tarfile.open(path, 'r:') as archive:
        index = json.load(archive.extractfile('index.json'))
        manifest = json.load(archive.extractfile('blobs/sha256/' + index['manifests'][0]['digest'][7:]))
        config = json.load(archive.extractfile('blobs/sha256/' + manifest['config']['digest'][7:]))
        if len(manifest['layers']) != 1: raise ValueError('this assembler has one filesystem layer')
        with archive.extractfile('blobs/sha256/' + manifest['layers'][0]['digest'][7:]) as source:
            with tarfile.open(fileobj=source, mode='r|') as layer:
                members, headers = {}, {}
                for item in layer:
                    members[item.name] = {'kind': 'symlink' if item.issym() else 'directory' if item.isdir() else 'file',
                                          'target': item.linkname}
                    if item.isfile():
                        stream = layer.extractfile(item); prefix = stream.read(4)
                        if prefix == b'\x7fELF': headers[item.name] = elf(prefix + stream.read())
    def resolve_member(name, seen=()):
        name = posixpath.normpath(name).lstrip('/')
        if name in seen or len(seen) > 64: return False
        parts = name.split('/')
        for i in range(len(parts)):
            prefix = '/'.join(parts[:i+1]); value = members.get(prefix)
            if value is None: return False
            if value['kind'] == 'symlink':
                target = a.link_target(prefix, value['target'])
                return resolve_member(target + '/' + '/'.join(parts[i+1:]), (*seen, name))
        return name if members[name]['kind'] == 'file' else None
    env = dict(item.split('=', 1) for item in config['config']['Env'])
    libraries = env['LD_LIBRARY_PATH'].split(':')
    missing, rows, other_machine, contexts = [], [], [], {}
    def expanded(name, values):
        origin = '/' + posixpath.dirname(name)
        return [directory.replace('${ORIGIN}', origin).replace('$ORIGIN', origin)
                for value in values for directory in value.split(':')]
    visited = set()
    def visit(name, inherited=()):
        key = (name, inherited)
        if key in visited: return
        visited.add(key)
        if len(visited) > 100000: raise ValueError('ELF lookup context exceeded bound')
        header = headers.get(name)
        if not header or 'other_machine' in header: return
        own = expanded(name, header['rpath']) if not header['runpath'] else []
        onward = tuple(dict.fromkeys(own + list(inherited)))
        paths = list(onward) + libraries + expanded(name, header['runpath']) + ['/lib64', '/usr/lib64']
        for needed in header['needed']:
            candidates = [needed] if '/' in needed else [base + '/' + needed for base in paths]
            match = next((p for p in candidates if p.startswith('/') and resolve_member(p)), None)
            if match:
                contexts.setdefault((name, needed), set()).add(posixpath.normpath(match))
                visit(resolve_member(match), onward)
    for name in headers: visit(name)
    conditional = []
    for name, header in headers.items():
        if 'other_machine' in header:
            other_machine.append({'member': name, **header}); continue
        resolved = {}
        for needed in header['needed']:
            matches = sorted(contexts.get((name, needed), ()))
            resolved[needed] = matches
            if not matches:
                providers = [path for path in headers if posixpath.basename(path) == needed]
                row = {'member': name, 'needed': needed}
                if providers: conditional.append({**row, 'present_but_lookup_context_unproved': providers})
                else: missing.append(row)
        if header['interpreter'] and not resolve_member(header['interpreter']):
            missing.append({'member': name, 'interpreter': header['interpreter']})
        rows.append({'member': name, **header, 'resolved': resolved})
    return {'archive_sha256': a.digest(path), 'elf_members': len(headers), 'members': rows,
            'missing': missing, 'other_machine_members': other_machine, 'conditional_loader_context': conditional,
            'runtime_executed': False,
            'scope': 'Static DT_NEEDED/RPATH inheritance from retained ELF members; possible lookup contexts, not actual loaded closure. ABI, symbol versions, dlopen and actual relocation unverified.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = a.checked_path(args.output)
    if out.exists(): raise ValueError('fresh output required')
    result = inspect(a.regular(args.archive)); out.write_bytes(a.encoded(result))
    print(json.dumps({'elf_members': result['elf_members'], 'missing': result['missing']}, sort_keys=True))
    raise SystemExit(bool(result['missing']))
