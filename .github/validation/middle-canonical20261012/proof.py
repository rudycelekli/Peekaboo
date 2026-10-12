import hashlib,json,os,re,subprocess,time
from pathlib import Path
source=Path.cwd();root=Path(os.environ['PROOF_OUTPUT']);root.mkdir(parents=True,exist_ok=True);group=os.environ['SOURCE_GROUP'];plans=json.loads((Path(os.environ['PROOF_ASSETS'])/'heads.json').read_text())[group];batch=[]
for item in plans:
 number=item['number'];head=item['head'];assert re.fullmatch('[0-9a-f]{40}',head);out=root/str(number);out.mkdir(exist_ok=True);results={}
 subprocess.run(['git','fetch','--no-tags','--depth=1','origin',head],check=True)
 subprocess.run(['git','checkout','--detach',head],check=True)
 subprocess.run(['git','submodule','update','--init','--recursive'],check=True)
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
 runtime={}
 for label,args in [('head',['git','rev-parse','HEAD']),('submodules',['git','submodule','status','--recursive']),('swift',['swift','--version']),('xcode',['xcodebuild','-version']),('node',['node','--version']),('pnpm',['pnpm','--version']),('host',['sw_vers'])]:
  p=subprocess.run(args,text=True,capture_output=True);runtime[label]={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 (out/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
 manifest=[]
 for path in subprocess.check_output(['git','ls-files'],text=True).splitlines():
  file=source/path
  if file.is_file():manifest.append({'path':path,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
 (out/'source-manifest.json').write_text(json.dumps({'head':head,'files':manifest},indent=2)+'\n')
 for label,args in [('install',['pnpm','install','--frozen-lockfile']),('lint',['pnpm','run','lint']),('format-check',['pnpm','run','format:check']),('test-safe',['pnpm','run','test:safe'])]:
  start=time.monotonic();log=out/(label+'.log')
  with log.open('w') as stream:
   try:code=subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,timeout=4500).returncode
   except subprocess.TimeoutExpired:code=124
  results[label]={'command':args,'exit':code,'elapsed_seconds':round(time.monotonic()-start,2),'log':log.name};(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(number,label,'exit',code,flush=True);print(log.read_text()[-2500:],flush=True)
 status=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True);(out/'tracked-status.log').write_text(status);assert not status,(number,status)
 for entry in manifest:
  file=source/entry['path'];assert file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==entry['sha256'],(number,entry['path'])
 failed=[name for name,value in results.items() if value['exit']!=0];receipt={'number':number,'head':head,'failed_gates':failed,'source_unchanged':True,'promotion_or_release':False};(out/'complete.json').write_text(json.dumps(receipt,indent=2)+'\n');batch.append(receipt);(root/'batch-complete.json').write_text(json.dumps(batch,indent=2)+'\n')
raise SystemExit(any(x['failed_gates'] for x in batch))
