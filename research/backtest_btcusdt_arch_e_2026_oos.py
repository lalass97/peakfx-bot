#!/usr/bin/env python3
import csv, hashlib, io, json, math, os, subprocess, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
INITIAL=10000.0; RISK=0.0025; COMM=0.001
OOS_START=(2026,1,1); OOS_END_TS=1785542400000  # 2026-08-01 00:00 UTC exclusive
CONFIGS={'BE03':(48,4.0),'BE01':(48,3.0)}
FROZEN_SPEC_COMMIT='1702a3b14f3f9df93715e18fb335d54d9b2eac7c'
FROZEN_SOURCE_COMMIT='f974d17f9f69d3bd26f869612d4eb7cdaa4b2221'
OOS_PROTOCOL_COMMIT='2d0e1f9387e159c1ad1002f387d6c5e04d90b0b1'

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def ms(x): return x//1000 if x>10_000_000_000_000 else x

def load_h1(cache):
    cache.mkdir(parents=True,exist_ok=True); out=[]; manifest=[]
    for y in range(2021,2027):
        months=range(1,8) if y==2026 else range(1,13)
        for m in months:
            fn=f'BTCUSDT-1h-{y}-{m:02d}.zip'; p=cache/fn
            if not p.exists():
                with urllib.request.urlopen(f'{BASE_URL}/{fn}',timeout=60) as r: p.write_bytes(r.read())
            if y==2026: manifest.append({'file':fn,'sha256':sha256_file(p),'bytes':p.stat().st_size})
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names)!=1: raise RuntimeError(fn)
                for row in csv.reader(io.StringIO(z.read(names[0]).decode('utf-8'))):
                    if row and row[0].strip().isdigit():
                        out.append(Bar(ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    uniq={b.ts:b for b in out}; return [uniq[k] for k in sorted(uniq)],manifest

def aggregate_h4(h1):
    groups=[]; cur=[]; key=None
    def flush(g):
        if len(g)==4: groups.append(Bar(g[0].ts,g[0].o,max(x.h for x in g),min(x.l for x in g),g[-1].c,sum(x.v for x in g)))
    for b in h1:
        d=datetime.fromtimestamp(b.ts/1000,timezone.utc); k=(d.year,d.month,d.day,d.hour//4)
        if k!=key: flush(cur); cur=[b]; key=k
        else: cur.append(b)
    flush(cur); return groups

def ema(vals,n):
    out=[None]*len(vals)
    if len(vals)<n:return out
    out[n-1]=sum(vals[:n])/n; a=2/(n+1)
    for i in range(n,len(vals)): out[i]=vals[i]*a+out[i-1]*(1-a)
    return out

def atr(bars,n=14):
    tr=[]
    for i,b in enumerate(bars):
        pc=bars[i-1].c if i else b.c
        tr.append(max(b.h-b.l,abs(b.h-pc),abs(b.l-pc)))
    out=[None]*len(bars); out[n-1]=sum(tr[:n])/n
    for i in range(n,len(bars)): out[i]=(out[i-1]*(n-1)+tr[i])/n
    return out

def run(bars,e200,e100,a14,cfg,lb,mult):
    bal=INITIAL; pos=None; pend=None; pexit=False; trades=[]; gp=gl=0.0; comm=0.0
    peak=INITIAL; maxdd_pct=0.0; maxdd_cash=0.0; curve=[]; integrity=[]
    first_oos=next(i for i,b in enumerate(bars) if datetime.fromtimestamp(b.ts/1000,timezone.utc).year==2026)
    last_index=max(i for i,b in enumerate(bars) if b.ts < OOS_END_TS)
    for i in range(first_oos,last_index+1):
        b=bars[i]
        # prior-bar discretionary exit
        if pos and pexit:
            px=b.o; xc=pos['q']*px*COMM; pp=pos['q']*(px-pos['e']); pnl=pp-pos['ec']-xc
            bal+=pp-xc; comm+=xc; gp+=max(pnl,0); gl+=min(pnl,0)
            trades.append({'config':cfg,'entry_ts':pos['ts'],'exit_ts':b.ts,'entry':pos['e'],'exit':px,'pnl':pnl,'reason':'ema100_exit'})
            pos=None; pexit=False
        # next-open entry from OOS signal only
        if pos is None and pend and pend['i']==i:
            e=b.o; dist=mult*pend['atr']; st=e-dist
            if dist>0 and st>0:
                rc=bal*RISK; q=min(rc/dist,bal/e)
                if q>0:
                    ec=q*e*COMM; bal-=ec; comm+=ec
                    pos={'e':e,'q':q,'st':st,'ec':ec,'ts':b.ts,'hc':e,'risk':q*dist}
            pend=None
        # protective stop frozen before current completed-bar update
        if pos and b.l<=pos['st']:
            px=b.o if b.o<pos['st'] else pos['st']; xc=pos['q']*px*COMM; pp=pos['q']*(px-pos['e']); pnl=pp-pos['ec']-xc
            bal+=pp-xc; comm+=xc; gp+=max(pnl,0); gl+=min(pnl,0)
            trades.append({'config':cfg,'entry_ts':pos['ts'],'exit_ts':b.ts,'entry':pos['e'],'exit':px,'pnl':pnl,'reason':'chandelier_stop'})
            pos=None; pexit=False
        # mark-to-market close equity; include estimated exit commission
        eq=bal if not pos else bal+pos['q']*(b.c-pos['e'])-pos['q']*b.c*COMM
        peak=max(peak,eq); dd=peak-eq; maxdd_cash=max(maxdd_cash,dd); maxdd_pct=max(maxdd_pct,dd/peak if peak else 0.0)
        curve.append({'config':cfg,'ts':b.ts,'balance':bal,'equity_mtm':eq})
        # completed-bar state update / new signal
        if pos:
            pos['hc']=max(pos['hc'],b.c)
            if a14[i] is not None: pos['st']=max(pos['st'],pos['hc']-mult*a14[i])
            if e100[i] is not None and b.c<e100[i] and i<last_index: pexit=True
        elif pend is None and i>=max(200,lb,6):
            if e200[i] is not None and e200[i-6] is not None and a14[i] is not None:
                roc=b.c/bars[i-lb].c-1 if bars[i-lb].c else 0.0
                if b.c>e200[i] and e200[i]>e200[i-6] and roc>0 and i<last_index:
                    pend={'i':i+1,'atr':a14[i]}
    end_eq=curve[-1]['equity_mtm']; net=end_eq-INITIAL
    pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0.0)
    recovery=net/maxdd_cash if maxdd_cash>0 else (math.inf if net>0 else 0.0)
    return {'configuration':cfg,'roc_lookback':lb,'trail_atr':mult,'oos_start':'2026-01-01','oos_end':'2026-07-31','partial_year':True,
            'initial_capital':INITIAL,'ending_equity_mtm':end_eq,'net_profit_mtm':net,'profit_factor_closed_trades':pf,
            'closed_trades':len(trades),'gross_profit':gp,'gross_loss':gl,'total_commission_realized':comm,
            'max_equity_drawdown_pct_mtm':maxdd_pct*100,'max_drawdown_dollars_mtm':maxdd_cash,'recovery_factor_mtm':recovery,
            'open_position_at_end':pos is not None,'integrity_violations':integrity,'trades':trades,'curve':curve}

def main():
    out=Path(os.getenv('BTC_OUT','artifacts/btcusdt-arch-e-2026-oos')); cache=Path(os.getenv('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True)
    h1,manifest=load_h1(cache); bars=aggregate_h4(h1); closes=[b.c for b in bars]; e200=ema(closes,200); e100=ema(closes,100); a14=atr(bars)
    runs=[]; alltr=[]; allcurve=[]
    for cfg,(lb,mult) in CONFIGS.items():
        r=run(bars,e200,e100,a14,cfg,lb,mult); runs.append({k:v for k,v in r.items() if k not in ('trades','curve')}); alltr+=r['trades']; allcurve+=r['curve']
    primary=runs[0]
    gate=(primary['net_profit_mtm']>0 and primary['profit_factor_closed_trades']>=1.20 and primary['max_equity_drawdown_pct_mtm']<=20 and primary['recovery_factor_mtm']>=1.25 and not primary['integrity_violations'])
    result={'protocol':'Frozen Architecture E one-time 2026 OOS','primary':'BE03','secondary':'BE01','oos_window':'2026-01-01 through 2026-07-31 UTC','partial_year':True,
            'frozen_spec_commit':FROZEN_SPEC_COMMIT,'frozen_source_commit':FROZEN_SOURCE_COMMIT,'oos_protocol_commit':OOS_PROTOCOL_COMMIT,
            'runner_head_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'oos_data_files':manifest,'results':runs,'be03_oos_pass':gate,
            'architecture_e_decision':'OOS-confirmed candidate under selection-adjusted evidence' if gate else 'Retire'}
    (out/'oos_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (out/'oos_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','net_profit_mtm','pf_closed','trades','dd_mtm_pct','recovery_mtm','open_at_end','decision'])
        for r in runs:
            dec=('PASS' if gate else 'FAIL') if r['configuration']=='BE03' else 'SUPPORTING_ONLY'
            w.writerow([r['configuration'],r['net_profit_mtm'],r['profit_factor_closed_trades'],r['closed_trades'],r['max_equity_drawdown_pct_mtm'],r['recovery_factor_mtm'],r['open_position_at_end'],dec])
    if alltr:
        with (out/'oos_trades.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(alltr[0].keys())); w.writeheader(); w.writerows(alltr)
    with (out/'oos_equity_curve.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['config','ts','balance','equity_mtm']); w.writeheader(); w.writerows(allcurve)
    with (out/'oos_data_hashes.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']); w.writeheader(); w.writerows(manifest)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
