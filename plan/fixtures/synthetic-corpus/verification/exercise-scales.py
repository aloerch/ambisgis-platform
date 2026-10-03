from pathlib import Path
import datetime,hashlib,json,subprocess,time,sys
R=Path("/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-corpus-runtime/round-005");W=Path("/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-corpus-worktree");tool=W/"plan/tools/synthetic_corpus.py"
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
report={"producer_sha256":sha(tool),"seed":2409,"scope":"Actual fixture generation and full-file verification; not product query capacity or database benchmark.","runs":[]}
for count in (100000,1000000):
 output=R/f"scale-{count}"
 argv=["/usr/bin/python3",str(W/"build-support/postgis/offline_exec.py"),"--evidence",str(R/f"scale-{count}-network.json"),"--","/usr/bin/python3",str(tool),"generate","--output",str(output),"--addresses",str(count)]
 start=time.perf_counter();done=subprocess.run(argv,check=True,capture_output=True,text=True);elapsed=time.perf_counter()-start
 (R/f"scale-{count}-command.json").write_text(json.dumps({"argv":argv,"exit_code":done.returncode,"stdout":done.stdout,"stderr":done.stderr},indent=2)+"\n")
 seen=set();population=0;rows=0;nulls=0;empty=0
 with (output/"addresses.ndjson").open() as stream:
  for rows,line in enumerate(stream,1):
   row=json.loads(line);p=row["properties"];assert p["object_id"]==rows and p["fid"]==row["id"] and p["fid"] not in seen;seen.add(p["fid"]);population+=p["population"];nulls+=p["name"] is None;empty+=p["name"]==""
 assert rows==count
 cycles,remainder=divmod(count,12)
 assert population==cycles*660+5*remainder*(remainder-1)
 assert nulls==cycles*2+sum(i<=remainder for i in (2,10));assert empty==cycles*2+sum(i<=remainder for i in (3,11))
 manifest=json.loads((output/"manifest.json").read_text());assert manifest["generator_sha256"]==sha(tool)
 for name,record in manifest["files"].items():assert sha(output/name)==record["sha256"]
 report["runs"].append({"addresses":count,"unique_fids":len(seen),"population_sum":population,"null_names":nulls,"empty_names":empty,"generation_seconds":elapsed,"bytes":sum(f["bytes"] for f in manifest["files"].values()),"manifest_sha256":sha(output/"manifest.json"),"all_file_hashes_verified":True,"network_receipt_sha256":sha(R/f"scale-{count}-network.json")})
 (R/"scale-results.json").write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(report["runs"][-1]),flush=True)
