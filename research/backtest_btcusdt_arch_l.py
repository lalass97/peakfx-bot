#!/usr/bin/env python3
import csv, io, json, math, os, statistics, urllib.request, zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-l-reset'))
CACHE = Path(os.environ.get('BTC_CACHE', str(OUT/'data')))
OUT.mkdir(parents=True, exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True)
SYMBOL='BTCUSDT'; COMM=0.001; INITIAL=10000.0; RISK_FRAC=0.0025
CONFIGS={
 'BL01':dict(ac_n=42, ac_thr=0.15, hold=6, target_r=1.5),
 'BL02':dict(ac_n=84, ac_thr=0.15, hold=6, target_r=1.5),
 'BL03':dict(ac_n=42, ac_thr=0.25, hold=9, target_r=2.0),
 'BL04':dict(ac_n=84, ac_thr=0.25, hold=9, target_r=2.0),
}

def month_iter(y0,m0,y1,m1):
    y,m=y0,m0
    while (y,m)<=(y1,m1):
        yield y,m
        m+=1
        if m==13:y+=1;m=1

def dl_month(y,m):
    name=f'{SYMBOL}-1h-{y}-{m:02d}.zip'; p=CACHE/name
    if not p.exists():
        url=f'https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/1h/{name}'
        with urllib.request.urlopen(url, timeout=60) as r: p.write_bytes(r.read())
    return p

def read_h1(y0,m0,y1,m1):
    rows=[]
    for y,m in month_iter(y0,m0,y1,m1):
        p=dl_month(y,m)
        with zipfile.ZipFile(p) as z:
            fn=z.namelist()[0]
            data=io.TextIOWrapper(z.open(fn),'utf-8')
            for r in csv.reader(data):
                if not r or not r[0].isdigit(): continue
                ts=int(r[0]);
                if ts>10**14: ts//=1000
                rows.append((ts,float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[5])))
    rows.sort(key=lambda x:x[0]); return rows

def h4_aggregate(h1):
    g=defaultdict(list)
    for r in h1:
        dt=datetime.fromtimestamp(r[0]/1000,tz=timezone.utc)
        k=(dt.year,dt.month,dt.day,dt.hour//4)
        g[k].append(r)
    out=[]; omitted=0
    for k in sorted(g):
        xs=g[k]
        if len(xs)!=4: omitted+=1; continue
        out.append(dict(ts=xs[0][0],o=xs[0][1],h=max(x[2] for x in xs),l=min(x[3] for x in xs),c=xs[-1][4],v=sum(x[5] for x in xs)))
    return out,omitted

def ema(vals,n):
    out=[None]*len(vals)
    if len(vals)<n:return out
    s=sum(vals[:n])/n; out[n-1]=s; a=2/(n+1)
    for i in range(n,len(vals)):
        s=a*vals[i]+(1-a)*s; out[i]=s
    return out

def atr_wilder(bars,n=14):
    tr=[]
    for i,b in enumerate(bars):
        pc=bars[i-1]['c'] if i else b['c']
        tr.append(max(b['h']-b['l'],abs(b['h']-pc),abs(b['l']-pc)))
    out=[None]*len(bars)
    if len(tr)<n:return out
    a=sum(tr[:n])/n; out[n-1]=a
    for i in range(n,len(tr)):
        a=((n-1)*a+tr[i])/n; out[i]=a
    return out

def autocorr1(xs):
    if len(xs)<3:return None
    a=xs[:-1]; b=xs[1:]; ma=sum(a)/len(a); mb=sum(b)/len(b)
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b)); da=sum((x-ma)**2 for x in a); db=sum((y-mb)**2 for y in b)
    if da<=0 or db<=0:return 0.0
    return num/math.sqrt(da*db)

def prep(bars):
    closes=[b['c'] for b in bars]; e200=ema(closes,200); atr=atr_wilder(bars,14)
    rets=[None]
    for i in range(1,len(bars)): rets.append(math.log(bars[i]['c']/bars[i-1]['c']))
    return e200,atr,rets

