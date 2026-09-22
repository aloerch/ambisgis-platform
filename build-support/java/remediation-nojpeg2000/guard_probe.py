"""Execute actual production guard classes against retained servlet fixtures offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
HERE = Path(__file__).resolve().parent
TASK = Path('/home/revelberry/Projects/AmbisGIS')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main(args):
    out=args.output.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    result={'result_exit_code':1,'scope':'actual production servlet guard plus Spring request fixture; not live HTTP acceptance'}
    try:
        java=TASK/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1/bin'
        m2=TASK/'build-worktrees/java-gmt-remediation/aggregate-02/fresh-m2'
        names=['javax/servlet/javax.servlet-api/3.1.0/javax.servlet-api-3.1.0.jar',
               'org/springframework/spring-test/5.3.39/spring-test-5.3.39.jar',
               'org/springframework/spring-core/5.3.39/spring-core-5.3.39.jar',
               'org/springframework/spring-jcl/5.3.39/spring-jcl-5.3.39.jar',
               'org/springframework/spring-web/5.3.39/spring-web-5.3.39.jar',
               'org/springframework/spring-beans/5.3.39/spring-beans-5.3.39.jar']
        result['inputs']={name:sha(m2/name) for name in names}
        source=out/'sources';source.mkdir();classes=out/'classes';classes.mkdir();(out/'tmp').mkdir()
        files=[]
        for name in ['NoJpeg2000Policy.java','NoJpeg2000Filter.java','NoJpeg2000GuardWitness.java']:
            shutil.copyfile(HERE/name,source/name);files.append(source/name)
        # Compile the two real changed controllers against the exact retained parent WAR libraries.
        repairs=json.loads((HERE/'geoserver-repairs.json').read_text())
        for row in repairs:
            if row['path'].endswith('.java'):
                path=source/Path(row['path']).name;path.write_text(row['after']);files.append(path)
        result['sources']={p.name:sha(p) for p in files}
        production=TASK/'build-worktrees/java-gmt-remediation/geonode-02/lib'
        libraries=sorted(production.glob('*.jar'))
        if len(libraries)!=367:raise ValueError('parent WAR library inventory changed')
        result['parent_libraries']={p.name:sha(p) for p in libraries}
        cp=os.pathsep.join([*(str(m2/name) for name in names),*(str(p) for p in libraries)])
        commands=[[str(java/'javac'),'-cp',cp,'-d',str(classes),*[str(p) for p in files]],
                  [str(java/'java'),'-Djava.io.tmpdir='+str(out/'tmp'),'-cp',str(classes)+os.pathsep+cp,'NoJpeg2000GuardWitness',str(out/'tree-input')]]
        result['commands']=[]
        sys.path.insert(0,str(HERE.parent));from compatibility import verify_network_receipt
        for index,command in enumerate(commands):
            proof=out/('network-'+str(index)+'.json')
            full=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(proof),'--',*command]
            executed=subprocess.run(full,capture_output=True,text=True,timeout=120)
            log=out/(str(index)+'.log');log.write_text(executed.stdout+executed.stderr)
            row={'command':full,'exit_code':executed.returncode,'log_sha256':sha(log),'network':verify_network_receipt(proof,executed.returncode)}
            result['commands'].append(row)
            if executed.returncode:raise ValueError('production guard compile/execution failed')
        if {p.name:sha(p) for p in files}!=result['sources']:raise ValueError('source changed')
        result['result_exit_code']=0
    except Exception as error:result['error']={'type':type(error).__name__,'message':str(error)}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'result_exit_code':result['result_exit_code'],'output':str(out),'error':result.get('error')}))
    return result['result_exit_code']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);raise SystemExit(main(p.parse_args()))
