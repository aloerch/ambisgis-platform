import hashlib,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path('build-support/java').resolve()))
import acquisition
root=pathlib.Path('/home/revelberry/Projects/AmbisGIS/source-archives')
results=[]
for folder,name in [('java-source-closure-parent','custody-snapshot-01.json'),('java-source-closure-research','research-snapshot-01.json')]:
 custody=root/folder;manifest=custody/name;raw=manifest.read_bytes();data=json.loads(raw)
 # These historical research manifests omit schema_version; reuse the verifier
 # over their unchanged file entries, retaining original manifest hash separately.
 result=acquisition.verify(custody,{'schema_version':1,'files':data['files']})
 assert result['files']==data['file_count']; assert result['bytes']==data['bytes']
 expected={row['path'] for row in data['files']}
 actual={p.relative_to(custody).as_posix() for p in custody.rglob('*') if p.is_file() and p!=manifest}
 assert expected==actual
 result.update(custody=str(custody),manifest=str(manifest),manifest_sha256=hashlib.sha256(raw).hexdigest(),complete_file_set_equal=True,original_manifest_unchanged=True,schema_adapter='add schema_version 1 in memory only; original file entries unchanged')
 results.append(result)
pathlib.Path('/tmp/ambisgis-pr57-review-20260920/research-custody.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