def year_of(ts): return datetime.fromtimestamp(ts/1000,tz=timezone.utc).year

def run_stage(allbars, start_year, end_year, cfg):
    e200,atrs,rets=prep(allbars)
    ac=[None]*len(allbars)
    n=cfg['ac_n']
    for i in range(len(allbars)):
        if i-n+1>=1:
            xs=rets[i-n+1:i+1]
            if all(x is not None for x in xs): ac[i]=autocorr1(xs)
    eq=INITIAL; peak=INITIAL; maxdd=0.0; maxdd_d=0.0; pos=None; pending=None; trades=[]; annual=defaultdict(float); violations=[]
    def mtm(mark):
        nonlocal peak,maxdd,maxdd_d
        val=eq
        if pos: val += pos['qty']*(mark-pos['entry'])
        if val>peak: peak=val
        dd=peak-val
        if dd>maxdd_d:maxdd_d=dd
        if peak>0:maxdd=max(maxdd,100*dd/peak)
    for i,b in enumerate(allbars):
        y=year_of(b['ts'])
        # execute a pending entry only inside the scored stage
        if pending is not None and pending==i and pos is None and start_year<=y<=end_year:
            sig=i-1
            if atrs[sig] and atrs[sig]>0:
                entry=b['o']; stopdist=2.5*atrs[sig]; riskcash=eq*RISK_FRAC
                qty=min(riskcash/stopdist, eq/entry)
                if qty>0:
                    fee=qty*entry*COMM; eq-=fee
                    pos=dict(entry=entry,qty=qty,stop=entry-stopdist,target=entry+cfg['target_r']*stopdist,entry_i=i,entry_fee=fee)
            pending=None
        if pos and start_year<=y<=end_year:
            exit_px=None; reason=None
            # conservative same-bar ordering: stop checked first
            if b['l']<=pos['stop']:
                exit_px=min(pos['stop'],b['o']); reason='stop'
            elif b['h']>=pos['target']:
                exit_px=pos['target']; reason='target'
            elif i-pos['entry_i']>=cfg['hold']:
                exit_px=b['o']; reason='time'
            if exit_px is not None:
                fee=pos['qty']*exit_px*COMM
                gross=pos['qty']*(exit_px-pos['entry'])
                pnl=gross-pos['entry_fee']-fee
                # entry fee already deducted, so add gross then deduct exit fee
                eq += gross-fee
                trades.append(dict(entry_i=pos['entry_i'],exit_i=i,entry=pos['entry'],exit=exit_px,pnl=pnl,reason=reason,exit_year=y))
                annual[y]+=pnl; pos=None
        if start_year<=y<=end_year: mtm(b['c'])
        # create next-bar signal only from completed current bar and only within stage
        if pos is None and pending is None and start_year<=y<=end_year and i+1<len(allbars):
            if e200[i] is not None and atrs[i] is not None and ac[i] is not None and rets[i] is not None and rets[i-1] is not None:
                if b['c']>e200[i] and ac[i]>=cfg['ac_thr'] and rets[i]>=0.0075 and rets[i-1]>0:
                    pending=i+1
    # force close any stage-end position at final in-stage close
    if pos:
        inds=[j for j,b in enumerate(allbars) if start_year<=year_of(b['ts'])<=end_year]
        if inds:
            j=inds[-1]; px=allbars[j]['c']; fee=pos['qty']*px*COMM; gross=pos['qty']*(px-pos['entry']); pnl=gross-pos['entry_fee']-fee; eq+=gross-fee
            y=year_of(allbars[j]['ts']); annual[y]+=pnl; trades.append(dict(entry_i=pos['entry_i'],exit_i=j,entry=pos['entry'],exit=px,pnl=pnl,reason='stage_end',exit_year=y)); pos=None
    net=eq-INITIAL
    gp=sum(max(0,t['pnl']) for t in trades); gl=sum(min(0,t['pnl']) for t in trades)
    pf=(gp/abs(gl)) if gl<0 else (float('inf') if gp>0 else 0.0)
    recovery=(net/maxdd_d) if maxdd_d>0 else (float('inf') if net>0 else 0.0)
    py=sum(1 for y in range(start_year,end_year+1) if annual[y]>0)
    return dict(net=net,pf=pf,trades=len(trades),dd_pct=maxdd,recovery=recovery,profitable_years=py,annual={str(y):annual[y] for y in range(start_year,end_year+1)},integrity_violations=violations,trade_rows=trades)

