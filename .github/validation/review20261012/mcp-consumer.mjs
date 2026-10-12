import { pathToFileURL } from 'node:url';
const { PeekabooMCPWrapper } = await import(pathToFileURL(process.env.PRODUCTION_WRAPPER).href);
const wrapper = new PeekabooMCPWrapper({binaryPath:process.env.SWIFT_BINARY});
const owned = new Set();
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const running = pid => {try {process.kill(pid,0); return true;}catch{return false;}};
async function waitFor(check,label) {for(let i=0;i<1000;i++){if(check())return;await sleep(10);}throw Error(label);}
try {
 wrapper.start(); const first=wrapper.child.pid; owned.add(first);
 console.log('ACTUAL_SWIFT_CHILD',first);
 await sleep(1500);
 if(!running(first)||wrapper.child?.pid!==first)throw Error('actual Swift server did not remain alive');
 wrapper.start(); if(wrapper.child)owned.add(wrapper.child.pid);
 wrapper.start(); if(wrapper.child)owned.add(wrapper.child.pid);
 if(wrapper.child?.pid!==first||owned.size!==1)throw Error('repeated starts replaced or duplicated the actual Swift child');
 console.log('REPEATED_STARTS_RETAIN_ONE_CHILD',first,'starts',wrapper.restartTimestamps.length);
 process.kill(first,'SIGKILL');
 await waitFor(()=>wrapper.restartTimer!==null&&wrapper.child===null,'restart backoff missing');
 const timer=wrapper.restartTimer;wrapper.start();
 if(wrapper.child)owned.add(wrapper.child.pid);
 if(wrapper.restartTimer!==timer||wrapper.child!==null)throw Error('start during backoff changed recovery state');
 console.log('START_DURING_BACKOFF_RETAINS_TIMER');
 await waitFor(()=>wrapper.child!==null,'actual Swift server did not recover');
 const recovered=wrapper.child.pid;owned.add(recovered);await sleep(1500);
 if(recovered===first||!running(recovered))throw Error('actual Swift recovery child unavailable');
 wrapper.start(); if(wrapper.child?.pid!==recovered)throw Error('recovered child duplicated');
 console.log('ACTUAL_SWIFT_RECOVERY',recovered,'starts',wrapper.restartTimestamps.length);
 console.log('TRACE_PASS');wrapper.shutdown();
} catch(error) {
 console.error('TRACE_FAILURE',error.message);
 for(const pid of owned)try{process.kill(pid,'SIGKILL');}catch{}
 process.exit(2);
}
setTimeout(()=>{for(const pid of owned)try{process.kill(pid,'SIGKILL');}catch{};process.exit(99)},12000).unref();
