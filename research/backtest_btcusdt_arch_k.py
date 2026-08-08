#!/usr/bin/env python3
import csv, io, json, math, os, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
INIT=10000.0; RISK=.0025; COMM=.001
CONFIGS={'BK01':(.02,1.5,2.0),'BK02':(.03,1.5,2.0),'BK03':(.02,2.0,3.0),'BK04':(.03,2.0,3.0)}

@dataclass
class B: ts:int; o:float; h:float; l:float; c:float; v:float

def ms(x): return x//1000 if x>10_000_000_000_000 else x

def load_years(cache, years):
    out=[]; cache.mkdir(parents=True,exist_ok=True)
    for y in years:
      for m in range(1,13):
        fn=f'BTCUSDT-1h-{y}-{m:02d}.zip'; p=cache/fn
        if not p.exists():
          with urllib.request.urlopen(f'{BASE}/{fn}',timeout=60) as r: p.write_bytes(r.read())
        with zipfile.ZipFile(p) as z:
          n=[x for x in z.namelist() if x.endswith('.csv')][0]
          for r in csv.reader(io.StringIO(z.read(n).decode())):
            if r and r[0].isdigit(): out.append(B(ms(int(r[0])),*(float(r[i]) for i in range(1,6))))
    d={b.ts:b for b in out}; return [d[k] for k in sorted(d)]

def h4(h1):
    g={}
    for b in h1:
      dt=datetime.fromtimestamp(b.ts/1000,timezone.utc); hh=(dt.hour//4)*4
      k=int(dt.replace(hour=hh,minute=0,second=0,microsecond=0).timestamp()*1000); g.setdefault(k,[]).append(b)
    out=[]
    for k in sorted(g):
      x=sorted(g[k],key=lambda q:q.ts)
      if len(x)==4 and [q.ts for q in x]==[k+i*3600000 for i in range(4)]: out.append(B(k,x[0].o,max(q.h for q in x),min(q.l for q in x),x[-1].c,sum(q.v for q in x)))
    return out

def ema(v,n):
    z=[None]*len(v)
    if len(v)<n:return z
    z[n-1]=sum(v[:n])/n; a=2/(n+1)
    for i in range(n,len(v)): z[i]=a*v[i]+(1-a)*z[i-1]
    return z

def atr(b,n=14):
    tr=[]
    for i,x in enumerate(b):
      pc=b[i-1].c if i else x.c; tr.append(max(x.h-x.l,abs(x.h-pc),abs(x.l-pc)))
    z=[None]*len(b)
    if len(b)<n:return z
    z[n-1]=sum(tr[:n])/n
    for i in range(n,len(b)): z[i]=(z[i-1]*(n-1)+tr[i])/n
    return z

def run_stage(bars,start,end,cfg,imp,vm,target):
    c=[x.c for x in bars]; e=ema(c,200); a=atr(bars); bal=INIT; pos=None; pend=None; trades=[]; gp=gl=0.0; annual={}
    peak=INIT; maxdd=0.0
    for i,b in enumerate(bars):
      if not(start<=b.ts<end): continue
      yr=datetime.fromtimestamp(b.ts/1000,timezone.utc).year; annual.setdefault(yr,0.0)
      if pos and pos.get('time_exit'):
        px=b.o; xc=pos['q']*px*COMM; pnl=pos['q']*(px-pos['en'])-pos['ec']-xc; bal+=pos['q']*(px-pos['en'])-xc; gp+=max(0,pnl); gl+=min(0,pnl); annual[yr]+=pnl; trades.append(pnl); pos=None
      if not pos and pend and pend['i']==i:
        en=b.o; sd=1.5*pend['atr']; st=en-sd
        if sd>0 and st>0:
          q=min((bal*RISK)/sd,bal/en); ec=q*en*COMM; bal-=ec; pos={'en':en,'q':q,'ec':ec,'st':st,'tg':en+target*sd,'ei':i}
        pend=None
      if pos:
        if b.o<pos['st']: px=b.o
        elif b.o>pos['tg']: px=b.o
        elif b.l<=pos['st']: px=pos['st']
        elif b.h>=pos['tg']: px=pos['tg']
        else: px=None
        if px is not None:
          xc=pos['q']*px*COMM; pnl=pos['q']*(px-pos['en'])-pos['ec']-xc; bal+=pos['q']*(px-pos['en'])-xc; gp+=max(0,pnl); gl+=min(0,pnl); annual[yr]+=pnl; trades.append(pnl); pos=None
      mtm=bal if not pos else bal+pos['q']*(b.c-pos['en'])-pos['q']*b.c*COMM
      peak=max(peak,mtm); maxdd=max(maxdd,peak-mtm)
      if pos:
        if i-pos['ei']+1>=12: pos['time_exit']=True
        continue
      if i>=212 and e[i] is not None and e[i-12] is not None and a[i] is not None:
        meanv=sum(x.v for x in bars[i-20:i])/20
        if b.c>e[i] and e[i]>e[i-12] and (b.c/b.o-1)>=imp and b.v>=vm*meanv and i+1<len(bars): pend={'i':i+1,'atr':a[i]}
    if pos:
      last=max((x for x in bars if start<=x.ts<end),key=lambda x:x.ts); mtm=bal+pos['q']*(last.c-pos['en'])-pos['q']*last.c*COMM
    else: mtm=bal
    net=mtm-INIT; pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0); rec=net/maxdd if maxdd>0 else 0; years=sum(v>0 for v in annual.values())
    return {'configuration':cfg,'net':net,'pf':pf,'trades':len(trades),'dd_pct':100*maxdd/peak if peak else 0,'recovery':rec,'profitable_years':years,'annual':annual}

