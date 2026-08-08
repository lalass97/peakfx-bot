#!/usr/bin/env python3
import csv, hashlib, io, json, math, os, statistics, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
INITIAL=10000.0
RISK=0.0025
COMMISSION=0.001
CONFIGS={
 'BJ01':(0.15,1.50,2.0),
 'BJ02':(0.25,1.50,2.0),
 'BJ03':(0.15,2.00,3.0),
 'BJ04':(0.25,2.00,3.0),
}
STAGES={
 'stage1_2021_2023':(datetime(2021,1,1,tzinfo=timezone.utc),datetime(2024,1,1,tzinfo=timezone.utc)),
 'stage2_2024':(datetime(2024,1,1,tzinfo=timezone.utc),datetime(2025,1,1,tzinfo=timezone.utc)),
 'stage3_2025':(datetime(2025,1,1,tzinfo=timezone.utc),datetime(2026,1,1,tzinfo=timezone.utc)),
}

@dataclass
class Bar:
 ts:int;o:float;h:float;l:float;c:float;v:float

def ms(dt): return int(dt.timestamp()*1000)
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for ch in iter(lambda:f.read(1024*1024),b''): h.update(ch)
 return h.hexdigest()

def load_h1(cache):
 cache.mkdir(parents=True,exist_ok=True); bars=[]; manifest=[]
 for y in range(2020,2026):
  for m in range(1,13):
   fn=f'BTCUSDT-1h-{y}-{m:02d}.zip'; p=cache/fn
   if not p.exists():
    with urllib.request.urlopen(f'{BASE_URL}/{fn}',timeout=60) as r: p.write_bytes(r.read())
   manifest.append({'file':fn,'sha256':sha256_file(p),'bytes':p.stat().st_size})
   with zipfile.ZipFile(p) as z:
    names=[n for n in z.namelist() if n.lower().endswith('.csv')]
    if len(names)!=1: raise RuntimeError(f'unexpected zip contents {fn}')
    for row in csv.reader(io.StringIO(z.read(names[0]).decode())):
     if not row or not row[0].strip().isdigit(): continue
     t=int(row[0]); t=t//1000 if t>10_000_000_000_000 else t
     bars.append(Bar(t,float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
 uniq={b.ts:b for b in bars}
 return [uniq[k] for k in sorted(uniq)],manifest

def aggregate_daily(h1):
 groups={}
 for b in h1:
  d=datetime.fromtimestamp(b.ts/1000,timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
  k=int(d.timestamp()*1000); groups.setdefault(k,[]).append(b)
 out=[]; omitted=[]; H=3_600_000
 for k in sorted(groups):
  g=sorted(groups[k],key=lambda x:x.ts); exp=[k+j*H for j in range(24)]
  if len(g)!=24 or [x.ts for x in g]!=exp:
   omitted.append(k); continue
  out.append(Bar(k,g[0].o,max(x.h for x in g),min(x.l for x in g),g[-1].c,sum(x.v for x in g)))
 return out,omitted

def atr(bars,n=20):
 tr=[]
 for i,b in enumerate(bars):
  pc=bars[i-1].c if i else b.c
  tr.append(max(b.h-b.l,abs(b.h-pc),abs(b.l-pc)))
 out=[None]*len(bars)
 if len(bars)<n:return out
 out[n-1]=sum(tr[:n])/n
 for i in range(n,len(bars)): out[i]=(out[i-1]*(n-1)+tr[i])/n
 return out,tr

def rv20(bars):
 rets=[None]
 for i in range(1,len(bars)): rets.append(math.log(bars[i].c/bars[i-1].c))
 rv=[None]*len(bars)
 for i in range(20,len(bars)):
  vals=rets[i-19:i+1]
  if any(v is None for v in vals):continue
  rv[i]=statistics.pstdev(vals)
 pct=[None]*len(bars)
 for i in range(len(bars)):
  if rv[i] is None:continue
  hist=[x for x in rv[max(0,i-252):i] if x is not None]
  if len(hist)<100:continue
  pct[i]=sum(x<=rv[i] for x in hist)/len(hist)
 return rv,pct

def metrics(trades,curve,ending):
 net=ending-INITIAL; gp=sum(max(t['pnl'],0) for t in trades); gl=sum(min(t['pnl'],0) for t in trades)
 pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0.0)
 peak=INITIAL; maxdd=0.0; maxddcash=0.0
 for r in curve:
  eq=r['equity_mtm']; peak=max(peak,eq); d=peak-eq; maxddcash=max(maxddcash,d); maxdd=max(maxdd,d/peak if peak else 0)
 rec=net/maxddcash if maxddcash>0 else (math.inf if net>0 else 0.0)
 return net,pf,maxdd*100,maxddcash,rec,gp,gl

def run_stage(bars,a20,pct,cfg,pars,start,end):
 threshold,expansion,target_r=pars; s=ms(start); e=ms(end)
 balance=INITIAL; pos=None; pending=None; pending_time=False; trades=[];curve=[]; integ=[]; annual={y:0.0 for y in range(start.year,end.year)}
 for i,b in enumerate(bars):
  if b.ts<s or b.ts>=e: continue
  yr=datetime.fromtimestamp(b.ts/1000,timezone.utc).year
  if pos and pending_time:
   px=b.o; xc=pos['qty']*px*COMMISSION; price=pos['qty']*(px-pos['entry']); pnl=price-pos['entry_comm']-xc
   balance+=price-xc; annual[yr]+=pnl; trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'entry':pos['entry'],'exit':px,'pnl':pnl,'reason':'time_exit'}); pos=None;pending_time=False
  if not pos and pending and pending['idx']==i:
   entry=b.o; stop=entry-1.5*pending['atr']; dist=entry-stop
   if dist>0:
    riskcash=balance*RISK; qty=min(riskcash/dist,balance/entry)
    if qty>0:
     ec=qty*entry*COMMISSION; balance-=ec
     pos={'entry':entry,'entry_ts':b.ts,'entry_idx':i,'qty':qty,'stop':stop,'target':entry+target_r*dist,'entry_comm':ec,'risk_cash':qty*dist}
   pending=None
  if pos:
   stophit=b.l<=pos['stop']; targethit=b.h>=pos['target']
   px=None;reason=None
   if b.o<pos['stop']: px=b.o;reason='stop_gap'
   elif b.o>pos['target']: px=b.o;reason='target_gap'
   elif stophit and targethit: px=pos['stop'];reason='stop_both_touched_conservative'
   elif stophit: px=pos['stop'];reason='stop'
   elif targethit: px=pos['target'];reason='target'
   if px is not None:
    xc=pos['qty']*px*COMMISSION; price=pos['qty']*(px-pos['entry']); pnl=price-pos['entry_comm']-xc
    balance+=price-xc;annual[yr]+=pnl;trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'entry':pos['entry'],'exit':px,'pnl':pnl,'reason':reason});pos=None;pending_time=False
  mtm=balance if not pos else balance+pos['qty']*(b.c-pos['entry'])-pos['qty']*b.c*COMMISSION
  curve.append({'ts':b.ts,'equity_mtm':mtm})
  if pos:
   if i-pos['entry_idx']+1>=10: pending_time=True
   continue
  if pending: continue
  if i<273 or a20[i-1] is None: continue
  recent=[pct[j] for j in range(i-5,i) if j>=0 and pct[j] is not None]
  lowreg=any(x<=threshold for x in recent)
  rng=b.h-b.l; tr=max(rng,abs(b.h-bars[i-1].c),abs(b.l-bars[i-1].c))
  upper=(b.c-b.l)/rng if rng>0 else 0
  if lowreg and b.c>b.o and tr>=expansion*a20[i-1] and upper>=0.75 and b.c>bars[i-20].c and i+1<len(bars):
   pending={'idx':i+1,'atr':a20[i] if a20[i] is not None else a20[i-1]}
 ending=balance if not pos else balance+pos['qty']*(bars[max(j for j,x in enumerate(bars) if x.ts<e)].c-pos['entry'])-pos['qty']*bars[max(j for j,x in enumerate(bars) if x.ts<e)].c*COMMISSION
 net,pf,dd,ddcash,rec,gp,gl=metrics(trades,curve,ending)
 return {'configuration':cfg,'stage_start':start.isoformat(),'stage_end_exclusive':end.isoformat(),'net_profit_mtm':net,'ending_equity_mtm':ending,'profit_factor_closed_trades':pf,'closed_trades':len(trades),'max_equity_drawdown_pct_mtm':dd,'max_drawdown_dollars_mtm':ddcash,'recovery_factor_mtm':rec,'gross_profit':gp,'gross_loss':gl,'annual_net_profit_closed':annual,'profitable_years':sum(v>0 for v in annual.values()),'integrity_violations':integ,'trades':trades}

