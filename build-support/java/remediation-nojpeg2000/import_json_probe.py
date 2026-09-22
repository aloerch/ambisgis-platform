"""Compare original/repaired native importer converters with retained real WAR libraries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
TASK=Path('/home/revelberry/Projects/AmbisGIS')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main(out):
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    report={'result_exit_code':1,'scope':'Native original/repaired HTTP converter; actual HTTP acceptance remains separately required','cases':[]}
    try:
        rows=[x for x in json.loads((HERE/'geoserver-repairs.json').read_text()) if x['path'].endswith('JSONMessageConverter.java')]
        java=TASK/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1/bin'
        sys.path.insert(0,str(HERE.parent));from compatibility import verify_network_receipt
        for label,side,libs,mode in [('parent-original','before','java-gmt-remediation/geonode-02/lib','original'),('candidate-original','before','json-jpeg2000-remediation/gwc-01/lib','original'),('candidate-repaired','after','json-jpeg2000-remediation/gwc-01/lib','repaired')]:
            directory=out/label;directory.mkdir();classes=directory/'classes';classes.mkdir()
            sources=[]
            for row in rows:
                source=directory/Path(row['path']).name;source.write_text(row[side]);sources.append(source)
            witness=directory/'ImportContextJsonWitness.java';witness.write_bytes((HERE/witness.name).read_bytes());sources.append(witness)
            libraries=sorted((TASK/'build-worktrees'/libs).glob('*.jar'))
            if len(libraries)!=367:raise ValueError('unexpected WAR library count')
            cp=os.pathsep.join(map(str,libraries))
            receipt={'case':label,'sources':{p.name:sha(p) for p in sources},'libraries':{p.name:sha(p) for p in libraries},'commands':[]}
            report['cases'].append(receipt)
            for index,command in enumerate([[str(java/'javac'),'-cp',cp,'-d',str(classes),*[str(p) for p in sources]],[str(java/'java'),'-cp',str(classes)+os.pathsep+cp,'ImportContextJsonWitness',mode]]):
                proof=directory/('network-'+str(index)+'.json');full=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(proof),'--',*command]
                process=subprocess.run(full,capture_output=True,text=True,timeout=120);log=directory/(str(index)+'.log');log.write_text(process.stdout+process.stderr)
                receipt['commands'].append({'command':full,'exit_code':process.returncode,'log_sha256':sha(log),'network':verify_network_receipt(proof,process.returncode)})
                if process.returncode:raise ValueError('native importer '+label+' failed')
        report['result_exit_code']=0
    except Exception as error:report['error']={'type':type(error).__name__,'message':str(error)}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'result_exit_code':report['result_exit_code'],'output':str(out),'error':report.get('error')}));return report['result_exit_code']
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);raise SystemExit(main(parser.parse_args().output.resolve()))
