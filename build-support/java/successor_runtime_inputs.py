"""Strict bridge from the FND08 owned-source producer to existing WAR inspection.

This does not certify FND08 completion or replace the historical recipe verifier.
Callers explicitly select this receipt schema and still pin the actual WAR/profile.
"""
import json
from pathlib import Path, PurePosixPath
from combined_logging_probe import inspect_war
from compatibility import verify_network_receipt
from resolution import sha

EXPECTED = {
    'geotools': {'repository_id':1376927869,'commit':'3363c3d4ae8adfe3ed2024c27f92ec63855093be','tree':'ebb65f687763ce40445eb02f6ce710dc1eaa1e00'},
    'geoserver': {'repository_id':1376927947,'commit':'fd2fe1dfcc78fa974bdb81673872879336312077','tree':'c12018e88493a351c60c370f2a43894701acf995'},
    'geowebcache': {'repository_id':1376927892,'commit':'b4e9a30c8e2be00b9aa87fb17324efa8e489ac22','tree':'8df655d13b9955776fe1532dfb27fac64612a772'}}


def regular(root, relative):
    parts=PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or '\\' in relative: raise ValueError('unsafe producer artifact path')
    path=root/parts
    if not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('producer artifact must be a regular file')
    return path


def packaged_classpath(build, output):
    build=Path(build).resolve();result_path=regular(build,'result.json');result=json.loads(result_path.read_text())
    if (result.get('result_exit_code')!=0 or result.get('build_exit_code')!=0
            or result.get('purpose')!='new owned source producer' or result.get('source_successor')!=EXPECTED
            or result.get('source_files_unchanged') is not True):
        raise ValueError('require exact successful owned-source producer receipt')
    roots=result['preparation']['owned_roots']
    if set(roots)!=set(EXPECTED):raise ValueError('unexpected owned producer roots')
    for name,pin in EXPECTED.items():
        if roots[name].get('tree_verified') is not True or any(roots[name].get(key)!=value for key,value in pin.items()):
            raise ValueError('source custody binding differs')
    network=regular(build,'network-denial.json')
    if result['network']['path']!=str(network) or sha(network)!=result['network']['sha256']:
        raise ValueError('producer network receipt differs')
    verify_network_receipt(network,result['build_exit_code'])
    source_manifest=regular(build,'source-inputs.json')
    if sha(source_manifest)!=result['source_inputs_sha256']:raise ValueError('source input manifest differs')
    source_root=build/'work/source';sources=json.loads(source_manifest.read_text())
    if not sources:raise ValueError('producer source inventory empty')
    for path,digest in sources.items():
        if sha(regular(source_root,path))!=digest:raise ValueError('producer source bytes changed')
    known={}
    for row in result['artifacts']['built']:
        path=regular(source_root,row['path'])
        if sha(path)!=row['sha256'] or path.stat().st_size!=row['bytes']:raise ValueError('producer artifact changed')
        known.setdefault(path.name,set()).add(row['sha256'])
    retained=regular(build,'retained-inputs.json')
    if sha(retained)!=result['retained_inputs_sha256']:raise ValueError('retained producer inventory differs')
    for row in json.loads(retained.read_text()):known.setdefault(PurePosixPath(row['maven_path']).name,set()).add(row['sha256'])
    war=regular(source_root,'geoserver/src/web/app/target/geoserver.war');before=sha(war)
    if result['artifacts']['war']!=str(war) or result['artifacts']['war_sha256']!=before:
        raise ValueError('producer WAR binding differs')
    inventory=inspect_war(war,known,output/'lib')
    if sha(war)!=before:raise ValueError('producer WAR changed during inspection')
    inventory.update(war_path=str(war),war_sha256=before,build_receipt_path=str(result_path),
                     build_receipt_sha256=sha(result_path),source_files_reverified=len(sources),
                     source_successor=EXPECTED,receipt_schema='FND08 owned source producer')
    return inventory
