import sys,json,shutil,hashlib,zipfile
from pathlib import Path
sys.path.insert(0,'build-support/java')
from maven_proxy import MavenCustodyProxy,AcquisitionError
from resolution_inventory import verify_custody,pom_licenses,archive_notices
root=Path('/home/revelberry/Projects/AmbisGIS/source-archives/java-http-auth')
source=root.parent/'java-compatibility/maven';dest=root/'maven'
if dest.exists():raise RuntimeError('new custody destination exists')
verified=verify_custody(source)
assert verified['verification']['valid']
shutil.copytree(source,dest)
proxy=MavenCustodyProxy(dest,timeout=30)
rows=[]
base='org/springframework/ldap/spring-ldap-core/2.3.2.RELEASE/spring-ldap-core-2.3.2.RELEASE'
for suffix in ('.pom','.jar','-sources.jar','.jar.sha1','-sources.jar.sha1','.pom.sha1','.jar.asc','-sources.jar.asc'):
 path=base+suffix
 try:
  artifact=proxy.fetch(path)
  row=dict(artifact.record)
  if suffix=='.pom':row['declared_licenses']=pom_licenses(artifact.path.read_bytes())
  if suffix in ('.jar','-sources.jar'):
   notices,contents,errors=archive_notices(artifact.path)
   row['notices']=notices;row['notice_errors']=errors
   for name,data in contents.items():
    output=root/'ldap-notices'/name;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
  rows.append(row)
 except AcquisitionError as e:rows.append({'maven_path':path,'error':str(e),'status':e.status})
report={'purpose':'exact-ldap-input-exposed-by-real-owned-webapp-package','parent_custody':str(source),'destination':str(dest),'parent_artifacts_verified':len(verified['artifacts']),'source_to_binary_correspondence':False,'signature_trust_verified':False,'acquisitions':rows}
(root/'ldap-acquisition.json').write_text(json.dumps(report,indent=2)+'\n')
shutil.copyfile('/tmp/ambisgis-http-acquire-ldap.py',root/'ldap-acquisition.py')
print(json.dumps({'artifacts':len(rows),'errors':[r for r in rows if 'error' in r],'destination':str(dest)},indent=2))
