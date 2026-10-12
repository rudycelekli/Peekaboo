import hashlib,json,os,signal,subprocess,time,uuid
from pathlib import Path
source=Path.cwd();out=Path(os.environ['PROOF_OUTPUT']);out.mkdir(parents=True,exist_ok=True);head=os.environ['SOURCE_HEAD'];assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
subsystem='boo.peekaboo.owned.'+uuid.uuid4().hex
emitter=out/'emitter.swift';emitter.write_text('''import Foundation
import os
let logger = Logger(subsystem: ProcessInfo.processInfo.environment["OWNED_LOG_SUBSYSTEM"]!, category: "owned-proof")
logger.error("OWNED_ERROR_EVENT_20261012")
logger.info("OWNED_INFO_CONTROL_20261012")
Thread.sleep(forTimeInterval: 1)
''')
binary=out/'emitter';p=subprocess.run(['swiftc',str(emitter),'-o',str(binary)],capture_output=True,text=True);(out/'compile.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
results={'head':head,'subsystem':subsystem,'host':subprocess.check_output(['sw_vers'],text=True),'swift':subprocess.check_output(['swift','--version'],text=True),'release_or_publish':False}
script=source/'scripts/pblog.sh';args=['bash',str(script),'--follow','--errors','--subsystem',subsystem];env={**os.environ,'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:'+os.environ['PATH'],'OWNED_LOG_SUBSYSTEM':subsystem};env.pop('OS_ACTIVITY_MODE',None)
with (out/'stream.log').open('w') as stream:
 child=subprocess.Popen(args,stdout=stream,stderr=subprocess.STDOUT,env=env,start_new_session=True)
 try:
  time.sleep(2);early=child.poll();results['stream_early_exit']=early
  emitted=subprocess.run([str(binary)],env=env,capture_output=True,text=True);(out/'emit.log').write_text(emitted.stdout+emitted.stderr);results['emitter_exit']=emitted.returncode
  deadline=time.monotonic()+15
  while time.monotonic()<deadline and child.poll() is None:
   if 'OWNED_ERROR_EVENT_20261012' in (out/'stream.log').read_text():break
   time.sleep(.25)
 finally:
  if child.poll() is None:os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
text=(out/'stream.log').read_text();results['stream_command']=args;results['stream_error_visible']='OWNED_ERROR_EVENT_20261012' in text;results['stream_info_excluded']='OWNED_INFO_CONTROL_20261012' not in text
p=subprocess.run(['bash',str(script),'--all','--last','2m','--subsystem',subsystem],env=env,capture_output=True,text=True,timeout=40);(out/'show-controls.log').write_text(p.stdout+p.stderr);results['show_exit']=p.returncode;results['show_error_visible']='OWNED_ERROR_EVENT_20261012' in p.stdout;results['show_info_visible']='OWNED_INFO_CONTROL_20261012' in p.stdout
results['script_sha256']=hashlib.sha256(script.read_bytes()).hexdigest();results['tracked_status']=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True)
passed=results['stream_early_exit'] is None and results['emitter_exit']==0 and results['stream_error_visible'] and results['stream_info_excluded'] and results['show_exit']==0 and results['show_error_visible'] and results['show_info_visible'] and not results['tracked_status'];results['pass']=passed
(out/'complete.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2));print(text);raise SystemExit(not passed)
