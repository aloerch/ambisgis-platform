#!/usr/bin/env python3
"""Read-only static/reflective/source accounting for the bounded compatibility surface."""
import argparse,collections,hashlib,io,json,re,struct,zipfile
from pathlib import Path
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pool(data):
    count=int.from_bytes(data[8:10],'big');offset=10;values=[None]*count;index=1
    while index<count:
        tag=data[offset];offset+=1
        if tag==1:
            length=int.from_bytes(data[offset:offset+2],'big');offset+=2;values[index]=data[offset:offset+length].decode('utf8','replace');offset+=length
        elif tag in (7,8,16,19,20):values[index]=(tag,int.from_bytes(data[offset:offset+2],'big'));offset+=2
        elif tag in (9,10,11,12,17,18):values[index]=(tag,*struct.unpack_from('>HH',data,offset));offset+=4
        elif tag in (3,4):offset+=4
        elif tag in (5,6):offset+=8;index+=1
        elif tag==15:offset+=3
        else:raise ValueError('Unknown class constant tag')
        index+=1
    return values

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.workspace_root
    aggregate=root/'build-worktrees/java-gmt-remediation/aggregate-02';war=aggregate/'work/source/geoserver/src/web/app/target/geoserver.war'
    refs=collections.defaultdict(set);testrefs=collections.defaultdict(set);consumers=set();classes=set();reflective=[];resources=[]
    def inspect(name,data,target):
        if b'net/sf/json' not in data and b'net.sf.json' not in data:return
        values=pool(data)
        for value in values:
            if isinstance(value,tuple) and value[0] in (9,10,11):
                owner=values[values[value[1]][1]]
                if owner.startswith('net/sf/json/'):
                    nt=values[value[2]];target[owner].add(values[nt[1]]+values[nt[2]])
                    if target is refs:consumers.add(name)
            if isinstance(value,str) and 'net.sf.json.' in value:reflective.append({'origin':name,'literal':value})
    with zipfile.ZipFile(war) as wz:
        for member in wz.namelist():
            if member.startswith('WEB-INF/lib/') and member.endswith('.jar'):
                with zipfile.ZipFile(io.BytesIO(wz.read(member))) as jar:
                    for n in jar.namelist():
                        if n.endswith('.class'):
                            classes.add(n)
                            if 'json-lib-' not in member:inspect(member+'!'+n,jar.read(n),refs)
                        elif 'json-lib-' not in member and not n.endswith('/'):
                            b=jar.read(n)
                            if b'net.sf.json' in b or b'net/sf/json' in b:resources.append({'origin':member+'!'+n,'sha256':hashlib.sha256(b).hexdigest()})
    source_matches=[];auth_sources=[]
    source_root=aggregate/'work/source'
    for file in source_root.rglob('*'):
        if not file.is_file():continue
        relative=str(file.relative_to(source_root))
        if '/target/test-classes/' in relative and file.suffix=='.class':inspect(relative,file.read_bytes(),testrefs);continue
        if '/target/' in relative or file.suffix not in {'.java','.xml','.properties','.json','.yaml','.yml','.mf'}:continue
        if file.stat().st_size>2_000_000:continue
        text=file.read_text(errors='replace')
        if 'net.sf.json' in text or 'net/sf/json' in text:
            compiled_name=relative.split('/src/main/java/')[-1].replace('.java','.class')
            source_matches.append({'path':relative,'sha256':sha(file),'production_definition_in_war':compiled_name in classes,'lines':[i+1 for i,line in enumerate(text.splitlines()) if 'net.sf.json' in line or 'net/sf/json' in line]})
        if file.suffix=='.java' and '/src/main/java/' in relative and any(word in relative.lower() for word in ['geonode','oauth','role']):
            imports=[line.strip() for line in text.splitlines() if line.startswith('import ') and any(word in line for word in ['json','JSON','ObjectMapper'])]
            if imports:auth_sources.append({'path':relative,'sha256':sha(file),'json_imports':imports})
    original=root/'build-worktrees/java-gmt-remediation/source/build-01/source/json'
    source_account=[]
    for file in sorted((original/'src/main').rglob('*')):
        if file.is_file() and file.suffix in {'.java','.groovy'}:
            text=file.read_text(errors='replace');source_account.append({'path':str(file.relative_to(original)),'sha256':sha(file),'json_org_attributed':'@author JSON.org' in text,'selected_prior':str(file).startswith(str(original/'src/main/java')),'disposition':'historical only; none incorporated into independent adapter'})
    result={'schema_version':1,'parent_war':{'path':str(war),'sha256':sha(war)},'production_member_references':{k:sorted(v) for k,v in sorted(refs.items())},'production_consumers':sorted(consumers),'selected_reactor_test_member_references':{k:sorted(v) for k,v in sorted(testrefs.items())},'reflective_literals':reflective,'resource_references':resources,'source_references':source_matches,'authentication_role_json_sources':auth_sources,'historical_source_accounting':source_account,'separation_decision':'Do not claim seven-file boundary: replace complete selected compatibility layer; all old JSONUtils helpers and potential uncredited derivations excluded. Other runtime JSON stacks remain separate unchanged candidate entries; no global JSON.org-removal claim.','limits':'Literal reflection/source scan is not proof against arbitrary dynamically constructed class names; selected compilation and actual affected runtime tests establish bounded support. Unselected inherited json-lib binding/function/XML/Groovy APIs are absent, not stubbed.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'production_consumers':len(consumers),'production_classes':len(refs),'production_members':sum(map(len,refs.values())),'source_matches':len(source_matches),'authentication_role_sources':len(auth_sources),'historical_source_files':len(source_account)}))
if __name__=='__main__':main()
