import hashlib,http.server,io,json,os,re,shutil,subprocess,tarfile,threading,time
from pathlib import Path
source=Path.cwd();assets=Path(os.environ['PROOF_ASSETS']);out=Path(os.environ['PROOF_OUTPUT']);out.mkdir(parents=True,exist_ok=True);head=os.environ['SOURCE_HEAD'];number=int(os.environ['PR_NUMBER']);clientfile=os.environ['CLIENT_FILE'];marker=os.environ['PASS_MARKER'];results={}
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
runtime={n:subprocess.check_output(a,text=True) for n,a in [('head',['git','rev-parse','HEAD']),('host',['sw_vers']),('swift',['swift','--version']),('xcode',['xcodebuild','-version'])]};(out/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
manifest=[]
for name in subprocess.check_output(['git','ls-files','Core/PeekabooFoundation'],text=True).splitlines():
 file=source/name
 if file.is_file():manifest.append({'path':name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
(out/'source-manifest.json').write_text(json.dumps({'head':head,'files':manifest},indent=2)+'\n')
def run(name,args,cwd=None,env=None):
 start=time.monotonic()
 try:p=subprocess.run(args,cwd=cwd or source,env=env,text=True,capture_output=True,timeout=900);code=p.returncode;text=p.stdout+p.stderr
 except subprocess.TimeoutExpired as e:code=124;text=(e.stdout or b'').decode()+(e.stderr or b'').decode()
 (out/(name+'.log')).write_text(text);results[name]={'exit':code,'elapsed_seconds':round(time.monotonic()-start,2),'command':args};(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,'exit',code,flush=True);print(text[-2500:],flush=True);return code,text
client=out/'client';(client/'Sources/Client').mkdir(parents=True,exist_ok=True)
# Keep an @main consumer outside main.swift so both library-style and top-level clients compile.
filename='main.swift' if number==1027 else 'Proof.swift';shutil.copyfile(assets/clientfile,client/'Sources/Client'/filename)
clientsha=hashlib.sha256((client/'Sources/Client'/filename).read_bytes()).hexdigest()
def dependency(path):
 (client/'Package.swift').write_text('// swift-tools-version: 6.2\nimport PackageDescription\nlet package = Package(name:"OwnedReviewSDKClient",platforms:[.macOS(.v14)],dependencies:[.package(path:'+json.dumps(str(path))+')],targets:[.executableTarget(name:"Client",dependencies:[.product(name:"PeekabooFoundation",package:"PeekabooFoundation")])])\n')
def consumer(name):
 args=['swift','run','--package-path',str(client),'--jobs','2','Client']
 if number!=1042:return run(name,args)
 # A real request must reach our owned loopback server before URLSession is cancelled.
 started=out/'owned-request-started';started.unlink(missing_ok=True)
 class Handler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):
   started.write_text('actual owned request observed\n');time.sleep(10)
   try:
    self.send_response(200);self.end_headers();self.wfile.write(b'owned delayed response')
   except (BrokenPipeError,ConnectionResetError):pass
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
 threading.Thread(target=server.serve_forever,daemon=True).start()
 env={**os.environ,'OWNED_CANCEL_URL':'http://127.0.0.1:'+str(server.server_port)+'/owned-cancellation','OWNED_REQUEST_STARTED_FILE':str(started)}
 try:
  code,text=run(name,args,env=env)
  observed=started.is_file();(out/'loopback-cancellation-receipt.json').write_text(json.dumps({'real_owned_http_request_observed':observed,'native_urlsession_cancel_marker':'CANCELLED_URLSESSION_REQUEST' in text,'native_swift_task_cancel_marker':'CANCELLED_SWIFT_TASK' in text,'url_logged':False},indent=2)+'\n')
  return (code if observed else 99),text
 finally:server.shutdown();server.server_close()
dependency(source/'Core/PeekabooFoundation');code,text=consumer('fresh-public-sdk-consumer');freshpass=code==0 and marker in text
code,text=run('native-foundation-suite',['swift','test','--package-path','Core/PeekabooFoundation','--jobs','2']);suitepass=code==0 and bool(re.search(r'(?:Test run with|Executed) [1-9][0-9]* tests?',text))
upgrade=None
if number==1027:
 baseline='10185c91a3fc92a9bb1385ed5e969c4b8997b368';subprocess.run(['git','fetch','--no-tags','--depth=1','origin',baseline],check=True)
 original=out/'original/Core/PeekabooFoundation';original.mkdir(parents=True,exist_ok=True)
 archive=subprocess.check_output(['git','archive','--format=tar',baseline+':Core/PeekabooFoundation'])
 with tarfile.open(fileobj=io.BytesIO(archive)) as files:files.extractall(original,filter='data')
 tree=subprocess.check_output(['git','rev-parse',baseline+':Core/PeekabooFoundation'],text=True).strip();(out/'original-source.json').write_text(json.dumps({'head':baseline,'tree':tree,'archive_sha256':hashlib.sha256(archive).hexdigest()},indent=2)+'\n')
 dependency(original);before,text=run('original-public-sdk-consumer',['swift','run','--package-path',str(client),'--jobs','2','Client']);beforepass=before!=0 and 'accepted invalid pid0' in text
 dependency(source/'Core/PeekabooFoundation');after,text=run('upgraded-public-sdk-consumer',['swift','run','--package-path',str(client),'--jobs','2','Client']);upgrade=beforepass and after==0 and marker in text
 assert hashlib.sha256((client/'Sources/Client'/filename).read_bytes()).hexdigest()==clientsha
status=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True);assert not status,status
for entry in manifest:assert hashlib.sha256((source/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
passed=freshpass and suitepass and (upgrade if number==1027 else True);receipt={'number':number,'head':head,'client_file':clientfile,'client_sha256':clientsha,'fresh_imported_public_sdk_pass':freshpass,'native_foundation_suite_pass':suitepass,'same_client_source_dependency_upgrade_pass':upgrade,'source_unchanged':True,'release_or_publish':False,'pass':passed};(out/'complete.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));raise SystemExit(not passed)
