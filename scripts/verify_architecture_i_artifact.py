#!/usr/bin/env python3
import argparse,hashlib,json,sys
from pathlib import Path
CONFIGS={"I01","I02","I03","I04"}; WINDOWS={"2020_2021","2021_2022","2022_2023","2023_2024","2024_2025"}; EXPECTED={(c,w) for c in CONFIGS for w in WINDOWS}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('artifact_root',type=Path); ap.add_argument('--output',type=Path); a=ap.parse_args(); r=a.artifact_root.resolve(); err=[]; checks=[]
 mp=r/'architecture_i_manifest.json'
 if not mp.is_file(): print('Missing manifest',file=sys.stderr); return 2
 m=load(mp); runs=m.get('runs',[]); seen=set(); src=set(); binh=set(); spec=set()
 if len(runs)!=20: err.append(f'Expected 20 runs, found {len(runs)}')
 for x in runs:
  c,w=str(x.get('configuration','')),str(x.get('window','')); pair=(c,w)
  if pair in seen: err.append(f'Duplicate {c}/{w}')
  seen.add(pair); src.add(str(x.get('source_sha256',''))); binh.add(str(x.get('binary_sha256',''))); spec.add(str(x.get('spec_sha256','')))
  if pair not in EXPECTED: err.append(f'Unexpected cell {c}/{w}')
  if x.get('oos_locked') is not True: err.append(f'OOS unlocked {c}/{w}')
  e=x.get('execution',{})
  if float(e.get('bars',0))<=0 or float(e.get('ticks',0))<=0: err.append(f'Empty execution {c}/{w}')
  if abs(float(e.get('initial_deposit',0))-10000)>0.01: err.append(f'Wrong deposit {c}/{w}')
  p=r/c/w/Path(str(x.get('report','x'))).name
  if not p.is_file(): err.append(f'Missing report {c}/{w}')
  elif sha(p)!=x.get('report_sha256'): err.append(f'Report hash mismatch {c}/{w}')
  else: checks.append({'configuration':c,'window':w,'report_sha256':sha(p)})
 if seen!=EXPECTED: err.append('Matrix mismatch')
 if len(src)!=1 or len(binh)!=1 or len(spec)!=1: err.append('Frozen hash inconsistency')
 out={'verified':not err,'expected_run_count':20,'observed_run_count':len(runs),'matrix_complete':seen==EXPECTED,'checks':checks,'errors':err}
 o=a.output or r/'independent_verification.json'; o.write_text(json.dumps(out,indent=2),encoding='utf-8')
 if err:
  [print('ERROR:',e,file=sys.stderr) for e in err]; return 1
 print('Verification PASSED: Architecture I 20/20 artifact verified.'); return 0
if __name__=='__main__': raise SystemExit(main())
