#!/usr/bin/env python3
"""One exact, layout-preserving DT_NEEDED repair for the retained PROJ build."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import assemble as a
import elf_closure

ORIGINAL_SHA256 = '5c39e16ad3ebf9db1ef45519068d3e9340291a48bf44532cb730b09154e5c591'
OLD = '/home/revelberry/Projects/AmbisGIS/build-worktrees/postgis-slice/run-003/prefix/lib/libsqlite3.so'
NEW = 'libsqlite3.so'


def transform(raw, old, new, expected_sha256):
    if hashlib.sha256(raw).hexdigest() != expected_sha256: raise ValueError('exact original ELF hash differs')
    if raw[:7] != b'\x7fELF\x02\x01\x01': raise ValueError('ELF64 little-endian required')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', raw)
    if header[2] != 62 or header[11] != 64 or not 1 <= header[12] <= 4096:
        raise ValueError('unexpected x86-64 section layout')
    sections = [struct.unpack_from('<IIQQQQIIQQ', raw, header[6] + i * 64) for i in range(header[12])]
    dynamic = [(i, row) for i, row in enumerate(sections) if row[1] == 6]
    if len(dynamic) != 1: raise ValueError('one dynamic section required')
    _, dyn = dynamic[0]; string_index = dyn[6]
    strings = sections[string_index]
    if strings[1] != 3 or strings[4] + strings[5] > len(raw): raise ValueError('invalid dynamic string table')
    table = raw[strings[4]:strings[4] + strings[5]]
    def value(offset):
        end = table.find(b'\0', offset)
        if not 0 <= offset <= end < len(table): raise ValueError('invalid dynamic string reference')
        return table[offset:end].decode(), end + 1
    references, needed = [], []
    allowed_tags = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20, 23, 25, 26, 27, 28, 29,
                    0x6ffffef5, 0x6ffffff0, 0x6ffffff9, 0x6ffffffe, 0x6fffffff}
    if dyn[9] != 16 or dyn[5] % 16 or dyn[4] + dyn[5] > len(raw): raise ValueError('invalid dynamic entries')
    tags = {}
    for position in range(dyn[4], dyn[4] + dyn[5], 16):
        tag, data = struct.unpack_from('<qQ', raw, position)
        if tag not in allowed_tags: raise ValueError('unreviewed dynamic tag')
        if not tag: break
        tags.setdefault(tag, []).append(data)
        if tag in (1, 14, 15, 29):
            text, end = value(data); references.append((data, end, 'dynamic', tag))
            if tag == 1 and text == old: needed.append(data)
    if tags.get(5) != [strings[3]] or tags.get(10) != [strings[5]]:
        raise ValueError('section and loader dynamic string tables differ')
    for index, section in enumerate(sections):
        if section[6] != string_index: continue
        if section[1] == 6: continue
        start, size = section[4:6]
        if start + size > len(raw): raise ValueError('linked section exceeds ELF')
        if section[1] == 11:
            if section[9] != 24 or size % 24: raise ValueError('invalid dynamic symbol table')
            for position in range(start, start + size, 24):
                offset = struct.unpack_from('<I', raw, position)[0]
                references.append((offset, value(offset)[1], 'symbol', index))
        elif section[1] == 0x6ffffffe:  # GNU version requirements.
            position, seen = 0, set()
            while True:
                if position in seen or position + 16 > size: raise ValueError('invalid version requirement chain')
                seen.add(position)
                version, count, filename, auxiliary, following = struct.unpack_from('<HHIII', raw, start + position)
                if version != 1 or count > 4096: raise ValueError('unsupported version requirement')
                references.append((filename, value(filename)[1], 'version-file', index))
                offset = position + auxiliary; auxiliary_seen = set()
                for number in range(count):
                    if offset in auxiliary_seen or offset + 16 > size: raise ValueError('invalid version auxiliary chain')
                    auxiliary_seen.add(offset)
                    _, _, _, name, next_aux = struct.unpack_from('<IHHII', raw, start + offset)
                    references.append((name, value(name)[1], 'version-name', index))
                    if number + 1 < count and not next_aux: raise ValueError('truncated version auxiliary chain')
                    offset += next_aux
                if not following: break
                position += following
        else:
            raise ValueError('unreviewed section references dynamic strings')
    if len(needed) != 1 or table.count(old.encode() + b'\0') != 1:
        raise ValueError('one unambiguous matching DT_NEEDED required')
    offset = needed[0]; end = value(offset)[1]
    candidates = [(begin, finish, kind, tag) for begin, finish, kind, tag in references
                  if begin < end and offset < finish]
    if candidates != [(offset, end, 'dynamic', 1)]: raise ValueError('other dynamic string reference overlaps replacement')
    if not new or '/' in new or '\0' in new or len(new.encode()) > len(old.encode()):
        raise ValueError('replacement must be a shorter library basename')
    position = strings[4] + offset
    replacement = new.encode() + b'\0' * (end - offset - len(new.encode()))
    derived = raw[:position] + replacement + raw[position + len(replacement):]
    before, after = elf_closure.elf(raw), elf_closure.elf(derived)
    expected = dict(before); expected['needed'] = [new if name == old else name for name in before['needed']]
    if after != expected or len(derived) != len(raw): raise ValueError('independent program-header parse differs')
    return derived, {'original_sha256': expected_sha256, 'derived_sha256': hashlib.sha256(derived).hexdigest(),
        'old_needed': old, 'new_needed': new, 'file_bytes': len(raw), 'string_offset': position,
        'replacement_span_bytes': len(replacement), 'checked_string_references': len(references),
        'before': before, 'after': after, 'layout_unchanged': True,
        'original_modified': False, 'runtime_executed': False}


def repair(source, destination):
    source, destination = a.regular(source), a.checked_path(destination)
    if destination.exists(): raise ValueError('derived ELF output must be fresh')
    derived, receipt = transform(source.read_bytes(), OLD, NEW, ORIGINAL_SHA256)
    destination.write_bytes(derived)
    receipt['tool_sha256'] = a.digest(__file__)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(repair(args.input, args.output), sort_keys=True))
