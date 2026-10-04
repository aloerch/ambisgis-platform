"""Project twelve retained glibc C.utf8 files; never read host locale data.

Only inert files and reviewed receipts are read. RPM parsing/extraction remains
the separately reviewed container-inputs producer's job. No subprocess runs.
"""
from pathlib import Path
import hashlib
import stat
import tarfile

import assemble as a

PREFIX = 'usr/lib/locale/C.utf8/'
CATEGORIES = ('LC_ADDRESS', 'LC_COLLATE', 'LC_CTYPE', 'LC_IDENTIFICATION',
              'LC_MEASUREMENT', 'LC_MESSAGES/SYS_LC_MESSAGES', 'LC_MONETARY',
              'LC_NAME', 'LC_NUMERIC', 'LC_PAPER', 'LC_TELEPHONE', 'LC_TIME')


def exact_file(path, sha256):
    return a.reference({'path': str(path), 'sha256': sha256})


def unique(rows, key):
    result = {}
    for row in rows:
        name = row[key]
        if name in result:
            raise ValueError('Duplicate locale inventory entry')
        result[name] = row
    return result


def validate_system(system, bindings):
    refs = []
    for name, binding in bindings.items():
        row = system.get(name, {})
        if (row.get('kind') != 'file' or row.get('file', {}).get('sha256') != binding['sha256']
                or row.get('origin') != binding['archive_sha256'] + ':' + name):
            raise ValueError('Locale matching libc or complete notice binding differs')
        refs.append(exact_file(row['file']['path'], binding['sha256']))
    return refs


def validate_payload(root, contract, audit, receipt):
    """Validate only the fixed selection against signed headers and actual bytes.

    Callers first bind the complete audit/receipt bytes. This pure/file-reading
    layer is independently exercised with synthetic package fixtures.
    """
    root = a.checked_path(root)
    expected = contract['members']
    if set(expected) != {PREFIX + name for name in CATEGORIES}:
        raise ValueError('Locale selection must contain exactly twelve categories')
    if (audit.get('failures') != [] or audit.get('host_modified') is not False
            or audit.get('network_used') is not False or len(audit.get('packages', [])) != 1):
        raise ValueError('Locale header audit failed or is not a single package')
    if (receipt.get('failures') != [] or receipt.get('package_code_executed') is not False
            or receipt.get('symlinks_materialized') is not False
            or len(receipt.get('packages', [])) != 1):
        raise ValueError('Locale payload must be successful inert extraction')
    signed, package = audit['packages'][0], receipt['packages'][0]
    if signed.get('scripts_executed') is not False or receipt.get('host_modified') is not False:
        raise ValueError('Locale producer must not run scripts or change host state')
    for row in (signed, package):
        if (row['identity'] != contract['identity']
                or row['archive_sha256'] != contract['binary']['sha256']):
            raise ValueError('Locale package identity differs')
    verification = signed['signed_verification']
    if (verification['signed_header_sha256'] != contract['binary']['signed_header_sha256']
            or verification['source_build_disturl'] != contract['source']['disturl']
            or verification['source_rpm'] != Path(contract['source']['path']).name
            or signed['payload']['filedigestalgo'] != 8):
        raise ValueError('Locale signed source/header provenance differs')
    identity = contract['identity']
    dirname = identity['name'] + '-' + identity['version'] + '-' + identity['release'] + '.' + identity['arch']
    directory = a.checked_path(root / dirname)
    if a.checked_path(package['directory']) != directory:
        raise ValueError('Locale package directory escapes selected payload')
    headers = unique(signed['files'], 'path')
    payload = unique(package['files'], 'path')
    selected = {name for name, row in payload.items()
                if name.startswith(PREFIX) and row['kind'] != 'directory'}
    if selected != set(expected):
        raise ValueError('Locale payload category membership differs')
    # Directory membership is inspected without following any symlink. Extra
    # categories/files cannot disappear merely by rewriting a payload receipt.
    locale_root = a.checked_path(directory / PREFIX)
    observed = set()
    for path in locale_root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Locale payload contains a symbolic link')
        if not path.is_dir():
            observed.add(str(path.relative_to(directory)))
    if observed != set(expected):
        raise ValueError('Locale file membership differs')
    rows = {}
    for name, wanted in expected.items():
        h, entry = headers.get('/' + name, {}), payload[name]
        if (h.get('filemodes') != (stat.S_IFREG | 0o644) or h.get('fileflags') != 0
                or h.get('filelinktos') or h.get('filecaps')
                or h.get('fileusername') != 'root' or h.get('filegroupname') != 'root'
                or h.get('filedigests') != wanted['sha256']
                or h.get('filesizes') != wanted['bytes']):
            raise ValueError('Locale signed member differs')
        if (entry.get('kind') != 'file' or entry.get('sha256') != wanted['sha256']
                or entry.get('bytes') != wanted['bytes']
                or entry.get('signed_mode') != oct(stat.S_IFREG | 0o644)
                or entry.get('materialized_mode') != '0600'):
            raise ValueError('Locale extracted member differs')
        path = exact_file(directory / name, wanted['sha256'])
        if path.stat().st_size != wanted['bytes'] or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError('Locale extracted file size/mode differs')
        rows[name] = {'kind': 'file', 'mode': 0o644,
                      'file': {'path': str(path), 'sha256': wanted['sha256']},
                      'origin': contract['binary']['sha256'] + ':' + name}
    return rows