def stage1_pass(r): return r['net_profit_mtm']>0 and r['profit_factor_closed_trades']>=1.20 and r['closed_trades']>=25 and r['max_equity_drawdown_pct_mtm']<=20 and r['recovery_factor_mtm']>=1.25 and r['profitable_years']>=2 and not r['integrity_violations']
def later_pass(r): return r['net_profit_mtm']>0 and r['profit_factor_closed_trades']>=1.10 and r['max_equity_drawdown_pct_mtm']<=20 and r['recovery_factor_mtm']>=1.0 and not r['integrity_violations']

def main():
 out=Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-j')); cache=Path(os.environ.get('BTC_CACHE',out/'data'));out.mkdir(parents=True,exist_ok=True)
 h1,manifest=load_h1(cache); bars,omitted=aggregate_daily(h1); a20,_=atr(bars,20);_,pct=rv20(bars)
 payload={'protocol':'BTCUSDT JKL reset / Architecture J','oos_2026_loaded':False,'daily_incomplete_groups_omitted':len(omitted),'source_data_manifest':manifest,'configs':{},'architecture_decision':'Retire'}
 summary=[];alltr=[]
 for cfg,pars in CONFIGS.items():
  r1=run_stage(bars,a20,pct,cfg,pars,*STAGES['stage1_2021_2023']); p1=stage1_pass(r1); r1['decision']='Advance' if p1 else 'Retire'; alltr+=r1.pop('trades')
  rec={'parameters':{'low_vol_percentile':pars[0],'expansion_atr_multiple':pars[1],'target_r':pars[2]},'stage1':r1}
  final='Retire'
  if p1:
   r2=run_stage(bars,a20,pct,cfg,pars,*STAGES['stage2_2024']); p2=later_pass(r2); r2['decision']='Advance' if p2 else 'Retire'; alltr+=r2.pop('trades');rec['stage2']=r2
   if p2:
    r3=run_stage(bars,a20,pct,cfg,pars,*STAGES['stage3_2025']); p3=later_pass(r3); r3['decision']='Pass' if p3 else 'Retire'; alltr+=r3.pop('trades');rec['stage3']=r3
    if p3: final='Pass'
  rec['final_decision']=final;payload['configs'][cfg]=rec
  summary.append({'configuration':cfg,'stage1_net':r1['net_profit_mtm'],'stage1_pf':r1['profit_factor_closed_trades'],'stage1_trades':r1['closed_trades'],'stage1_years':r1['profitable_years'],'stage1_decision':r1['decision'],'final_decision':final})
  print(json.dumps({'configuration':cfg,**summary[-1]},indent=2))
 if any(x['final_decision']=='Pass' for x in summary): payload['architecture_decision']='Pass'
 (out/'results.json').write_text(json.dumps(payload,indent=2,allow_nan=True))
 with (out/'summary.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=summary[0].keys());w.writeheader();w.writerows(summary)
 with (out/'trades.csv').open('w',newline='') as f:
  fields=['config','entry_ts','exit_ts','entry','exit','pnl','reason'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:t.get(k) for k in fields} for t in alltr])
 with (out/'data_hashes.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']);w.writeheader();w.writerows(manifest)
 print('ARCHITECTURE_DECISION',payload['architecture_decision'])

if __name__=='__main__': main()
