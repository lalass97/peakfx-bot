#!/usr/bin/env python3
import csv, hashlib, io, json, math, os, subprocess, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
START_YEAR,END_YEAR=2021,2025
INITIAL=10000.0
RISK=0.0025
COMM=0.001
CONFIGS={'BE01':(48,3.0),'BE03':(48,4.0)}
EXPECTED={
 'BE01':{'net':1252.4221857250013,'pf':1.6930126258479232,'trades':225,'years':4},
 'BE03':{'net':1045.341909420942,'pf':2.048162906987389,'trades':179,'years':4},
}
SPEC_COMMIT='1702a3b14f3f9df93715e18fb335d54d9b2eac7c'
SOURCE_COMMIT='f974d17f9f69d3bd26f869612d4eb7cdaa4b2221'
SPEC_PATH='docs/BTCUSDT_ARCH_E_FROZEN_BASELINE_SPEC.md'
SOURCE_PATH='research/backtest_btcusdt_arch_e.py'

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def git(*args):
    return subprocess.check_output(['git',*args],text=True).strip()

def ts_ms(x): return x//1000 if x>10_000_000_000_000 else x

def load_h1(cache):
    cache.mkdir(parents=True,exist_ok=True); bars=[]; files=[]
    for y in range(START_YEAR,END_YEAR+1):
        for m in range(1,13):
            fn=f'BTCUSDT-1h-{y}-{m:02d}.zip'; p=cache/fn
            if not p.exists():
                with urllib.request.urlopen(f'{BASE}/{fn}',timeout=60) as r:p.write_bytes(r.read())
            digest=sha256_file(p); files.append({'file':fn,'sha256':digest,'bytes':p.stat().st_size})
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names)!=1: raise RuntimeError(fn)
                for row in csv.reader(io.StringIO(z.read(names[0]).decode())):
                    if not row or not row[0].strip().isdigit():continue
                    bars.append(Bar(ts_ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    uniq={b.ts:b for b in bars}; bars=[uniq[k] for k in sorted(uniq)]
    manifest='\n'.join(f"{x['file']} {x['sha256']} {x['bytes']}" for x in files).encode()
    return bars,files,hashlib.sha256(manifest).hexdigest()

def aggregate_h4(h1):
    bars=[]; children={}; cur=[]; key=None
    def flush(g):
        if len(g)==4:
            b=Bar(g[0].ts,g[0].o,max(x.h for x in g),min(x.l for x in g),g[-1].c,sum(x.v for x in g))
            bars.append(b); children[b.ts]=list(g)
    for b in h1:
        d=datetime.fromtimestamp(b.ts/1000,timezone.utc); k=(d.year,d.month,d.day,d.hour//4)
        if k!=key:
            flush(cur); key=k; cur=[b]
        else:cur.append(b)
    flush(cur); return bars,children

def ema(v,n):
    z=[None]*len(v)
    if len(v)<n:return z
    z[n-1]=sum(v[:n])/n; a=2/(n+1)
    for i in range(n,len(v)):z[i]=v[i]*a+z[i-1]*(1-a)
    return z

def atr(b,n=14):
    tr=[]
    for i,x in enumerate(b):
        pc=b[i-1].c if i else x.c; tr.append(max(x.h-x.l,abs(x.h-pc),abs(x.l-pc)))
    z=[None]*len(b)
    if len(b)<n:return z
    z[n-1]=sum(tr[:n])/n
    for i in range(n,len(b)):z[i]=(z[i-1]*(n-1)+tr[i])/n
    return z

def dd_update(eq,peak,maxdd):
    peak=max(peak,eq); return peak,max(maxdd,(peak-eq)/peak if peak else 0.0)

def replay(bars,children,e200,e100,a14,cfg,roc_lb,mult):
    bal=INITIAL; gp=gl=0.0; pos=None; pend=None; pexit=False; trades=[]; annual={y:0.0 for y in range(START_YEAR,END_YEAR+1)}
    peaks={'realized':INITIAL,'close_mtm':INITIAL,'intrabar':INITIAL}; dds={k:0.0 for k in peaks}; zero=[]
    integrity=[]
    for i,b in enumerate(bars):
        yr=datetime.fromtimestamp(b.ts/1000,timezone.utc).year
        if not START_YEAR<=yr<=END_YEAR:continue
        # Exit at open from prior completed EMA100 signal.
        if pos and pexit:
            px=b.o; xc=pos['q']*px*COMM; pp=pos['q']*(px-pos['entry']); pnl=pp-pos['ec']-xc; bal+=pp-xc
            gp+=max(pnl,0);gl+=min(pnl,0);annual[yr]+=pnl;trades.append((pos['ets'],b.ts,pnl,'ema100_exit'))
            pos=None;pexit=False
        # Entry at next bar open from prior completed signal.
        if pos is None and pend and pend['i']==i:
            entry=b.o; dist=mult*pend['atr']; stop=entry-dist
            if dist>0 and stop>0:
                rc=bal*RISK;q=min(rc/dist,bal/entry)
                if q>0:
                    ec=q*entry*COMM;bal-=ec;pos={'entry':entry,'q':q,'stop':stop,'ec':ec,'ets':b.ts,'highc':entry,'risk':q*dist,'entry_index':i}
            pend=None
        # Conservative adverse mark before stop handling; stop caps executable loss unless gap below.
        if pos:
            adverse_px=b.l
            if b.o<pos['stop']: adverse_px=b.o
            elif b.l<=pos['stop']: adverse_px=pos['stop']
            adverse_eq=bal+pos['q']*(adverse_px-pos['entry'])-pos['q']*adverse_px*COMM
            peaks['intrabar'],dds['intrabar']=dd_update(adverse_eq,peaks['intrabar'],dds['intrabar'])
        # Stop frozen from prior completed bar (or initial stop on entry bar).
        if pos and b.l<=pos['stop']:
            px=b.o if b.o<pos['stop'] else pos['stop'];xc=pos['q']*px*COMM;pp=pos['q']*(px-pos['entry']);pnl=pp-pos['ec']-xc;bal+=pp-xc
            gp+=max(pnl,0);gl+=min(pnl,0);annual[yr]+=pnl
            dur=(b.ts-pos['ets'])/3600000
            rec={'entry_ts':pos['ets'],'exit_ts':b.ts,'pnl':pnl,'reason':'chandelier_stop','duration_hours':dur,'stop':pos['stop'],'entry':pos['entry'],'exit':px}
            trades.append((pos['ets'],b.ts,pnl,'chandelier_stop'))
            if dur==0:
                h1s=children.get(b.ts,[]); trigger=None
                for h in h1s:
                    if h.ts>=pos['ets'] and h.l<=pos['stop']:
                        trigger=h.ts;break
                rec['first_h1_trigger_ts']=trigger; rec['h1_verified']=trigger is not None
                zero.append(rec)
                if trigger is None:integrity.append(f'{cfg}: zero-duration stop has no H1 trigger at {b.ts}')
            pos=None;pexit=False
        # Realized and close-MTM drawdowns.
        peaks['realized'],dds['realized']=dd_update(bal,peaks['realized'],dds['realized'])
        closeeq=bal
        if pos: closeeq=bal+pos['q']*(b.c-pos['entry'])-pos['q']*b.c*COMM
        peaks['close_mtm'],dds['close_mtm']=dd_update(closeeq,peaks['close_mtm'],dds['close_mtm'])
        if not pos: peaks['intrabar'],dds['intrabar']=dd_update(bal,peaks['intrabar'],dds['intrabar'])
        # Completed-bar updates only now.
        if pos:
            pos['highc']=max(pos['highc'],b.c)
            if a14[i] is not None:pos['stop']=max(pos['stop'],pos['highc']-mult*a14[i])
            if e100[i] is not None and b.c<e100[i] and i+1<len(bars):pexit=True
        elif pend is None and i>=max(200,roc_lb,6):
            if e200[i] is None or e200[i-6] is None or a14[i] is None:continue
            roc=b.c/bars[i-roc_lb].c-1 if bars[i-roc_lb].c else 0
            if b.c>e200[i] and e200[i]>e200[i-6] and roc>0 and i+1<len(bars):pend={'i':i+1,'atr':a14[i],'signal_ts':b.ts}
    net=bal-INITIAL; pf=gp/abs(gl) if gl<0 else math.inf
    md_cash=dds['intrabar']*max(peaks['intrabar'],1.0) # informational only; recovery below uses percent gate independent
    years=sum(v>0 for v in annual.values())
    exp=EXPECTED[cfg]
    matches={'trade_count':len(trades)==exp['trades'],'net_profit':abs(net-exp['net'])<1e-6,'profit_factor':abs(pf-exp['pf'])<1e-9,'profitable_years':years==exp['years']}
    strict_pass=net>0 and pf>=1.20 and len(trades)>=50 and dds['intrabar']*100<=20 and years>=4 and not integrity
    return {'config':cfg,'net_profit':net,'profit_factor':pf,'closed_trades':len(trades),'profitable_years':years,'annual_net_profit':annual,
            'max_dd_realized_pct':dds['realized']*100,'max_dd_close_mtm_pct':dds['close_mtm']*100,'max_dd_intrabar_conservative_pct':dds['intrabar']*100,
            'zero_duration_count':len(zero),'zero_duration_all_h1_verified':all(x['h1_verified'] for x in zero),'zero_duration_trades':zero,
            'baseline_match':matches,'integrity_violations':integrity,'strict_drawdown_gate_pass':strict_pass}

def main():
    out=Path(os.environ.get('AUDIT_OUT','artifacts/btcusdt-arch-e-forensic-audit'));cache=Path(os.environ.get('BTC_CACHE',out/'data'));out.mkdir(parents=True,exist_ok=True)
    h1,files,mhash=load_h1(cache);bars,children=aggregate_h4(h1);cl=[x.c for x in bars];e200=ema(cl,200);e100=ema(cl,100);a14=atr(bars)
    audits=[replay(bars,children,e200,e100,a14,cfg,*CONFIGS[cfg]) for cfg in CONFIGS]
    identity={'spec_commit':SPEC_COMMIT,'source_commit':SOURCE_COMMIT,'audit_head_commit':git('rev-parse','HEAD'),
              'spec_git_blob':git('hash-object',SPEC_PATH),'source_git_blob':git('hash-object',SOURCE_PATH),
              'spec_sha256':sha256_file(SPEC_PATH),'source_sha256':sha256_file(SOURCE_PATH),'data_manifest_sha256':mhash}
    overall=all(a['strict_drawdown_gate_pass'] and all(a['baseline_match'].values()) and a['zero_duration_all_h1_verified'] for a in audits)
    result={'protocol':'Architecture E forensic audit','strategy_rules_changed':False,'oos_tested':False,'oos_locked':'2026-01-01 onward','identity':identity,'data_files':files,'audits':audits,'forensic_gate_pass':overall}
    (out/'audit_results.json').write_text(json.dumps(result,indent=2))
    with (out/'audit_summary.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['config','net_profit','pf','trades','years','dd_realized_pct','dd_close_mtm_pct','dd_intrabar_pct','zero_duration','zero_h1_verified','baseline_match','strict_gate'])
        for a in audits:w.writerow([a['config'],a['net_profit'],a['profit_factor'],a['closed_trades'],a['profitable_years'],a['max_dd_realized_pct'],a['max_dd_close_mtm_pct'],a['max_dd_intrabar_conservative_pct'],a['zero_duration_count'],a['zero_duration_all_h1_verified'],all(a['baseline_match'].values()),a['strict_drawdown_gate_pass']])
    with (out/'data_hash_manifest.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']);w.writeheader();w.writerows(files)
    with (out/'zero_duration_trades.csv').open('w',newline='') as f:
        fields=['config','entry_ts','exit_ts','pnl','reason','duration_hours','stop','entry','exit','first_h1_trigger_ts','h1_verified'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for a in audits:
            for z in a['zero_duration_trades']:
                x={'config':a['config'],**z};w.writerow(x)
    print(json.dumps({'forensic_gate_pass':overall,'audits':[{k:v for k,v in a.items() if k not in ('zero_duration_trades','annual_net_profit')} for a in audits],'identity':identity},indent=2))

if __name__=='__main__':main()
