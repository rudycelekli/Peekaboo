import hashlib,io,json,os,re,subprocess,zipfile
from pathlib import Path
out=Path(os.environ.get('PROOF_OUTPUT','.'));out.mkdir(parents=True,exist_ok=True)
local=os.environ.get('LOCAL_FROZEN_PROOF')
metadata={}
if local:root=Path(local)
else:
 repo='rudycelekli/Peekaboo';artifact=11747401672;run=38245341853
 metadata=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/artifacts/{artifact}'],text=True));assert metadata['name']=='peekaboo-cli-1043-38245341853';assert metadata['workflow_run']['id']==run
 runmeta=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}'],text=True));assert runmeta['conclusion']=='failure';assert runmeta['status']=='completed'
 data=subprocess.check_output(['gh','api',f'repos/{repo}/actions/artifacts/{artifact}/zip']);metadata['zip_sha256']=hashlib.sha256(data).hexdigest();metadata['run']=runmeta
 root=out/'frozen-original';root.mkdir(exist_ok=True)
 with zipfile.ZipFile(io.BytesIO(data)) as archive:
  for item in archive.infolist():
   path=Path(item.filename);assert not path.is_absolute() and '..' not in path.parts
   if item.is_dir() or '.build' in path.parts:continue
   file=root/path;file.parent.mkdir(exist_ok=True,parents=True);file.write_bytes(archive.read(item))
head='e7c99895e8a692b5e8147a5d2abf956ac9b18188';old='fa8556d81c341fbba8721b5c83d04312a2976458'
original=json.loads((root/'complete.json').read_text());results=json.loads((root/'results.json').read_text());manifest=json.loads((root/'source-manifest.json').read_text());assert original['head']==manifest['head']==head;assert original['baseline_head']==old;assert original['source_unchanged']
before=(root/'original-production-with-new-canonical-tests.log').read_text();after=(root/'candidate-canonical-cli-tests.log').read_text();safe=(root/'test-safe.log').read_text()
def baseline_valid(exit_code,text):
 return exit_code!=0 and bool(re.search(r'Test run with 6 tests in 1 suite failed.*15 issues',text)) and bool(re.search(r'Valid JSON values reach verbose tool completion output.*with 5 test cases failed',text))
def candidate_valid(exit_code,text):
 lines=[line for line in text.splitlines() if line.startswith('✔ Test "') and ' passed after ' in line]
 scenarios=sum(int(re.search(r'with (\d+) test cases',line).group(1)) if re.search(r'with (\d+) test cases',line) else 1 for line in lines)
 return exit_code==0 and len(lines)==6 and scenarios==14 and bool(re.search(r'Test run with 6 tests in 1 suite passed',text))
# Negative controls test the evaluator rather than accepting compilation errors or absent cases.
assert not baseline_valid(0,before)
assert not baseline_valid(1,'error: compilation failed')
assert not candidate_valid(0,after.replace('with 5 test cases passed','with 4 test cases passed'))
assert not candidate_valid(1,after)
assert baseline_valid(results['original-production-with-new-canonical-tests']['exit'],before)
assert candidate_valid(results['candidate-canonical-cli-tests']['exit'],after)
required=['install','lint','format-check','cli-build','test-safe','candidate-canonical-cli-tests'];assert all(results[name]['exit']==0 for name in required)
assert 'Test run with 110 tests in 23 suites passed' in safe
assert 'Test run with 2279 tests in 272 suites passed' in safe
assert 'SwiftPM consumer contract passed for:' in safe
receipt={'number':1043,'head':head,'baseline_head':old,'original_run':38245341853,'original_workflow_conclusion':'failure','correction':'Swift Testing logical test count differs from parameterized case count','logical_tests':6,'parameterized_and_single_cases':14,'failing_original_delegate_cases':5,'original_failure_issues':15,'original_producer_actual_native_failure':True,'candidate_actual_native_pass':True,'required_gates_pass':True,'full_safe_foundation_tests':110,'full_safe_cli_tests':2279,'full_safe_cli_suites':272,'source_unchanged':True,'commands_rerun':False,'evaluator_negative_controls_pass':True,'logs_unchanged':True,'promotion_or_release':False,'failed_gates':[],'frozen_file_hashes':{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in root.iterdir() if file.is_file()}}
(out/'original-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n');(out/'corrected-complete.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
