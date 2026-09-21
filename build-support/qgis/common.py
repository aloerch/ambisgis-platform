"""Receipt and integrity helpers for the bounded F02-04 build."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1]
COMMIT = '1a4cda5f2620e7374e5926fc955a7d2d06493e15'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')


def inventory(root):
    root = Path(root)
    rows = []
    for p in sorted(root.rglob('*')):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            rows.append({'path':rel, 'link':os.readlink(p)})
        elif p.is_file():
            rows.append({'path':rel, 'bytes':p.stat().st_size, 'sha256':sha(p)})
    return rows


def verify_inventory(root, rows):
    normalized=[]
    for row in rows:
        if 'link' in row:
            normalized.append({'path':row['path'],'link':row['link']})
        else:
            normalized.append({'path':row['path'],'bytes':row.get('bytes',row.get('size')),'sha256':row['sha256']})
            if 'mode' in row:
                require(oct((Path(root)/row['path']).stat().st_mode & 0o777)==row['mode'], 'Input mode changed')
    require(sorted(inventory(root),key=lambda row:row['path']) == sorted(normalized,key=lambda row:row['path']), 'Retained prefix changed: '+str(root))


def environment(output, native, support=None, spatial=None):
    output, native = Path(output), Path(native)
    paths = [native]
    if support:
        paths.insert(0, Path(support)/'usr')
    if spatial:
        paths.insert(0, Path(spatial))
    env = {'PATH':':'.join(str(p/'bin') for p in paths)+':/usr/bin:/bin',
           'HOME':str(output/'home'), 'TMPDIR':str(output/'tmp'),
           'XDG_CACHE_HOME':str(output/'cache'), 'XDG_CONFIG_HOME':str(output/'config'),
           'XDG_DATA_HOME':str(output/'data'), 'LANG':'C.UTF-8', 'LC_ALL':'C.UTF-8',
           'PYTHONNOUSERSITE':'1', 'PYTHONDONTWRITEBYTECODE':'1',
           'PROJ_NETWORK':'OFF', 'PROJ_DATA':str((Path(spatial) if spatial and (Path(spatial)/'share/proj/proj.db').exists() else native)/'share/proj'),
           'GDAL_DATA':str((Path(spatial) if spatial else native)/'share/gdal'),
           'GDAL_DRIVER_PATH':'disable', 'QT_QPA_PLATFORM':'offscreen',
           'QT_LOGGING_RULES':'qt.qpa.*=false', 'CC':'/usr/bin/gcc-15','CXX':'/usr/bin/g++-15',
           'CCACHE_DISABLE':'1', 'PIP_NO_INDEX':'1', 'PIP_CONFIG_FILE':'/dev/null',
           'LD_LIBRARY_PATH':':'.join(str(p/s) for p in paths for s in ('lib','lib64')),
           'PKG_CONFIG_PATH':':'.join(str(p/s/'pkgconfig') for p in paths for s in ('lib','lib64'))}
    if support:
        env['PYTHONPATH'] = ':'.join(str(Path(support)/p) for p in ('usr/lib64/python3.13/site-packages','usr/lib/python3.13/site-packages'))
        env['QT_PLUGIN_PATH'] = str(Path(support)/'usr/lib64/qt5/plugins')
        env['PATH'] = str(Path(support)/'usr/lib64/qt5/bin')+':'+env['PATH']
    for key in ('HOME','TMPDIR','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME'):
        Path(env[key]).mkdir(parents=True,exist_ok=True)
    return env


def run(command, cwd, env, output, name, offline=True):
    command = [str(x) for x in command]
    argv = command
    if offline:
        argv = [sys.executable,str(PLATFORM/'build-support/postgis/offline_exec.py'),
                '--evidence',str(output/(name+'-network.json')),'--',*command]
    started = datetime.now(timezone.utc).isoformat()
    with (output/(name+'.log')).open('xb') as f:
        result = subprocess.run(argv,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
    save(output/(name+'-command.json'),{'argv':argv,'cwd':str(cwd),'environment':env,
         'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),
         'exit_code':result.returncode,'log_sha256':sha(output/(name+'.log'))})
    require(result.returncode==0, name+' failed; see '+str(output/(name+'.log')))
    if offline:
        proof=json.loads((output/(name+'-network.json')).read_text())
        require(proof.get('command_exit_code')==0 and proof.get('status')=='completed'
                and proof.get('command')==command and proof.get('kernel_state',{}).get('no_new_privs')==1
                and proof.get('kernel_state',{}).get('seccomp_mode')==2 and len(proof.get('probes',[]))==4
                and [p.get('family') for p in proof['probes']]==['AF_INET','AF_INET6','AF_UNIX','AF_UNIX']
                and all(p['passed'] for p in proof['probes']), 'Network enforcement failed')


def tools_record(env):
    import shutil
    rows=[]
    for name in ('python3','gcc-15','g++-15','cmake','ninja','ld','ld.bfd','ar','pkg-config','bison','flex','perl'):
        path=shutil.which(name,path=env['PATH'])
        require(path, 'Missing build tool '+name)
        p=Path(path).resolve()
        rows.append({'name':name,'path':path,'resolved':str(p),'sha256':sha(p),
                     'version':subprocess.run([path,'--version'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.splitlines()[:2],
                     'custody':'observed host tool, source/bootstrap closure unresolved'})
    return rows


def verify_historical(native):
    """Recover trust from the merged, hashed native archive, not a new snapshot."""
    import tarfile
    specification=json.loads((HERE/'source-inputs.json').read_text())
    for key in ('native_inputs_manifest','historical_native_receipt'):
        ref=specification[key]
        require(sha(HERE/ref['path'])==ref['sha256'],'Historical manifest/receipt changed')
    historical=json.loads((HERE/specification['historical_native_receipt']['path']).read_text())
    ref=historical['output_archive']
    workspace=Path(native).resolve().parents[3]
    archive=Path(ref['path'].replace('<workspace>',str(workspace)))
    require(archive.is_file() and archive.stat().st_size==ref['bytes'] and sha(archive)==ref['sha256'],
            'Historical native prefix archive changed')
    expected=[]
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            rel=Path(m.name)
            require(rel.parts[0]=='prefix' and '..' not in rel.parts,'Invalid historical archive member')
            path=str(Path(*rel.parts[1:]))
            if m.issym():expected.append({'path':path,'link':m.linkname})
            elif m.isfile() or m.islnk():
                with t.extractfile(m) as f:
                    data=f.read();h=hashlib.sha256(data).hexdigest()
                expected.append({'path':path,'bytes':len(data),'sha256':h})
            else:require(m.isdir(),'Unexpected historical archive entry type')
    verify_inventory(native, sorted(expected,key=lambda row:row['path']))
    return {'archive':str(archive),'sha256':ref['sha256'],'verified_files':len(expected)}


def verify_selected(native, spatial, support, support_inventory=None):
    """Require the reviewed selected profile and successful producer evidence."""
    profile=json.loads((HERE/'profile-inputs.json').read_text())
    require(profile['qgis_commit']==COMMIT,'Wrong profile source')
    for name,row in profile['references'].items():
        path=Path(row['path'])
        require(path.is_file() and not path.is_symlink() and sha(path)==row['sha256'],
                'Selected profile reference changed: '+name)
    refs=profile['references']
    inv=Path(refs['support_inventory']['path'])
    require(Path(support).resolve()==Path(json.loads(inv.read_text())['prefix']).resolve(),'Wrong support prefix')
    if support_inventory is not None: require(Path(support_inventory).resolve()==inv.resolve(),'Unselected support inventory')
    require(sha(Path(support)/'support-inputs.json')==sha(HERE/'support-inputs.json'),'Supporting package selection changed')
    verify_inventory(support,json.loads(inv.read_text())['files'])
    manifest=Path(refs['spatial_manifest']['path']);result=Path(refs['spatial_success']['path'])
    receipt=json.loads(result.read_text());values=json.loads(manifest.read_text())
    require(not (result.parent/'failure.json').exists() and receipt['state']=='native-profile-built'
            and receipt['manifest_sha256']==sha(manifest),'Selected spatial producer did not succeed')
    require(Path(spatial).resolve()==Path(values['prefix']).resolve(),'Wrong selected spatial prefix')
    verify_inventory(spatial,values['files'])
    return {'profile_sha256':sha(HERE/'profile-inputs.json'),'historical_authority':verify_historical(native)}