def select(work, custody, payload_root, system, notice_output):
    """Verify production custody and return mapped entries plus full references."""
    contract_path = Path(__file__).with_name('locale-inputs.json')
    contract = a.document(contract_path)
    root = a.checked_path(payload_root)
    receipt_path = exact_file(root / 'receipt.json', contract['payload']['sha256'])
    audit_path = exact_file(root.parent / contract['payload']['audit_sibling'],
                           contract['payload']['audit_sha256'])
    receipt, audit = a.document(receipt_path), a.document(audit_path)
    if receipt['static_audit_sha256'] != a.digest(audit_path):
        raise ValueError('Locale extraction is not bound to its header audit')
    refs = [contract_path, receipt_path, audit_path,
            exact_file(root.parent / contract['payload']['producer_result_sibling'],
                       contract['payload']['producer_result_sha256']),
            exact_file(custody / contract['binary']['path'], contract['binary']['sha256']),
            exact_file(custody / contract['source']['path'], contract['source']['sha256'])]
    for name, sha256 in contract['historical_receipts'].items():
        refs.append(exact_file(work / 'delivery-control' / name, sha256))
    for item in contract['source_receipts']:
        refs.append(exact_file(work / item['path'], item['sha256']))
    refs += validate_system(system, contract['system_bindings'])
    rows = validate_payload(root, contract, audit, receipt)
    archive_path = exact_file(custody / contract['notice_source']['path'],
                              contract['notice_source']['sha256'])
    refs.append(archive_path)
    notice_bytes = {}
    if {Path(name).name for name in contract['notice_source']['members']} != {'COPYING.LESSERv2', 'unicode-license.txt'}:
        raise ValueError('Complete LGPL and Unicode notices required')
    with tarfile.open(archive_path) as archive:
        for name, sha256 in contract['notice_source']['members'].items():
            matches = [member for member in archive.getmembers() if member.name == name]
            if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 100000:
                raise ValueError('Exact bounded locale source notice required')
            raw = archive.extractfile(matches[0]).read()
            if hashlib.sha256(raw).hexdigest() != sha256:
                raise ValueError('Locale source notice differs')
            notice_bytes[name] = raw
    notice_output = a.checked_path(notice_output)
    notice_output.mkdir(mode=0o700, exist_ok=False)
    for name, raw in notice_bytes.items():
        path = notice_output / Path(name).name
        with path.open('xb') as stream:
            stream.write(raw)
        path.chmod(0o600)
        rows['opt/ambisgis/notices/glibc-locale/' + path.name] = {
            'kind': 'file', 'mode': 0o644,
            'file': {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()},
            'origin': contract['notice_source']['sha256'] + ':' + name}
    provenance = [{'path': str(path), 'sha256': a.digest(path)} for path in refs]
    return rows, provenance
