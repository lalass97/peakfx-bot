#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any

EXPECTED_CONFIGS={"B01","B02","B03","B04"}
EXPECTED_WINDOWS={"2020_2021","2021_2022","2022_2023","2023_2024","2024_2025"}
EXPECTED_RUNS={(c,w) for c in EXPECTED_CONFIGS for w in EXPECTED_WINDOWS}

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def load_json(path:Path)->Any:
    with path.open('r',encoding='utf-8-sig') as f:return json.load(f)

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('artifact_root',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
    root=a.artifact_root.resolve(); errors=[]; checks=[]
    manifest_path=root/'architecture_b_manifest.json'
    if not manifest_path.is_file(): print(f'Missing manifest: {manifest_path}',file=sys.stderr);return 2
    m=load_json(manifest_path); runs=m.get('runs',[]); seen=set(); sh=set(); bh=set(); sph=set()
    if len(runs)!=20: errors.append(f'Expected 20 manifest runs, found {len(runs)}')
    if m.get('revision_enabled') is not True: errors.append('B-R1 revision_enabled must be true')
    if m.get('oos_locked') is not True or m.get('reserved_oos_not_tested') is not True: errors.append('OOS lock/state invalid')
    for r in runs:
        cfg=str(r.get('configuration','')); w=str(r.get('window','')); pair=(cfg,w)
        if pair in seen: errors.append(f'Duplicate run {cfg}/{w}')
        seen.add(pair)
        if pair not in EXPECTED_RUNS: errors.append(f'Unexpected run {cfg}/{w}')
        if r.get('tick_volume_revision') is not True: errors.append(f'B-R1 tick-volume filter missing for {cfg}/{w}')
        if r.get('oos_locked') is not True: errors.append(f'OOS lock missing for {cfg}/{w}')
        if str(r.get('model'))!='real_ticks': errors.append(f'Non-real-tick model for {cfg}/{w}')
        ex=r.get('execution',{})
        if float(ex.get('initial_deposit',0))!=10000 or int(ex.get('bars',0))<=0 or int(ex.get('ticks',0))<=0:
            errors.append(f'Invalid execution for {cfg}/{w}: {ex}')
        sh.add(str(r.get('source_sha256',''))); bh.add(str(r.get('binary_sha256',''))); sph.add(str(r.get('spec_sha256','')))
        report=Path(str(r.get('report','')))
        if not report.is_absolute():
            cand=[root/report,root/cfg/w/report.name]; report=next((p for p in cand if p.is_file()),cand[-1])
        else:
            report=root/cfg/w/report.name
        if not report.is_file(): errors.append(f'Missing report for {cfg}/{w}: {report}');continue
        actual=sha256(report)
        if actual!=str(r.get('report_sha256','')): errors.append(f'Report hash mismatch for {cfg}/{w}')
        meta=root/cfg/w/'run_metadata.json'
        if not meta.is_file(): errors.append(f'Missing run metadata for {cfg}/{w}')
        else:
            md=load_json(meta)
            if md.get('tick_volume_revision') is not True: errors.append(f'Metadata B-R1 flag missing for {cfg}/{w}')
            checks.append({'configuration':cfg,'window':w,'report_sha256':actual,'metadata_sha256':sha256(meta)})
    if seen!=EXPECTED_RUNS: errors.append(f'Matrix mismatch; missing={sorted(EXPECTED_RUNS-seen)} extra={sorted(seen-EXPECTED_RUNS)}')
    if len(sh)!=1: errors.append(f'Expected one source hash, found {len(sh)}')
    if len(bh)!=1: errors.append(f'Expected one binary hash, found {len(bh)}')
    if len(sph)!=1: errors.append(f'Expected one spec hash, found {len(sph)}')
    for label,name,hashes in [('source','PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.mq5',sh),('binary','PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.ex5',bh),('specification','ARCHITECTURE_B_FROZEN_BASELINE_SPEC.md',sph)]:
        p=root/'frozen_inputs'/name
        if not p.is_file(): errors.append(f'Missing frozen {label} copy: {p}')
        elif hashes and sha256(p)!=next(iter(hashes)): errors.append(f'Frozen {label} hash mismatch')
    result={'artifact_root':str(root),'verified':not errors,'stage':'B-R1','expected_run_count':20,'observed_run_count':len(runs),'matrix_complete':seen==EXPECTED_RUNS,'checks':checks,'errors':errors}
    out=a.output or root/'independent_verification_br1.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    if errors:
        for e in errors: print('ERROR:',e,file=sys.stderr)
        return 1
    print(f'B-R1 verification PASSED: 20/20 reports verified. Report: {out}')
    return 0
if __name__=='__main__': raise SystemExit(main())
