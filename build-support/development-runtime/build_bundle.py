#!/usr/bin/env python3
"""Inert assembly from exact retained inputs. Does not invoke a runtime engine."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'build-support/development-images'))
from installer import bundle
from installer.state import checked_path, digest
from elf_closure import elf

BUILD = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees')
INERT = BUILD / 'plt01-runtime/inert-002'
PODMAN = ROOT.parent / 'plt01-runtime-checks/podman-health-timer-build-001'
RUNC = ROOT.parent / 'plt01-runtime-checks/runc-build-002'
RUNC_ARCHIVE = Path('/home/revelberry/Projects/AmbisGIS/source-archives/plt01-container/obs-source/runc-64446271a17ff823ebb1b17b0b955d06/runc-1.5.1.tar.xz')
IMAGES = ROOT.parent / 'plt01-runtime-checks/images-017'
INPUTS = ROOT.parent / 'plt01-inputs-worktree/build-support/container-inputs'
CONTROL = BUILD / 'delivery-control'
PINS = {
    INERT / 'runtime-payload.json': 'd73b431af1fdb89f47196363e265be957b2eb369cf0cf107bf34514ebde9e83b',
    BUILD / 'plt01-container-inputs/payload-001/receipt.json': '6d685c53f28d75e66923f4e3c1c652398f76c41a48863caa10d3dbcf87591650',
    BUILD / 'plt01-image-inputs/payload-001/receipt.json': '24b9de32cc79a9836bc6dc82cb9d84b00a7b2bea4b23b9c7f725246170b30ce4',
    IMAGES / 'result.json': '576ab5bba01c211a2e05b06ac2a7aac4c8b9dc35c7d6b214b3ed82cce79d80ee',
    PODMAN / 'bin/podman': '42178d5a85f9dd23ab688f8c34491e20f1c57543e63d5ee9c511b4a23565c2b4',
    PODMAN / 'bin/rootlessport': '6b868441aed6c8917103eaac689b5f98a002a426701aec3931dfe6078be46ce1',
    PODMAN / 'result.json': '8123fb4804541ce686918e4984fd00e6c4adb46240e7a31a5ed2720fca99f343',
    PODMAN / 'MODIFICATIONS.txt': 'ecc8e57ccad52420cdc212293a96023c313294928c8d489a4301c9e3247efbcd',
    PODMAN / 'commands.json': 'e06aac5c5a6263d469ca53cac5304408267fadf09be94a77ab6f79c41170d2d7',
    PODMAN / 'invocation.json': '286b69204edd418d2defb008cc60ba4a3026c2589708bdb5ba893989a036f8ea',
    PODMAN / 'network.json': 'cedee92ebb75746b07714dfc0b0b1d4ee8dbed00f6b946714ac27dbd1d364d7c',
    PODMAN / 'owned-source.patch': 'f3b15a9d64ffb19acee386cfcdfb2add717993305867d0ce6c0635c4fcd2d677',
    PODMAN / 'preparation.json': '23550906b7ee3d58252c201c2c824c18c1b1cc1d207f3f64516351b0f73f64cf',
    PODMAN / 'toolchain.json': '88c9dfab2f03d59019b96d94ca119c5a3aa12cf8509c0da7547747123e19f60a',
    RUNC_ARCHIVE: 'db743b39fd7de8da88adce5a61a54529a494928cd59227fffb622f5cb4ba6ef9',
    RUNC / 'result.json': '64ac169e79dd481fb5d6488b4c32f39ffc30f1cf902c3bbb1c807916f0b9ea00',
    RUNC / 'invocation.json': '9a283834d11f89f87ce0bc74ac3ab3576b3bfdbcc31edc194e27576140f34156',
    RUNC / 'commands.json': 'e153f924399bad3ae36a0d849218278f0745eb0b957f2657fef086399a3659eb',
    RUNC / 'preparation.json': '467455a1b068ba132debaa8d27227a88fd6d06ec705b233eb40ee7d90de116ca',
    RUNC / 'toolchain.json': '88c9dfab2f03d59019b96d94ca119c5a3aa12cf8509c0da7547747123e19f60a',
    RUNC / 'network.json': '2a137fdc2855b10907cace98347210116cdb99c1f3d4a9ab1e64063b7c76626d',
    RUNC / 'owned-source.patch': '9132b82fbccf032cbf113be79a2b82d6608ea8bb4b1590400132371f4a12ec65',
    RUNC / 'bin/runc': '88a8ad522d529ad484d07631d0e55caf44f4a156fce181c4074952e2c33c49ef',
    INPUTS / 'retained-inputs.lock.json': 'b7fa4c75199a9abedc9c1a749886f8bafd79dae47ea063d0556588edad8a8271',
    INPUTS / 'python312-image-inputs.lock.json': 'fc7449babfee72a361da2ad309c463a4ec33ef89a28fbfdc2fa63e5d882bfefd',
    CONTROL / 'host-payload-correspondence-007.json': 'bb47cd1820af73a078c14d6b8a0363909c9fa7898a6d6d18b796ed8da6ab0023',
    CONTROL / 'host-binaries-007.json': '4d5264386c03cd89eee33993973182fb5d7e1ed42ba7ea3175f0888405d84c1e',
    CONTROL / 'host-sources-007.json': 'a7a4f051329cf62ba5d4f89c3d068583d1f96c386daa7ce6e188d749f5eccb5f',
}


def encoded(value): return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def safe_name(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name or name == '.':
        raise ValueError('contained normalized member required')
    return path


def regular(path, identity=None):
    path = checked_path(path)
    if not stat.S_ISREG(path.lstat().st_mode): raise ValueError('regular input required')
    if identity is not None and digest(path) != identity: raise ValueError('input hash mismatch')
    return path


class Writer:
    def __init__(self, output):
        self.root = checked_path(output)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.rows = {}

    def put(self, name, *, source=None, sha256=None, data=None, executable=False, origin=None):
        path = self.root / safe_name(name)
        if name in self.rows or path.exists(): raise ValueError('duplicate output member')
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if source is not None:
            source = regular(source, sha256)
            shutil.copyfile(source, path)
            if digest(path) != digest(source) or sha256 is not None and digest(path) != sha256:
                raise ValueError('input changed while copying')
        else:
            path.write_bytes(data)
        path.chmod(0o700 if executable else 0o600)
        self.rows[name] = {'sha256': digest(path), 'bytes': path.stat().st_size,
                           'mode': stat.S_IMODE(path.stat().st_mode), 'origin': origin}
        return path

    def document(self, name, value): return self.put(name, data=encoded(value), origin={'generated': True})


def shell_launcher(mode, *, public=False):
    # This host bootstrap shell and loader must already be trusted. In
    # particular their loading happens before these unset statements. Use no
    # caller PATH lookup, shell evaluation, rc file or inherited Python path.
    ascent = '..' if public else '../..'
    return ('''#!/usr/bin/bash
set -eu
unset LD_PRELOAD LD_AUDIT GLIBC_TUNABLES ENV BASH_ENV CDPATH
case "$0" in /*) entry="$0";; *) entry="$PWD/$0";; esac
base=$(CDPATH= cd -P -- "${entry%/*}/''' + ascent + '''" && pwd -P && printf '.')
# Preserve trailing path newlines until validation; command substitution would
# otherwise strip them and could select a different sibling bundle.
base=${base%.}
base=${base%$'\\n'}
export LC_ALL=C
case "$base" in /|*[!A-Za-z0-9_./-]*)
  printf '%s\\n' 'The owned development bundle requires an absolute ASCII path using letters, digits, underscore, dot, slash and hyphen.' >&2
  exit 125;;
esac
export LD_LIBRARY_PATH="$base/runtime/lib64"
exec "$base/runtime/engine/env" -i \\
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \\
  PYTHONHOME="$base/runtime" \\
  PYTHONPATH="$base/runtime/modules:$base/runtime/lib/python3.13/site-packages:$base/runtime/lib64/python3.13/site-packages" \\
  LD_LIBRARY_PATH="$base/runtime/lib64" \\
  PATH="$base/runtime/bin:$base/runtime/helpers" \\
  "$base/runtime/bin/python3.13" -S -s -P "$base/runtime/modules/ambisgis_runtime.py" ''' + mode + ''' "$@"
''').encode()


def package_inventory():
    rows = {}
    for receipt in (BUILD / 'plt01-container-inputs/payload-001/receipt.json',
                    BUILD / 'plt01-image-inputs/payload-001/receipt.json'):
        value = json.loads(regular(receipt, PINS[receipt]).read_bytes())
        if value['failures']: raise ValueError('failed retained package input')
        for package in value['packages']:
            for item in package['files']:
                if item['kind'] != 'file': continue
                path = Path(package['directory']) / safe_name(item['path'])
                record = {'path': str(path), 'sha256': item['sha256'], 'package': package['identity'],
                          'archive_sha256': package['archive_sha256'], 'member': item['path'],
                          'signed_mode': item['signed_mode'], 'payload_receipt': str(receipt),
                          'payload_receipt_sha256': PINS[receipt]}
                rows.setdefault(item['path'], []).append(record)
    return rows


def choose(rows, member):
    candidates = rows.get(member, [])
    identities = {r['sha256'] for r in candidates}
    if len(identities) != 1: raise ValueError('missing or ambiguous retained package file: ' + member)
    return candidates[0]


def copy_package(writer, inventory, member, destination, *, executable=False):
    row = choose(inventory, member)
    return writer.put(destination, source=Path(row['path']), sha256=row['sha256'], executable=executable, origin=row)


def add_elf_dependencies(writer, inventory):
    """Static SONAME closure of copied tools; does not run ldd or an ELF."""
    pending = [name for name in writer.rows if (writer.root / name).read_bytes()[:4] == b'\x7fELF']
    visited = set(); observations = []
    while pending:
        name = pending.pop()
        if name in visited: continue
        visited.add(name); value = elf((writer.root / name).read_bytes())
        if value.get('other_machine'): raise ValueError('unsupported host runtime ELF machine')
        if value['rpath']:
            # RPATH can outrank the deliberately pinned LD_LIBRARY_PATH.
            raise ValueError('unqualified runtime RPATH requires explicit review: ' + name)
        resolved = {}
        for needed in value['needed']:
            if '/' in needed: raise ValueError('absolute runtime DT_NEEDED requires explicit repair')
            destination = 'runtime/lib64/' + needed
            if destination not in writer.rows:
                candidates = [r for rows in inventory.values() for r in rows if Path(r['member']).name == needed]
                # Some SONAMEs are only signed links. Find the actual regular
                # file's DT_SONAME, with exact bytes from retained payloads.
                if not candidates:
                    for member, choices in inventory.items():
                        if not member.startswith('usr/lib64/') or '.so' not in Path(member).name: continue
                        row = choices[0]; raw = regular(Path(row['path']), row['sha256']).read_bytes()
                        if raw[:4] == b'\x7fELF' and needed in (elf(raw) or {}).get('soname', []): candidates.append(row)
                if len({r['sha256'] for r in candidates}) != 1:
                    raise ValueError('missing or ambiguous retained runtime SONAME: ' + needed)
                row = candidates[0]
                writer.put(destination, source=Path(row['path']), sha256=row['sha256'], origin=row)
                pending.append(destination)
            resolved[needed] = destination
        observations.append({'member': name, **value, 'resolved': resolved})
    return sorted(observations, key=lambda r: r['member'])


def host_inventory(inventory):
    pending = [Path('/usr/bin/bash'), Path('/usr/bin/newuidmap'), Path('/usr/bin/newgidmap'),
               Path('/usr/lib64/ld-linux-x86-64.so.2')]
    observed = {}; correspondence = []
    while pending:
        path = pending.pop().resolve(strict=True)
        if str(path) in observed: continue
        info = path.stat(); raw_hash = digest(path)
        matches = [r for choices in inventory.values() for r in choices if r['sha256'] == raw_hash]
        if not matches and str(path) == '/usr/lib64/libtinfo.so.6.6':
            matches = [host_tinfo_correspondence(path, raw_hash)]
        if not matches or info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
            raise ValueError('unretained or writable host bootstrap prerequisite: ' + str(path))
        try: capability = os.getxattr(path, 'security.capability').hex()
        except OSError as error:
            if error.errno not in (61, 95): raise
            capability = ''
        observed[str(path)] = {'path': str(path), 'sha256': raw_hash, 'uid': info.st_uid, 'gid': info.st_gid,
                              'mode': stat.S_IMODE(info.st_mode), 'capability_hex': capability}
        correspondence.append({'host': str(path), 'retained': matches[0]})
        for needed in elf(path.read_bytes())['needed']:
            if '/' in needed: raise ValueError('unexpected absolute host dependency')
            pending.append(Path('/usr/lib64') / needed)
    # Dynamic loader policy/cache remain explicit existing-host bootstrap trust,
    # not copied/redistributable signed payloads. Native loaded mappings pending.
    if Path('/etc/ld.so.preload').exists(): raise ValueError('unexpected host preload configuration')
    cache = Path('/etc/ld.so.cache'); info = cache.stat()
    observed[str(cache)] = {'path': str(cache), 'sha256': digest(cache), 'uid': info.st_uid, 'gid': info.st_gid,
                            'mode': stat.S_IMODE(info.st_mode), 'capability_hex': ''}
    return {'schema_version': 1, 'host_tools': sorted(observed.values(), key=lambda r: r['path']),
            'requirements': {'kernel_release': os.uname().release, 'minimum_subordinate_ids': 65536,
                             'cgroup_controllers': ['cpu', 'memory', 'pids'], 'fuse_required': False}}, correspondence


def host_tinfo_correspondence(path, raw_hash):
    """Existing host uses the separately retained FND08 ncurses successor.

    Rebind its prior signed header/payload attestation and all exact source
    files; do not silently substitute it into the selected PLT runtime libs.
    """
    records = {name: json.loads(regular(CONTROL / name, PINS[CONTROL / name]).read_bytes()) for name in
        ('host-payload-correspondence-007.json', 'host-binaries-007.json', 'host-sources-007.json')}
    package = next(r for r in records['host-payload-correspondence-007.json']['packages'] if r['name'] == 'libncurses6')
    file = next(r for r in package['files'] if r['path'] == str(path))
    if file['status'] != 'match' or file['expected_digest'] != raw_hash or file['sha256'] != raw_hash:
        raise ValueError('host tinfo signed payload correspondence differs')
    archive = next(r for r in records['host-binaries-007.json']['results'] if r['sha256'] == package['rpm_sha256'])
    regular(Path(archive['file']), archive['sha256'])
    source = next(r for r in records['host-sources-007.json']['results']
                  if r.get('disturl') == package['verification']['disturl'])
    root = Path('/home/revelberry/Projects/AmbisGIS/source-archives/fnd08-host-inputs/obs-source/ncurses-3aeb23c95bb91b4df605af490cdaa482')
    regular(root / 'directory.xml', source['listing_sha256'])
    if {p.name for p in root.iterdir()} != {'directory.xml', *(r['name'] for r in source['files'])}:
        raise ValueError('host ncurses retained source membership differs')
    for row in source['files']:
        regular(root / safe_name(row['name']), row['sha256'])
    return {'host_only': True, 'archive': archive, 'signed_file': file, 'source': source,
            'source_directory': str(root), 'verification': 'Rebound prior signed header/payload attestation; no new signature verification or source rebuild.'}


def add_owned_runc(writer, original):
    result = json.loads(regular(RUNC / 'result.json', PINS[RUNC / 'result.json']).read_bytes())
    if result['exit_code'] != 0 or result['unchanged'] != {'original': True, 'source': True, 'toolchain': True}:
        raise ValueError('Owned runc build is incomplete or changed')
    for name, identity in result['records'].items(): regular(RUNC / safe_name(name), identity)
    source = json.loads((RUNC / 'preparation.json').read_bytes())
    if not source['init_clearenv_source_unchanged']:
        raise ValueError('Native init environment isolation changed')
    invocation = json.loads((RUNC / 'invocation.json').read_bytes())
    regular(RUNC / 'build-executed.py', invocation['recipe_sha256'])
    writer.put('runtime/helpers/runc', source=RUNC / 'bin/runc', sha256=PINS[RUNC / 'bin/runc'], executable=True,
        origin={'owned_build': str(RUNC), 'result_sha256': PINS[RUNC / 'result.json'], 'replaced_retained_input': original})
    prefix = 'runtime/notices/runc-owned-build/'
    for name in ('result.json', 'invocation.json', 'commands.json', 'preparation.json', 'toolchain.json', 'network.json', 'owned-source.patch'):
        writer.put(prefix + name, source=RUNC / name, sha256=PINS[RUNC / name], origin={'original_build_record': True})
    writer.put(prefix + 'build-executed.py', source=RUNC / 'build-executed.py', sha256=invocation['recipe_sha256'], origin={'owned_recipe': True})
    writer.put(prefix + 'runc-1.5.1.tar.xz', source=RUNC_ARCHIVE, sha256=PINS[RUNC_ARCHIVE], origin={'exact_retained_source_with_vendor': True})
    names = ['LICENSE', 'libcontainer/ambisgis_environment_test.go'] + sorted(n for n in source['patched']
        if n.startswith('vendor/') and Path(n).name.lower().startswith(('license', 'copying', 'notice')))
    for name in names:
        row = source['patched'][name]
        if row['kind'] != 'file': raise ValueError('Unexpected source notice member')
        writer.put(prefix + 'source/' + name, source=RUNC / 'source' / safe_name(name), sha256=row['sha256'],
                   origin={'owned_runc_source': name, 'source_archive_sha256': PINS[RUNC_ARCHIVE]})
    writer.put(prefix + 'MODIFICATIONS.txt', data=(
        'AmbisGIS development packaging modification, 2026-10-03.\n'
        'runc 1.5.1 retains Apache-2.0 and its original notices. Exact vendor notices are included separately.\n'
        'The sealed init bootstrap now carries only the owned launcher-validated LD_LIBRARY_PATH in addition to the existing GOMAXPROCS.\n'
        'Later native init Clearenv and container environment handling remain unchanged. See owned-source.patch and preparation.json.\n'
        'The source archive, patch and build hashes identify this derived binary; no Git commit value is invented.\n'
        'Build-001 is excluded for misleading revision metadata; this artifact is corrected build-002.\n'
        'Only the pure bootstrap environment unit was executed. Runtime installation/security and distribution approval remain pending.\n'
    ).encode(), origin={'modified_source_notice': True})


def add_owned_podman(writer):
    """Bind the reviewed finite native health-timer successor and exact source."""
    result = json.loads(regular(PODMAN / 'result.json', PINS[PODMAN / 'result.json']).read_bytes())
    if result['exit_code'] != 0 or result['unchanged'] != {
            'source': True, 'prior_source': True, 'baseline': True, 'toolchain': True}:
        raise ValueError('Owned Podman health-timer build is incomplete or changed')
    for name, identity in result['records'].items(): regular(PODMAN / safe_name(name), identity)
    invocation = json.loads((PODMAN / 'invocation.json').read_bytes())
    regular(PODMAN / 'build-executed.py', invocation['recipe_sha256'])
    regular(Path(__file__).with_name('podman_health_timer_build.py'), invocation['recipe_sha256'])
    preparation = json.loads((PODMAN / 'preparation.json').read_bytes())
    if preparation['vendor_unchanged'] is not True:
        raise ValueError('Existing Podman vendor source changed')
    for name in ('podman', 'rootlessport'):
        destination = 'runtime/engine/podman' if name == 'podman' else 'runtime/helpers/rootlessport'
        writer.put(destination, source=PODMAN / 'bin' / name, sha256=PINS[PODMAN / 'bin' / name], executable=True,
                   origin={'owned_build': str(PODMAN), 'result_sha256': PINS[PODMAN / 'result.json']})
    prefix = 'runtime/notices/podman-owned-build/'
    for name in ('result.json', *result['records']):
        writer.put(prefix + name, source=PODMAN / name, sha256=PINS[PODMAN / name],
                   origin={'original_build_record': True, 'producer': str(PODMAN)})
    writer.put(prefix + 'build-executed.py', source=PODMAN / 'build-executed.py', sha256=invocation['recipe_sha256'],
               origin={'owned_recipe': True, 'producer': str(PODMAN)})
    for name in ('LICENSE', 'libpod/ambisgis_oci_environment.go', 'libpod/ambisgis_oci_environment_test.go',
                 'pkg/systemd/dbus.go', 'pkg/systemd/ambisgis_user_socket.go', 'pkg/systemd/ambisgis_user_socket_test.go',
                 'libpod/healthcheck_linux.go', 'libpod/ambisgis_health_timer.go', 'libpod/ambisgis_health_timer_test.go'):
        row = preparation['patched'][name]
        if row['kind'] != 'file': raise ValueError('Unexpected owned Podman source member')
        writer.put(prefix + 'source/' + name, source=PODMAN / 'source' / name, sha256=row['sha256'],
                   origin={'owned_podman_source': name, 'producer': str(PODMAN)})
    for index, row in enumerate(preparation['existing_patches']):
        writer.put(prefix + 'prior-patches/' + str(index) + '-' + Path(row['file']).name,
                   source=Path(row['file']), sha256=row['sha256'],
                   origin={'retained_prior_patch': True, 'source': row['file']})


def assemble(output):
    os.umask(0o077)
    for path, sha in PINS.items(): regular(path, sha)
    writer = Writer(output); inventory = package_inventory()
    payload = json.loads((INERT / 'runtime-payload.json').read_bytes())
    actual = {str(p.relative_to(INERT)) for p in (INERT / 'runtime').rglob('*') if p.is_file()}
    if actual != {r['path'] for r in payload['files']}: raise ValueError('retained runtime payload membership differs')
    for row in payload['files']:
        path = row['path']; destination = path
        if path == 'runtime/bin/runc':
            regular(INERT / path, row['sha256'])
            add_owned_runc(writer, row)
            continue
        if path.startswith('runtime/bin/') and Path(path).name != 'python3.13':
            destination = 'runtime/helpers/' + Path(path).name
        writer.put(destination, source=INERT / path, sha256=row['sha256'],
                   executable=path.startswith('runtime/bin/'), origin=row)
    add_owned_podman(writer)
    copy_package(writer, inventory, 'usr/bin/env', 'runtime/engine/env', executable=True)
    copy_package(writer, inventory, 'usr/share/licenses/coreutils/COPYING', 'runtime/notices/licenses/coreutils/COPYING')
    copy_package(writer, inventory, 'usr/bin/systemd-run', 'runtime/engine/systemd-run', executable=True)
    # runc's native rootless DetectUID invokes this exact retained helper via
    # the private PATH. It reads the existing user bus; no UID is substituted.
    copy_package(writer, inventory, 'usr/bin/busctl', 'runtime/helpers/busctl', executable=True)
    observations = add_elf_dependencies(writer, inventory)
    prerequisites, host_sources = host_inventory(inventory)
    for source in sorted((ROOT / 'installer').glob('*.py')):
        writer.put('runtime/modules/installer/' + source.name, source=source, origin={'owned_source': str(source), 'sha256': digest(source)})
    source = Path(__file__).with_name('ambisgis_runtime.py')
    writer.put('runtime/modules/ambisgis_runtime.py', source=source, origin={'owned_source': str(source), 'sha256': digest(source)})
    gpl = ROOT.parent / 'geodb-integration-worktree/COPYING'
    writer.put('runtime/notices/ambisgis/COPYING', source=gpl,
               sha256='2ca9503d76d1ffab14f599b4741382eec11face60ad1f0d7a41897809003a286',
               origin={'existing_first_party_policy': 'GPL-3.0-or-later', 'source': str(gpl)})
    writer.put('runtime/notices/ambisgis/NOTICE.txt', data=(
        'AmbisGIS owned installer and runtime adapter: GPL-3.0-or-later, following the existing first-party policy.\n'
        'Exact corresponding Python sources are carried under runtime/modules; build recipe/source hashes are in custody.json.\n'
        'This development artifact is not an approved product distribution. Original component notices remain separately retained.\n').encode(), origin={'existing_policy': True})
    # Native health timers use the owned D-Bus helper. Omitting the obsolete
    # PATH scope launcher selects netavark's retained direct DNS daemon branch;
    # the explicit bundle profile rejects any replacement in its lookup paths.
    for mode in ('ambisgis', 'podman', 'compose', 'newuidmap', 'newgidmap', 'healthcheck-timer'):
        writer.put(('bin/' if mode == 'ambisgis' else 'runtime/bin/') + mode,
                   data=shell_launcher(mode, public=mode == 'ambisgis'), executable=True, origin={'generated_launcher': mode})
    program_source = ROOT / 'deploy/development/journey_probe.py'
    programs = [ast.literal_eval(node.value) for node in ast.parse(program_source.read_text()).body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'INTERNAL_CLIENT' for t in node.targets)]
    if len(programs) != 1: raise ValueError('diagnostic program binding missing')
    permission_source = ROOT / 'deploy/development/catalog_permission_probe.py'
    writer.put('runtime/configuration/catalog-permission-source.py', source=permission_source,
               origin={'owned_acceptance_program': str(permission_source), 'sha256': digest(permission_source)})
    dns_source = ROOT / 'deploy/development/dns_wire_probe.py'
    writer.put('runtime/configuration/dns-wire-source.py', source=dns_source,
               origin={'owned_acceptance_program': str(dns_source), 'sha256': digest(dns_source)})
    writer.document('runtime/configuration/ordinary-command.json', {'source_sha256': digest(program_source),
                      'internal_client_sha256': hashlib.sha256(programs[0].encode()).hexdigest(),
                      'catalog_permission_sha256': digest(permission_source),
                      'dns_wire_sha256': digest(dns_source)})
    writer.document('runtime/configuration/host-prerequisites.json', prerequisites)
    for name in ('retained-inputs.lock.json', 'python312-image-inputs.lock.json'):
        writer.put('runtime/notices/retained-locks/' + name, source=INPUTS / name, sha256=PINS[INPUTS / name],
                   origin={'original_input_lock': True, 'qualification': 'Custody only, original runtime hold wording preserved.'})
    writer.document('runtime/configuration/elf-inputs.json', {'members': observations, 'runtime_executed': False,
        'scope': 'Static selected runtime DT_NEEDED/SONAME inputs; actual loader mappings, symbol versions and ABI pending.'})
    # These custody records bind the exact retained inputs, not an assertion
    # that every shipped package or host service has been qualified here.
    custody = {'schema_version': 1, 'inputs': [{'path': str(p), 'sha256': s} for p, s in PINS.items()],
               'source_files': {str(p.relative_to(ROOT)): digest(p) for p in (Path(__file__).resolve(), source)},
               'host_correspondence': host_sources, 'files': copy_rows(writer.rows),
               'limitations': ['Host shell/loader/startup policy are trusted before this adapter can clear environment.',
                 'Host systemd user service, SELinux policy, kernel/cgroup delegation remain actual host prerequisites.',
                 'No runtime, engine, mapping helper, transient unit or installer was executed.',
                 'vfs storage is selected; space and throughput are unmeasured.',
                 'Targeted probe remains held; full runtime security and installation acceptance are not passed.']}
    writer.document('runtime/configuration/custody.json', custody)
    result = json.loads((IMAGES / 'result.json').read_bytes())
    images = {}
    for role, row in result['images'].items():
        writer.put('images/' + row['path'], source=IMAGES / row['path'], sha256=row['sha256'], origin={'image_result': str(IMAGES / 'result.json')})
        images[role] = {'archive': 'images/' + row['path'], 'archive_sha256': row['sha256'], 'reference': row['reference'],
                        'image_id': row['image_id'], 'source_manifest_sha256': row['source_manifest_sha256']}
    writer.put('source-manifest.json', source=IMAGES / 'source-manifest.json', sha256=result['source_manifest_sha256'], origin={'image_sources': True})
    def ref(name): return {'path': name, 'sha256': digest(writer.root / name)}
    roots = ['bin', 'runtime']
    closure = {'schema_version': 1, 'roots': roots,
               'files': [ref(name) for name in sorted(writer.rows) if name.split('/')[0] in roots],
               'directories': sorted(str(p.relative_to(writer.root)) for base in roots for p in
                    (writer.root / base).rglob('*') if p.is_dir()), 'symlinks': []}
    writer.document('runtime-files.json', closure)
    manifest = {'schema_version': 1, 'kind': 'ambisgis.development-bundle', 'target': {'os': 'linux', 'architecture': 'x86_64'},
                'product_revision': result['platform_revision'], 'source_manifest': ref('source-manifest.json'),
                'runtime': {'path_profile': 'owned-health-timer-ascii-v1', 'dns_profile': 'native-direct-v1',
                    'podman': ref('runtime/bin/podman'), 'compose': ref('runtime/bin/compose'),
                    'environment': {'PATH': ['runtime/bin', 'runtime/helpers'], 'LD_LIBRARY_PATH': ['runtime/lib64'],
                        'PYTHONPATH': ['runtime/modules', 'runtime/lib/python3.13/site-packages', 'runtime/lib64/python3.13/site-packages']},
                    'files_manifest': ref('runtime-files.json'), 'prerequisites': ref('runtime/configuration/host-prerequisites.json')},
                'images': images}
    writer.document('bundle.json', manifest)
    bundle.load(writer.root / 'bundle.json', digest(writer.root / 'bundle.json'))
    writer.document('assembly-result.json', {'schema_version': 1, 'bundle_sha256': digest(writer.root / 'bundle.json'),
        'files_manifest_sha256': digest(writer.root / 'runtime-files.json'), 'assembler_sha256': digest(Path(__file__)),
        'runtime_regular_files': len(closure['files']), 'static_elf_members': len(observations),
        'host_prerequisites': len(prerequisites['host_tools']), 'runtime_executed': False,
        'full_installation_acceptance': False, 'distribution_approved': False})
    return writer.root / 'assembly-result.json'


def copy_rows(rows): return {name: dict(value) for name, value in sorted(rows.items())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(assemble(parser.parse_args().output))