def gate1(r): return r['net']>0 and r['pf']>=1.2 and r['trades']>=40 and r['dd_pct']<=20 and r['recovery']>=1.25 and r['profitable_years']>=2
def gate_later(r): return r['net']>0 and r['pf']>=1.1 and r['dd_pct']<=20 and r['recovery']>=1.0

def main():
    out=Path(os.getenv('BTC_OUT','artifacts/btcusdt-arch-k-reset')); cache=Path(os.getenv('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True)
    # Stage 1 only: warm-up 2020 + 2021-2023. 2024/2025 are conditionally fetched only after passes.
    bars=h4(load_years(cache,range(2020,2024))); s1a=int(datetime(2021,1,1,tzinfo=timezone.utc).timestamp()*1000); s1b=int(datetime(2024,1,1,tzinfo=timezone.utc).timestamp()*1000)
    rows=[]; adv=[]
    for cfg,(imp,vm,tg) in CONFIGS.items():
      r=run_stage(bars,s1a,s1b,cfg,imp,vm,tg); r['stage1_decision']='Advance' if gate1(r) else 'Retire'; rows.append({'configuration':cfg,'stage1':r});
      if gate1(r): adv.append(cfg)
    if adv:
      bars=h4(load_years(cache,range(2020,2025))); a=int(datetime(2024,1,1,tzinfo=timezone.utc).timestamp()*1000); b=int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp()*1000)
      for row in rows:
        if row['configuration'] in adv:
          p=CONFIGS[row['configuration']]; r=run_stage(bars,a,b,row['configuration'],*p); r['stage2_decision']='Advance' if gate_later(r) else 'Retire'; row['stage2']=r
      adv2=[r['configuration'] for r in rows if r.get('stage2',{}).get('stage2_decision')=='Advance']
      if adv2:
        bars=h4(load_years(cache,range(2020,2026))); a=int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp()*1000); b=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000)
        for row in rows:
          if row['configuration'] in adv2:
            p=CONFIGS[row['configuration']]; r=run_stage(bars,a,b,row['configuration'],*p); r['stage3_decision']='Advance' if gate_later(r) else 'Retire'; row['stage3']=r
    for row in rows:
      row['final_decision']='Advance' if row.get('stage3',{}).get('stage3_decision')=='Advance' else 'Retire'; print(json.dumps(row,indent=2))
    payload={'protocol':'BTCUSDT J/K/L reset Architecture K','oos_2026_loaded':False,'results':rows,'architecture_decision':'Advance' if any(r['final_decision']=='Advance' for r in rows) else 'Retire'}
    (out/'results.json').write_text(json.dumps(payload,indent=2))
    with (out/'summary.csv').open('w',newline='') as f:
      w=csv.writer(f); w.writerow(['configuration','stage1_net','stage1_pf','stage1_trades','stage1_years','stage1_decision','final_decision'])
      for r in rows:
        s=r['stage1']; w.writerow([r['configuration'],s['net'],s['pf'],s['trades'],s['profitable_years'],s['stage1_decision'],r['final_decision']])

if __name__=='__main__': main()
