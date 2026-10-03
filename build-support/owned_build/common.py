"""Exact source export for fresh owned component builds; no ref/default resolution."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def git_environment():
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_NO_REPLACE_OBJECTS='1',
               GIT_TERMINAL_PROMPT='0',GIT_ALLOW_PROTOCOL='file',GIT_OPTIONAL_LOCKS='0')
    return env


def git(repo,*args):
    return subprocess.check_output(['git','--no-replace-objects','-c','core.hooksPath=/dev/null',
                                     '-C',str(repo),*args],env=git_environment())


def inventory(root):
    result={}
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink():
            raise ValueError('Source symlink forbidden: '+str(p))
        if p.is_file():
            result[p.relative_to(root).as_posix()]=sha(p)
    return result


def inventory_digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def export_owned(repo, selection, destination):
    """Export every exact Git blob and mode, including export-ignore attributes."""
    commit=selection['commit']
    if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Source selection must be a full immutable commit')
    tree=git(repo,'rev-parse',commit+'^{tree}').decode().strip()
    if tree!=selection['tree']:
        raise ValueError('Owned source tree identity mismatch')
    entries=[];gitlinks={}
    for record in git(repo,'ls-tree','-r','-z',commit).split(b'\0'):
        if not record: continue
        info,name=record.split(b'\t',1)
        mode,kind,oid=info.decode().split()
        name=name.decode();relative=PurePosixPath(name)
        if kind=='commit' and mode=='160000' and selection.get('gitlinks',{}).get(name)==oid:
            gitlinks[name]=oid;continue
        if (kind!='blob' or mode not in ('100644','100755') or relative.is_absolute()
                or '..' in relative.parts or '\\' in name or '\n' in name):
            raise ValueError('Unsupported or unsafe selected Git entry: '+name)
        entries.append((name,mode,oid))
    if gitlinks!=selection.get('gitlinks',{}):raise ValueError('Declared source gitlink identity mismatch')
    destination.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryFile() as requests:
        requests.write(''.join(oid+'\n' for _,_,oid in entries).encode());requests.seek(0)
        process=subprocess.Popen(['git','--no-replace-objects','-C',str(repo),'cat-file','--batch'],
                                  stdin=requests,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  env=git_environment())
        try:
            for name,mode,oid in entries:
                header=process.stdout.readline().decode().split()
                if len(header)!=3 or header[:2]!=[oid,'blob']:
                    raise ValueError('Selected blob is unavailable: '+name)
                size=int(header[2]);data=process.stdout.read(size)
                if len(data)!=size or process.stdout.read(1)!=b'\n':
                    raise ValueError('Truncated Git blob')
                if hashlib.sha1(b'blob '+str(size).encode()+b'\0'+data).hexdigest()!=oid:
                    raise ValueError('Git blob identity mismatch')
                path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data);path.chmod(0o755 if mode=='100755' else 0o644)
            error=process.stderr.read()
            if process.wait()!=0: raise ValueError(error.decode(errors='replace'))
        finally:
            if process.poll() is None: process.kill();process.wait()
            process.stdout.close();process.stderr.close()
    return {**selection,'repository':str(repo),'files':len(entries),'tree_verified':True,'gitlinks':gitlinks,
            'export_method':'exact blob bytes and executable modes; no attributes/patches/ref resolution'}
