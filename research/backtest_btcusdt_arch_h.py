#!/usr/bin/env python3
import csv, hashlib, io, json, math, os, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

INITIAL_CAPITAL=10000.0
RISK_PCT=0.0025
COMMISSION=0.001
DEV_START=int(datetime(2021,1,1,tzinfo=timezone.utc).timestamp()*1000)
DEV_END=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000)
CONFIGS={
 'BH01':(0.03,0.02,1.5),
 'BH02':(0.04,0.02,1.5),
 'BH03':(0.03,0.03,2.0),
 'BH04':(0.04,0.03,2.0),
}

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def ms(x): return x//1000 if x>10_000_000_000_000 else x

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for ch in iter(lambda:f.read(1<<20),b''): h.update(ch)
    return h.hexdigest()

def load_symbol(sym,cache):
    base=f'https://data.binance.vision/data/spot/monthly/klines/{sym}/1h'
    bars=[]; manifest=[]
    for y in range(2020,2026):
        for m in range(1,13):
            fn=f'{sym}-1h-{y}-{m:02d}.zip'; p=cache/fn
            if not p.exists():
                with urllib.request.urlopen(f'{base}/{fn}',timeout=60) as r: p.write_bytes(r.read())
            manifest.append({'symbol':sym,'file':fn,'sha256':sha256_file(p),'bytes':p.stat().st_size})
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names)!=1: raise RuntimeError(fn)
                for row in csv.reader(io.StringIO(z.read(names[0]).decode())):
                    if not row or not row[0].isdigit(): continue
                    bars.append(Bar(ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    d={b.ts:b for b in bars}; return [d[k] for k in sorted(d)],manifest

def agg_h4(h1):
    g={}
    for b in h1:
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc); hh=(dt.hour//4)*4
        key=int(dt.replace(hour=hh,minute=0,second=0,microsecond=0).timestamp()*1000)
        g.setdefault(key,[]).append(b)
    out=[]; bad=[]
    for key in sorted(g):
        x=sorted(g[key],key=lambda b:b.ts); exp=[key+j*3600000 for j in range(4)]
        if [b.ts for b in x]!=exp: bad.append(key); continue
        out.append(Bar(key,x[0].o,max(b.h for b in x),min(b.l for b in x),x[-1].c,sum(b.v for b in x)))
    return out,bad

def ema(vals,n):
    out=[None]*len(vals)
    if len(vals)<n:return out
    out[n-1]=sum(vals[:n])/n; a=2/(n+1)
    for i in range(n,len(vals)): out[i]=vals[i]*a+out[i-1]*(1-a)
    return out

def atr(bars,n=14):
    tr=[]
    for i,b in enumerate(bars):
        pc=bars[i-1].c if i else b.c; tr.append(max(b.h-b.l,abs(b.h-pc),abs(b.l-pc)))
    out=[None]*len(bars)
    if len(bars)<n:return out
    out[n-1]=sum(tr[:n])/n
    for i in range(n,len(bars)): out[i]=(out[i-1]*(n-1)+tr[i])/n
    return out

def run(btc,eth,e200,a14,cfg,eth_thr,gap_thr,target_r):
    bal=INITIAL_CAPITAL; pos=None; pending=None; time_exit=False; trades=[]; annual={y:0.0 for y in range(2021,2026)}
    gp=gl=comm=0.0; peak=INITIAL_CAPITAL; maxdd=0.0; maxddpct=0.0; curve=[]; integrity=[]
    def close(px,ts,reason):
        nonlocal bal,pos,gp,gl,comm,time_exit
        xc=pos['qty']*px*COMMISSION; price=pos['qty']*(px-pos['entry']); pnl=price-pos['entry_comm']-xc
        bal+=price-xc; comm+=xc; y=datetime.fromtimestamp(ts/1000,timezone.utc).year
        if y in annual: annual[y]+=pnl
        gp+=max(pnl,0); gl+=min(pnl,0)
        trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':ts,'entry':pos['entry'],'exit':px,'pnl':pnl,'reason':reason,'duration_hours':(ts-pos['entry_ts'])/3600000})
        pos=None; time_exit=False
    for i,b in enumerate(btc):
        if b.ts<DEV_START or b.ts>=DEV_END: continue
        if pos is not None and time_exit: close(b.o,b.ts,'time_exit')
        if pos is None and pending is not None and pending['idx']==i:
            entry=b.o; stop=entry-1.5*pending['atr']; dist=entry-stop
            if dist>0:
                risk=bal*RISK_PCT; qty=min(risk/dist,bal/entry)
                if qty>0:
                    ec=qty*entry*COMMISSION; bal-=ec; comm+=ec
                    pos={'entry':entry,'entry_ts':b.ts,'entry_idx':i,'qty':qty,'stop':stop,'target':entry+target_r*dist,'entry_comm':ec}
            pending=None
        if pos is not None:
            if b.o<pos['stop']: close(b.o,b.ts,'stop_gap')
            elif b.o>pos['target']: close(b.o,b.ts,'target_gap')
            else:
                sh=b.l<=pos['stop']; th=b.h>=pos['target']
                if sh and th: close(pos['stop'],b.ts,'stop_both_conservative')
                elif sh: close(pos['stop'],b.ts,'stop')
                elif th: close(pos['target'],b.ts,'target')
        mtm=bal if pos is None else bal+pos['qty']*(b.c-pos['entry'])-pos['qty']*b.c*COMMISSION
        peak=max(peak,mtm); dd=peak-mtm; maxdd=max(maxdd,dd); maxddpct=max(maxddpct,dd/peak if peak else 0)
        curve.append({'config':cfg,'ts':b.ts,'equity_mtm':mtm})
        if pos is not None:
            if i-pos['entry_idx']+1>=6: time_exit=True
            continue
        if pending is not None: continue
        if i<max(200,12,6) or i+1>=len(btc) or e200[i] is None or e200[i-12] is None or a14[i] is None: continue
        broc=b.c/btc[i-6].c-1; eroc=eth[i].c/eth[i-6].c-1; lead=eroc-broc
        if b.c>e200[i] and e200[i]>e200[i-12] and eroc>=eth_thr and lead>=gap_thr and broc>-0.02 and broc<eroc:
            pending={'idx':i+1,'atr':a14[i]}
    last=next((b for b in reversed(btc) if DEV_START<=b.ts<DEV_END),None)
    endeq=bal if pos is None or last is None else bal+pos['qty']*(last.c-pos['entry'])-pos['qty']*last.c*COMMISSION
    net=endeq-INITIAL_CAPITAL; pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0); rec=net/maxdd if maxdd>0 else (math.inf if net>0 else 0)
    years=sum(v>0 for v in annual.values())
    r={'configuration':cfg,'eth_roc24_threshold':eth_thr,'lead_gap_threshold':gap_thr,'target_r':target_r,'net_profit_mtm':net,'ending_equity_mtm':endeq,'profit_factor_closed_trades':pf,'closed_trades':len(trades),'wins':sum(t['pnl']>0 for t in trades),'losses':sum(t['pnl']<=0 for t in trades),'max_equity_drawdown_pct_mtm':maxddpct*100,'max_drawdown_dollars_mtm':maxdd,'recovery_factor_mtm':rec,'annual_net_profit_closed':annual,'profitable_years':years,'total_commission':comm,'open_position_at_end':pos is not None,'integrity_violations':integrity}
    r['decision']='Advance' if net>0 and pf>=1.2 and len(trades)>=60 and maxddpct*100<=20 and rec>=1.25 and years>=4 and not integrity else 'Retire'
    return r,trades,curve

def main():
    out=Path(os.getenv('BTC_OUT','artifacts/btcusdt-arch-h-baseline')); cache=Path(os.getenv('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True); cache.mkdir(parents=True,exist_ok=True)
    bh1,bm=load_symbol('BTCUSDT',cache); eh1,em=load_symbol('ETHUSDT',cache); b4,bbad=agg_h4(bh1); e4,ebad=agg_h4(eh1)
    bd={b.ts:b for b in b4}; ed={b.ts:b for b in e4}; ts=sorted(set(bd)&set(ed)); btc=[bd[t] for t in ts]; eth=[ed[t] for t in ts]
    e200=ema([b.c for b in btc],200); a14=atr(btc)
    results=[]; trades=[]; curve=[]
    for cfg,(et,gt,tr) in CONFIGS.items():
        r,t,c=run(btc,eth,e200,a14,cfg,et,gt,tr); r['btc_incomplete_h4_omitted']=len(bbad); r['eth_incomplete_h4_omitted']=len(ebad); results.append(r); trades+=t; curve+=c; print(json.dumps(r,indent=2))
    payload={'protocol':'BTCUSDT Architecture H frozen baseline','strategy':'ETH-led BTC catch-up','development_period':'2021-01-01 through 2025-12-31 UTC','oos_2026_loaded':False,'source_data_manifest':bm+em,'results':results,'architecture_decision':'Advance' if any(r['decision']=='Advance' for r in results) else 'Retire'}
    (out/'results.json').write_text(json.dumps(payload,indent=2))
    with (out/'summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['configuration','net_profit_mtm','profit_factor_closed_trades','closed_trades','max_equity_drawdown_pct_mtm','recovery_factor_mtm','profitable_years','decision']); w.writeheader(); [w.writerow({k:r[k] for k in w.fieldnames}) for r in results]
    with (out/'trades.csv').open('w',newline='') as f:
        fields=['config','entry_ts','exit_ts','entry','exit','pnl','reason','duration_hours']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(trades)
    with (out/'equity_curve.csv').open('w',newline='') as f:
        fields=['config','ts','equity_mtm']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(curve)
    with (out/'data_hashes.csv').open('w',newline='') as f:
        fields=['symbol','file','sha256','bytes']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(bm+em)
if __name__=='__main__': main()
