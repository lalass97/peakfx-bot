#!/usr/bin/env python3
import csv, hashlib, io, json, math, os, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
INITIAL=10000.0
RISK=0.0025
COMMISSION=0.001
DEV_START=int(datetime(2021,1,1,tzinfo=timezone.utc).timestamp()*1000)
DEV_END=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000)
CONFIGS={'BI01':(0.015,2),'BI02':(0.025,2),'BI03':(0.015,3),'BI04':(0.025,3)}

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def ms(x): return x//1000 if x>10_000_000_000_000 else x

def sha256(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for ch in iter(lambda:f.read(1<<20),b''): h.update(ch)
    return h.hexdigest()

def load_h1(cache):
    cache.mkdir(parents=True,exist_ok=True)
    bars=[]; manifest=[]
    for y in range(2020,2026):
        for m in range(1,13):
            fn=f'BTCUSDT-1h-{y}-{m:02d}.zip'; p=cache/fn
            if not p.exists():
                with urllib.request.urlopen(f'{BASE_URL}/{fn}',timeout=60) as r: p.write_bytes(r.read())
            manifest.append({'file':fn,'sha256':sha256(p),'bytes':p.stat().st_size})
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.endswith('.csv')]
                if len(names)!=1: raise RuntimeError(fn)
                for row in csv.reader(io.StringIO(z.read(names[0]).decode())):
                    if not row or not row[0].isdigit(): continue
                    bars.append(Bar(ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    uniq={b.ts:b for b in bars}
    return [uniq[k] for k in sorted(uniq)],manifest

def daily(h1):
    groups={}
    for b in h1:
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc)
        key=int(dt.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000)
        groups.setdefault(key,[]).append(b)
    out=[]; omitted=[]; H=3_600_000
    for k in sorted(groups):
        g=sorted(groups[k],key=lambda x:x.ts); exp=[k+j*H for j in range(24)]
        if len(g)!=24 or [x.ts for x in g]!=exp:
            omitted.append({'day':k,'actual':[x.ts for x in g]}); continue
        out.append(Bar(k,g[0].o,max(x.h for x in g),min(x.l for x in g),g[-1].c,sum(x.v for x in g)))
    return out,omitted

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
    out=[None]*len(bars)
    if len(bars)<n:return out
    out[n-1]=sum(tr[:n])/n
    for i in range(n,len(bars)): out[i]=(out[i-1]*(n-1)+tr[i])/n
    return out

def run(bars,e100,a14,cfg,thr,hold):
    bal=INITIAL; pos=None; pending=None; trades=[]; curve=[]
    annual={y:0.0 for y in range(2021,2026)}; gp=gl=comm=0.0
    peak=INITIAL; maxdd=0.0; maxddpct=0.0; integrity=[]
    idx_by_ts={b.ts:i for i,b in enumerate(bars)}

    def close(px,ts,reason):
        nonlocal bal,pos,gp,gl,comm
        xc=pos['qty']*px*COMMISSION
        price_pnl=pos['qty']*(px-pos['entry'])
        pnl=price_pnl-pos['entry_comm']-xc
        bal+=price_pnl-xc; comm+=xc
        y=datetime.fromtimestamp(ts/1000,timezone.utc).year
        if y in annual: annual[y]+=pnl
        gp+=max(pnl,0); gl+=min(pnl,0)
        trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':ts,'entry':pos['entry'],'exit':px,'stop':pos['stop'],'pnl':pnl,'reason':reason,'duration_hours':(ts-pos['entry_ts'])/3_600_000,'risk_cash':pos['risk_cash']})
        pos=None

    for i,b in enumerate(bars):
        if b.ts<DEV_START or b.ts>=DEV_END: continue
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc)

        if pos is not None and i>=pos['exit_index']:
            close(b.o,b.ts,'time_exit')

        if pos is None and pending is not None and pending['entry_index']==i:
            if dt.weekday()!=0: integrity.append(f'non_monday_entry:{b.ts}')
            entry=b.o; stop=entry-1.5*pending['atr']; dist=entry-stop
            if dist>0:
                risk_budget=bal*RISK; qty=min(risk_budget/dist,bal/entry)
                if qty>0:
                    ec=qty*entry*COMMISSION; bal-=ec; comm+=ec
                    pos={'entry':entry,'entry_ts':b.ts,'entry_index':i,'exit_index':i+hold,'qty':qty,'stop':stop,'entry_comm':ec,'risk_cash':qty*dist}
            pending=None

        if pos is not None:
            if b.o<pos['stop']: close(b.o,b.ts,'stop_gap')
            elif b.l<=pos['stop']: close(pos['stop'],b.ts,'stop')

        mtm=bal if pos is None else bal+pos['qty']*(b.c-pos['entry'])-pos['qty']*b.c*COMMISSION
        peak=max(peak,mtm); dd=peak-mtm; ddpct=dd/peak if peak else 0
        maxdd=max(maxdd,dd); maxddpct=max(maxddpct,ddpct)
        curve.append({'config':cfg,'ts':b.ts,'equity_mtm':mtm,'balance':bal})

        if pos is not None or pending is not None: continue
        if dt.weekday()!=6 or i<100 or e100[i] is None or a14[i] is None: continue
        fri_ts=b.ts-2*86_400_000
        fi=idx_by_ts.get(fri_ts)
        if fi is None: continue
        fri=bars[fi]
        weekend=b.c/fri.c-1
        if weekend>=thr and b.c>e100[i] and i+1<len(bars):
            nd=datetime.fromtimestamp(bars[i+1].ts/1000,timezone.utc)
            if nd.weekday()!=0: integrity.append(f'sunday_not_followed_monday:{b.ts}')
            elif bars[i+1].ts<DEV_END:
                pending={'entry_index':i+1,'atr':a14[i],'signal_ts':b.ts,'weekend_return':weekend}

    last=next((b for b in reversed(bars) if DEV_START<=b.ts<DEV_END),None)
    ending=bal if pos is None or last is None else bal+pos['qty']*(last.c-pos['entry'])-pos['qty']*last.c*COMMISSION
    net=ending-INITIAL; pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0.0); rec=net/maxdd if maxdd>0 else (math.inf if net>0 else 0.0)
    py=sum(v>0 for v in annual.values())
    result={'configuration':cfg,'weekend_threshold':thr,'hold_days':hold,'initial_capital':INITIAL,'ending_equity_mtm':ending,'net_profit_mtm':net,'profit_factor_closed_trades':pf,'closed_trades':len(trades),'wins':sum(t['pnl']>0 for t in trades),'losses':sum(t['pnl']<=0 for t in trades),'gross_profit':gp,'gross_loss':gl,'total_commission':comm,'max_equity_drawdown_pct_mtm':maxddpct*100,'max_drawdown_dollars_mtm':maxdd,'recovery_factor_mtm':rec,'annual_net_profit_closed':annual,'profitable_years':py,'open_position_at_end':pos is not None,'integrity_violations':integrity}
    return result,trades,curve

