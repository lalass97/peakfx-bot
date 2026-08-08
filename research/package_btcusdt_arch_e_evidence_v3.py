#!/usr/bin/env python3
import csv, hashlib, io, json, shutil, subprocess, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE1M='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m'
OUT=Path('artifacts/btcusdt-arch-e-forensic-evidence-v3')
CACHE1M=OUT/'data_1m'
EVID=OUT/'evidence'

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def ts_ms(x):
    x=int(x); return x//1000 if x>10_000_000_000_000 else x

def load_zip_rows(path):
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names)!=1: raise RuntimeError(f'Unexpected zip contents: {path}')
        return list(csv.reader(io.StringIO(z.read(names[0]).decode('utf-8'))))

def download_1m(year,month):
    CACHE1M.mkdir(parents=True,exist_ok=True)
    fn=f'BTCUSDT-1m-{year}-{month:02d}.zip'; p=CACHE1M/fn
    if not p.exists():
        with urllib.request.urlopen(f'{BASE1M}/{fn}',timeout=90) as r:p.write_bytes(r.read())
    return p

def main():
    EVID.mkdir(parents=True,exist_ok=True)
    zeros=list(csv.DictReader((OUT/'zero_duration_trades.csv').open()))
    raw1m=[]; summary=[]; mh=[]
    months={}
    for z in zeros:
        ets=int(z['entry_ts']); dt=datetime.fromtimestamp(ets/1000,timezone.utc); key=(dt.year,dt.month)
        if key not in months:
            p=download_1m(*key); months[key]=(p,load_zip_rows(p)); mh.append({'file':p.name,'sha256':sha256_file(p),'bytes':p.stat().st_size})
        p,rows=months[key]
        stop=float(z['stop']); entry=float(z['entry']); end=ets+4*3600*1000
        bars=[]
        for r in rows:
            if not r or not r[0].strip().isdigit(): continue
            t=ts_ms(r[0])
            if ets<=t<end:
                bars.append({'open_time':t,'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5])})
        trigger=next((b for b in bars if b['low']<=stop),None)
        if trigger is None: raise RuntimeError(f'No 1m trigger found for {ets}')
        trigger_idx=bars.index(trigger); evidence_bars=bars[:min(len(bars),trigger_idx+6)]
        for b in evidence_bars:
            raw1m.append({'entry_ts':ets,'stop':stop,**b})
        same_minute=(trigger['open_time']==ets)
        entry_open_matches=abs(trigger['open']-entry)<1e-8 if same_minute else True
        timing_supported=(trigger['open_time']>ets) or (same_minute and entry_open_matches and trigger['open']>stop and trigger['low']<=stop)
        summary.append({'entry_ts':ets,'entry':entry,'stop':stop,'first_1m_trigger_ts':trigger['open_time'],'same_minute_as_entry':same_minute,'trigger_bar_open':trigger['open'],'trigger_bar_high':trigger['high'],'trigger_bar_low':trigger['low'],'trigger_bar_close':trigger['close'],'entry_open_matches':entry_open_matches,'timing_supported_at_1m_resolution':timing_supported})

    with (OUT/'zero_duration_1m_summary.csv').open('w',newline='') as f:
        fields=list(summary[0].keys()); w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(summary)
    with (OUT/'raw_1m_zero_duration_evidence.csv').open('w',newline='') as f:
        fields=list(raw1m[0].keys()); w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(raw1m)
    with (OUT/'minute_data_hash_manifest.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']); w.writeheader(); w.writerows(mh)

    # Export the actual immutable inputs and replay code, not just hashes.
    copies=[
      ('docs/BTCUSDT_ARCH_E_FROZEN_BASELINE_SPEC.md','BTCUSDT_ARCH_E_FROZEN_BASELINE_SPEC.md'),
      ('research/backtest_btcusdt_arch_e.py','backtest_btcusdt_arch_e.py'),
      ('research/audit_btcusdt_arch_e_v2.py','audit_btcusdt_arch_e_v2.py'),
      ('research/package_btcusdt_arch_e_evidence_v3.py','package_btcusdt_arch_e_evidence_v3.py'),
    ]
    for src,dst in copies: shutil.copy2(src,EVID/dst)
    subprocess.run(['git','show','--no-patch','--pretty=fuller','1702a3b14f3f9df93715e18fb335d54d9b2eac7c'],check=True,stdout=(EVID/'spec_commit.txt').open('w'))
    subprocess.run(['git','show','--no-patch','--pretty=fuller','f974d17f9f69d3bd26f869612d4eb7cdaa4b2221'],check=True,stdout=(EVID/'source_commit.txt').open('w'))
    subprocess.run(['git','log','--oneline','--decorate','--all','--max-count=30'],check=True,stdout=(EVID/'git_log.txt').open('w'))
    file_hashes=[]
    for p in sorted(EVID.iterdir()):
        if p.is_file(): file_hashes.append({'file':p.name,'sha256':sha256_file(p),'bytes':p.stat().st_size})
    with (OUT/'included_file_hashes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']); w.writeheader(); w.writerows(file_hashes)
    result={'protocol':'Architecture E reproducible evidence package v3','oos_tested':False,'zero_duration_1m_all_supported':all(x['timing_supported_at_1m_resolution'] for x in summary),'zero_duration_1m':summary,'included_files':file_hashes,'minute_data_files':mh}
    (OUT/'evidence_result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
