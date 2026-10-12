import hashlib,json,os,re,shutil,signal,subprocess,time
from pathlib import Path
source=Path.cwd();assets=Path(os.environ['PROOF_ASSETS']);out=Path(os.environ['PROOF_OUTPUT']);out.mkdir(parents=True,exist_ok=True);number=int(os.environ['PR_NUMBER']);head=os.environ['SOURCE_HEAD'];results={}
def run(name,args,timeout=1800,cwd=None,env=None,hold_stdin=False):
 log=out/(name+'.log');start=time.monotonic()
 with log.open('w') as stream:
  try:
   if hold_stdin:
    p=subprocess.Popen(args,cwd=cwd or source,env=env or os.environ,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait();code=124
    finally:p.stdin.close()
   else:code=subprocess.run(args,cwd=cwd or source,env=env or os.environ,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:code=124
  except FileNotFoundError as error:stream.write(str(error)+'\n');code=127
 text=log.read_text();results[name]={'exit':code,'elapsed_seconds':round(time.monotonic()-start,2),'command':args,'log':log.name};(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,'exit',code,flush=True);print(text[-2500:],flush=True);return code,text
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
runtime={}
for name,args in [('head',['git','rev-parse','HEAD']),('submodules',['git','submodule','status','--recursive']),('swift',['swift','--version']),('xcode',['xcodebuild','-version']),('node',['node','--version']),('pnpm',['pnpm','--version']),('host',['sw_vers'])]:
 p=subprocess.run(args,text=True,capture_output=True);runtime[name]={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
(out/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
files=[]
for name in subprocess.check_output(['git','ls-files'],text=True).splitlines():
 p=source/name
 if p.is_file():files.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(out/'source-manifest.json').write_text(json.dumps({'head':head,'files':files},indent=2)+'\n')
run('install',['pnpm','install','--frozen-lockfile'])
run('lint',['pnpm','run','lint'])
run('format-check',['pnpm','run','format:check'])
code,_=run('cli-build',['pnpm','run','build:cli'],timeout=2700)
if code==0:
 p=subprocess.run(['python3','scripts/setup-swift-workspace.py','run','--','swift','build','--package-path','Apps/CLI','--show-bin-path'],text=True,capture_output=True)
 (out/'bin-path.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
 binary=Path(p.stdout.strip().splitlines()[-1])/'peekaboo';assert binary.is_file(),str(binary)
 (out/'binary.json').write_text(json.dumps({'path':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()},indent=2)+'\n')
 if number==1020:
  env={**os.environ,'PRODUCTION_WRAPPER':str(source/'peekaboo-mcp.js'),'SWIFT_BINARY':str(binary)}
  code,text=run('actual-swift-mcp-consumer',['node',str(assets/'mcp-consumer.mjs')],timeout=40,env=env,hold_stdin=True)
  if code==0 and 'TRACE_PASS' not in text:results['actual-swift-mcp-consumer']['exit']=99
  # Baseline production JavaScript with the same verified-unchanged Swift package trees.
  baseline='509f12ce7958f220b693608106a135a7ac163775'
  subprocess.run(['git','fetch','--no-tags','--depth=1','origin',baseline],check=True)
  for path in ['Apps/CLI','Core']:
   assert subprocess.check_output(['git','rev-parse',head+':'+path])==subprocess.check_output(['git','rev-parse',baseline+':'+path]),path
  old=out/'baseline-wrapper.mjs';old.write_bytes(subprocess.check_output(['git','show',baseline+':peekaboo-mcp.js']))
  env['PRODUCTION_WRAPPER']=str(old);before,text=run('original-swift-mcp-consumer',['node',str(assets/'mcp-consumer.mjs')],timeout=40,env=env,hold_stdin=True)
  if before!=2 or 'repeated starts replaced or duplicated' not in text:results['original-swift-mcp-consumer']['expected_regression']='NOT_CONFIRMED'
  else:results['original-swift-mcp-consumer']['expected_regression']='confirmed duplicate actual Swift child'
 if number==1027:
  original='0f82c67471701dd6a87aa5a341050926709ecec1';subprocess.run(['git','fetch','--no-tags','--depth=1','origin',original],check=True)
  path=source/'Apps/CLI/Sources/PeekabooCLI/Commands/System/WindowCommand+Support.swift';candidate=path.read_bytes()
  args=['swift','test','--package-path','Apps/CLI','--jobs','2','-Xswiftc','-DPEEKABOO_SKIP_AUTOMATION','--no-parallel','--filter','WindowTargetCreationTests']
  try:
   path.write_bytes(subprocess.check_output(['git','show',original+':Apps/CLI/Sources/PeekabooCLI/Commands/System/WindowCommand+Support.swift']))
   before,text=run('original-adapter-with-new-native-regressions',args,timeout=2700)
   results['original-adapter-with-new-native-regressions']['expected_regression']='confirmed' if before!=0 and ('precondition' in text.lower() or 'unexpected' in text.lower() or 'signal 4' in text.lower()) else 'NOT_CONFIRMED'
  finally:path.write_bytes(candidate)
  code,text=run('actual-cli-adapter-regressions',args,timeout=2700)
  if code==0 and not re.search(r'Test run with [1-9][0-9]* tests?.*passed',text):results['actual-cli-adapter-regressions']['exit']=99
  sdk=out/'sdk-client';(sdk/'Sources/Client').mkdir(parents=True,exist_ok=True)
  (sdk/'Package.swift').write_text('// swift-tools-version: 6.2\nimport PackageDescription\nlet package = Package(name:"OwnedSDKClient",platforms:[.macOS(.v14)],dependencies:[.package(path:'+json.dumps(str(source/'Core/PeekabooFoundation'))+')],targets:[.executableTarget(name:"Client",dependencies:[.product(name:"PeekabooFoundation",package:"PeekabooFoundation")])])\n')
  shutil.copyfile(assets/'sdk-consumer.swift',sdk/'Sources/Client/main.swift')
  code,text=run('public-sdk-consumer',['swift','run','--package-path',str(sdk),'--jobs','2','Client'],timeout=900)
  if code==0 and 'PUBLIC_SDK_TRACE_PASS' not in text:results['public-sdk-consumer']['exit']=99
run('test-safe',['pnpm','run','test:safe'],timeout=2700)
status=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True);(out/'tracked-status.log').write_text(status)
assert not status,'test/build modified tracked source'
for item in files:
 p=source/item['path'];assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],item['path']
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
required=['install','lint','format-check','cli-build','test-safe']+(['actual-swift-mcp-consumer'] if number==1020 else ['actual-cli-adapter-regressions','public-sdk-consumer'])
fail=[name for name in required if results.get(name,{}).get('exit')!=0]
if number==1020 and results.get('original-swift-mcp-consumer',{}).get('expected_regression')!='confirmed duplicate actual Swift child':fail.append('original-swift-mcp-consumer baseline')
if number==1027 and results.get('original-adapter-with-new-native-regressions',{}).get('expected_regression')!='confirmed':fail.append('adapter baseline')
(out/'complete.json').write_text(json.dumps({'number':number,'head':head,'required_gates':required,'failed_gates':fail,'source_unchanged':True,'promotion_or_release':False},indent=2)+'\n')
raise SystemExit(bool(fail))