def passes(r):
    return r['net_profit_mtm']>0 and r['profit_factor_closed_trades']>=1.20 and r['closed_trades']>=40 and r['max_equity_drawdown_pct_mtm']<=20 and r['recovery_factor_mtm']>=1.25 and r['profitable_years']>=4 and not r['integrity_violations']

def main():
    out=Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-i-baseline')); cache=Path(os.environ.get('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True)
    h1,manifest=load_h1(cache); bars,omitted=daily(h1); closes=[b.c for b in bars]; e100=ema(closes,100); a14=atr(bars)
    results=[]; alltr=[]; allcurve=[]
    for cfg,(thr,hold) in CONFIGS.items():
        r,tr,cv=run(bars,e100,a14,cfg,thr,hold); r['daily_incomplete_groups_omitted']=len(omitted); r['decision']='Advance' if passes(r) else 'Retire'; results.append(r); alltr+=tr; allcurve+=cv; print(json.dumps(r,indent=2))
    payload={'protocol':'BTCUSDT Architecture I frozen baseline','strategy':'Weekend-to-Weekday Carry','development_period':'2021-01-01 through 2025-12-31 UTC','oos_2026_loaded':False,'source_data_manifest':manifest,'daily_incomplete_groups_omitted':len(omitted),'results':results,'architecture_decision':'Advance' if any(r['decision']=='Advance' for r in results) else 'Retire'}
    (out/'results.json').write_text(json.dumps(payload,indent=2))
    with (out/'summary.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['configuration','net_profit_mtm','profit_factor_closed_trades','closed_trades','max_equity_drawdown_pct_mtm','recovery_factor_mtm','profitable_years','decision'])
        for r in results:w.writerow([r['configuration'],r['net_profit_mtm'],r['profit_factor_closed_trades'],r['closed_trades'],r['max_equity_drawdown_pct_mtm'],r['recovery_factor_mtm'],r['profitable_years'],r['decision']])
    if alltr:
        with (out/'trades.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(alltr[0])); w.writeheader(); w.writerows(alltr)
    else:(out/'trades.csv').write_text('')
    if allcurve:
        with (out/'equity_curve.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(allcurve[0])); w.writeheader(); w.writerows(allcurve)
    with (out/'data_hashes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']); w.writeheader(); w.writerows(manifest)
if __name__=='__main__': main()