def pass_stage1(r): return r['net']>0 and r['pf']>=1.20 and r['trades']>=40 and r['dd_pct']<=20 and r['recovery']>=1.25 and r['profitable_years']>=2 and not r['integrity_violations']
def pass_later(r): return r['net']>0 and r['pf']>=1.20 and r['dd_pct']<=20 and r['recovery']>=1.25 and not r['integrity_violations']

def main():
    # Stage 1 deliberately downloads no data later than 2023.
    bars1,omit1=h4_aggregate(read_h1(2020,1,2023,12))
    results={}; stage1_pass=[]
    for name,cfg in CONFIGS.items():
        r=run_stage(bars1,2021,2023,cfg); ok=pass_stage1(r)
        results[name]={'configuration':name,'params':cfg,'stage1':{k:v for k,v in r.items() if k!='trade_rows'},'stage1_decision':'Advance' if ok else 'Retire','final_decision':'Pending' if ok else 'Retire'}
        if ok:stage1_pass.append(name)
    # Only now may 2024 be accessed, and only if at least one configuration passed Stage 1.
    if stage1_pass:
        bars2,omit2=h4_aggregate(read_h1(2020,1,2024,12))
        stage2_pass=[]
        for name in stage1_pass:
            r=run_stage(bars2,2024,2024,CONFIGS[name]); ok=pass_later(r)
            results[name]['stage2']={k:v for k,v in r.items() if k!='trade_rows'}; results[name]['stage2_decision']='Advance' if ok else 'Retire'; results[name]['final_decision']='Pending' if ok else 'Retire'
            if ok:stage2_pass.append(name)
        # Only now may 2025 be accessed.
        if stage2_pass:
            bars3,omit3=h4_aggregate(read_h1(2020,1,2025,12))
            for name in stage2_pass:
                r=run_stage(bars3,2025,2025,CONFIGS[name]); ok=pass_later(r)
                results[name]['stage3']={k:v for k,v in r.items() if k!='trade_rows'}; results[name]['stage3_decision']='Confirm' if ok else 'Retire'; results[name]['final_decision']='Confirm' if ok else 'Retire'
    architecture_decision='Confirm' if any(v['final_decision']=='Confirm' for v in results.values()) else 'Retire'
    payload={'protocol':'BTCUSDT J/K/L reset — Architecture L frozen baseline','architecture':'L statistical serial-persistence regime','oos_2026_accessed':False,'architecture_decision':architecture_decision,'stage1_h4_incomplete_groups_omitted':omit1,'configurations':results}
    (OUT/'results.json').write_text(json.dumps(payload,indent=2,allow_nan=True))
    with (OUT/'summary.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['configuration','stage1_net','stage1_pf','stage1_trades','stage1_dd_pct','stage1_recovery','stage1_years','stage1_decision','final_decision'])
        for n,v in results.items():
            r=v['stage1']; w.writerow([n,r['net'],r['pf'],r['trades'],r['dd_pct'],r['recovery'],r['profitable_years'],v['stage1_decision'],v['final_decision']])
    for n,v in results.items(): print(json.dumps(v,indent=2,allow_nan=True))
    print('ARCHITECTURE_DECISION',architecture_decision)

if __name__=='__main__': main()
