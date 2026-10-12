import hashlib,json,os,re,subprocess,time
from pathlib import Path
source=Path.cwd();out=Path(os.environ['PROOF_OUTPUT']);out.mkdir(parents=True,exist_ok=True);head=os.environ['SOURCE_HEAD'];number=int(os.environ['PR_NUMBER']);baseline=os.environ['BASELINE_HEAD'];testfilter=os.environ['TEST_FILTER'];count=int(os.environ['TEST_COUNT']);results={}
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
runtime={}
for name,args in [('head',['git','rev-parse','HEAD']),('submodules',['git','submodule','status','--recursive']),('swift',['swift','--version']),('xcode',['xcodebuild','-version']),('node',['node','--version']),('pnpm',['pnpm','--version']),('uv',['uv','--version']),('host',['sw_vers'])]:
 p=subprocess.run(args,text=True,capture_output=True);runtime[name]={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
(out/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
manifest=[]
for name in subprocess.check_output(['git','ls-files'],text=True).splitlines():
 p=source/name
 if p.is_file():manifest.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(out/'source-manifest.json').write_text(json.dumps({'head':head,'files':manifest},indent=2)+'\n')
def run(name,args,timeout=2700):
 start=time.monotonic();log=out/(name+'.log')
 with log.open('w') as f:
  try:code=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:code=124
 text=log.read_text();results[name]={'exit':code,'elapsed_seconds':round(time.monotonic()-start,2),'command':args};(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,'exit',code,flush=True);print(text[-2500:],flush=True);return code,text
for name,args in [('install',['pnpm','install','--frozen-lockfile']),('lint',['pnpm','run','lint']),('format-check',['pnpm','run','format:check']),('cli-build',['pnpm','run','build:cli'])]:run(name,args)
subprocess.run(['git','fetch','--no-tags','--depth=1','origin',baseline],check=True)
paths=['Apps/CLI/Sources/PeekabooCLI/Commands/AI/AgentOutputDelegate.swift','Apps/CLI/Sources/PeekabooCLI/Commands/AI/AgentOutputDelegate+Formatting.swift'] if number==1043 else ['Apps/CLI/Sources/PeekabooCLI/Helpers/ProcessWait.swift']
args=['swift','test','--package-path','Apps/CLI','--jobs','2','-Xswiftc','-DPEEKABOO_SKIP_AUTOMATION','--no-parallel','--filter',testfilter]
saved={p:(source/p).read_bytes() for p in paths};oldreceipt=[]
try:
 for path in paths:
  data=subprocess.check_output(['git','show',baseline+':'+path]);(source/path).write_bytes(data);oldreceipt.append({'path':path,'sha256':hashlib.sha256(data).hexdigest()})
 before,text=run('original-production-with-new-canonical-tests',args)
 # Compiler/setup failures cannot stand in for the requested real behavior regression.
 beforepass=before!=0 and bool(re.search(r'Test run with '+str(count)+r' tests? .*failed',text)) and ('✘ Test' in text or 'Issue recorded' in text)
finally:
 for path,data in saved.items():(source/path).write_bytes(data)
(out/'baseline-source.json').write_text(json.dumps({'head':baseline,'files':oldreceipt,'real_native_test_failure_confirmed':beforepass},indent=2)+'\n')
after,text=run('candidate-canonical-cli-tests',args);candidatepass=after==0 and bool(re.search(r'Test run with '+str(count)+r' tests? .*passed',text))
run('test-safe',['pnpm','run','test:safe'])
status=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True);assert not status,status
for entry in manifest:assert hashlib.sha256((source/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
failed=[n for n in ['install','lint','format-check','cli-build','test-safe','candidate-canonical-cli-tests'] if results[n]['exit']!=0]
if not beforepass:failed.append('native original behavior regression not confirmed')
if not candidatepass:failed.append('candidate expected native count/pass not confirmed')
receipt={'number':number,'head':head,'baseline_head':baseline,'filter':testfilter,'expected_tests':count,'original_producer_actual_native_failure':beforepass,'candidate_actual_native_pass':candidatepass,'failed_gates':failed,'source_unchanged':True,'promotion_or_release':False};(out/'complete.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));raise SystemExit(bool(failed))
