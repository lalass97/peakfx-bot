#!/usr/bin/env python3
import csv,hashlib,io,json,math,os,subprocess,urllib.request,zipfile
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
BASE='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'; Y0,Y1=2021,2025; INITIAL=10000.; RISK=.0025; COMM=.001
CONFIGS={'BE01':(48,3.0),'BE03':(48,4.0)}
EXPECTED={'BE01':(1252.4221857250013,1.6930126258479232,225,4),'BE03':(1045.341909420942,2.048162906987389,179,4)}
SPEC='docs/BTCUSDT_ARCH_E_FROZEN_BASELINE_SPEC.md'; SRC='research/backtest_btcusdt_arch_e.py'
@dataclass
class B: ts:int;o:float;h:float;l:float;c:float;v:float

def fsha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for x in iter(lambda:f.read(1<<20),b''):h.update(x)
 return h.hexdigest()
def git(*a):return subprocess.check_output(['git',*a],text=True).strip()
def ms(x):return x//1000 if x>10_000_000_000_000 else x

def load(cache):
 cache.mkdir(parents=True,exist_ok=True);out=[];manifest=[]
 for y in range(Y0,Y1+1):
  for m in range(1,13):
   fn=f'BTCUSDT-1h-{y}-{m:02d}.zip';p=cache/fn
   if not p.exists():
    with urllib.request.urlopen(f'{BASE}/{fn}',timeout=60) as r:p.write_bytes(r.read())
   sh=fsha(p);manifest.append({'file':fn,'sha256':sh,'bytes':p.stat().st_size})
   with zipfile.ZipFile(p) as z:
    n=[q for q in z.namelist() if q.endswith('.csv')][0]
    for r in csv.reader(io.StringIO(z.read(n).decode())):
     if r and r[0].isdigit():out.append(B(ms(int(r[0])),*map(float,r[1:6])))
 out={x.ts:x for x in out};out=[out[k] for k in sorted(out)]
 raw='\n'.join(f"{x['file']} {x['sha256']} {x['bytes']}" for x in manifest).encode()
 return out,manifest,hashlib.sha256(raw).hexdigest()

def h4(h1):
 out=[];kids={};cur=[];key=None
 def flush(g):
  if len(g)==4:
   x=B(g[0].ts,g[0].o,max(q.h for q in g),min(q.l for q in g),g[-1].c,sum(q.v for q in g));out.append(x);kids[x.ts]=g[:]
 for x in h1:
  d=datetime.fromtimestamp(x.ts/1000,timezone.utc);k=(d.year,d.month,d.day,d.hour//4)
  if k!=key:flush(cur);cur=[x];key=k
  else:cur.append(x)
 flush(cur);return out,kids

def ema(v,n):
 z=[None]*len(v)
 if len(v)<n:return z
 z[n-1]=sum(v[:n])/n;a=2/(n+1)
 for i in range(n,len(v)):z[i]=v[i]*a+z[i-1]*(1-a)
 return z

def atr(b,n=14):
 tr=[]
 for i,x in enumerate(b):
  pc=b[i-1].c if i else x.c;tr.append(max(x.h-x.l,abs(x.h-pc),abs(x.l-pc)))
 z=[None]*len(b);z[n-1]=sum(tr[:n])/n
 for i in range(n,len(b)):z[i]=(z[i-1]*(n-1)+tr[i])/n
 return z

def upd(eq,peak,ddcash,ddpct):
 peak=max(peak,eq);cash=peak-eq;return peak,max(ddcash,cash),max(ddpct,cash/peak if peak else 0.)

def run(bars,kids,e200,e100,a14,cfg,lb,mult):
 bal=INITIAL;gp=gl=0.;pos=None;pend=None;pexit=False;annual={y:0. for y in range(Y0,Y1+1)};trades=[];zero=[];viol=[]
 peak_r=peak_c=peak_w=INITIAL;dc_r=dc_c=dc_w=0.;dp_r=dp_c=dp_w=0.
 for i,b in enumerate(bars):
  yr=datetime.fromtimestamp(b.ts/1000,timezone.utc).year
  if not Y0<=yr<=Y1:continue
  if pos and pexit:
   px=b.o;xc=pos['q']*px*COMM;pp=pos['q']*(px-pos['e']);pnl=pp-pos['ec']-xc;bal+=pp-xc;gp+=max(pnl,0);gl+=min(pnl,0);annual[yr]+=pnl;trades.append((pos['ts'],b.ts,pnl,'ema100_exit'));pos=None;pexit=False
  if pos is None and pend and pend['i']==i:
   e=b.o;dist=mult*pend['atr'];st=e-dist
   if dist>0 and st>0:
    rc=bal*RISK;q=min(rc/dist,bal/e)
    if q>0:
     ec=q*e*COMM;bal-=ec;pos={'e':e,'q':q,'st':st,'ec':ec,'ts':b.ts,'hc':e,'risk':q*dist}
   pend=None
  # worst-case intrabar envelope: favorable high may establish peak, then executable adverse price establishes trough.
  if pos:
   high_eq=bal+pos['q']*(b.h-pos['e'])-pos['q']*b.h*COMM
   peak_w=max(peak_w,high_eq)
   adverse=b.l
   if b.o<pos['st']:adverse=b.o
   elif b.l<=pos['st']:adverse=pos['st']
   low_eq=bal+pos['q']*(adverse-pos['e'])-pos['q']*adverse*COMM
   _,dc_w,dp_w=upd(low_eq,peak_w,dc_w,dp_w)
  if pos and b.l<=pos['st']:
   px=b.o if b.o<pos['st'] else pos['st'];xc=pos['q']*px*COMM;pp=pos['q']*(px-pos['e']);pnl=pp-pos['ec']-xc;bal+=pp-xc;gp+=max(pnl,0);gl+=min(pnl,0);annual[yr]+=pnl
   dur=(b.ts-pos['ts'])/3600000;trades.append((pos['ts'],b.ts,pnl,'chandelier_stop'))
   if dur==0:
    trig=None
    for q in kids.get(b.ts,[]):
     if q.ts>=pos['ts'] and q.l<=pos['st']:trig=q.ts;break
    z={'config':cfg,'entry_ts':pos['ts'],'exit_ts':b.ts,'entry':pos['e'],'stop':pos['st'],'exit':px,'pnl':pnl,'first_h1_trigger_ts':trig,'h1_verified':trig is not None};zero.append(z)
    if trig is None:viol.append(f'No H1 trigger for same-H4 stop {b.ts}')
   pos=None;pexit=False
  peak_r,dc_r,dp_r=upd(bal,peak_r,dc_r,dp_r)
  ce=bal if not pos else bal+pos['q']*(b.c-pos['e'])-pos['q']*b.c*COMM
  peak_c,dc_c,dp_c=upd(ce,peak_c,dc_c,dp_c)
  if not pos:peak_w,dc_w,dp_w=upd(bal,peak_w,dc_w,dp_w)
  if pos:
   pos['hc']=max(pos['hc'],b.c)
   if a14[i] is not None:pos['st']=max(pos['st'],pos['hc']-mult*a14[i])
   if e100[i] is not None and b.c<e100[i] and i+1<len(bars):pexit=True
  elif pend is None and i>=max(200,lb,6):
   if e200[i] is None or e200[i-6] is None or a14[i] is None:continue
   roc=b.c/bars[i-lb].c-1 if bars[i-lb].c else 0.
   if b.c>e200[i] and e200[i]>e200[i-6] and roc>0 and i+1<len(bars):pend={'i':i+1,'atr':a14[i]}
 net=bal-INITIAL;pf=gp/abs(gl);years=sum(v>0 for v in annual.values());en,ep,et,ey=EXPECTED[cfg]
 match={'net':abs(net-en)<1e-6,'pf':abs(pf-ep)<1e-9,'trades':len(trades)==et,'years':years==ey}
 rec_w=net/dc_w if dc_w>0 else math.inf
 gate=net>0 and pf>=1.20 and len(trades)>=50 and dp_w*100<=20 and rec_w>=1.25 and years>=4 and not viol and all(match.values()) and all(z['h1_verified'] for z in zero)
 return {'config':cfg,'net_profit':net,'profit_factor':pf,'closed_trades':len(trades),'profitable_years':years,'annual_net_profit':annual,'baseline_match':match,
 'max_dd_realized_pct':dp_r*100,'max_dd_realized_cash':dc_r,'max_dd_close_mtm_pct':dp_c*100,'max_dd_close_mtm_cash':dc_c,
 'max_dd_intrabar_worstcase_pct':dp_w*100,'max_dd_intrabar_worstcase_cash':dc_w,'recovery_intrabar_worstcase':rec_w,
 'zero_duration_count':len(zero),'zero_duration_all_h1_verified':all(z['h1_verified'] for z in zero),'zero_duration_trades':zero,'integrity_violations':viol,'strict_gate_pass':gate}

def main():
 out=Path(os.getenv('AUDIT_OUT','artifacts/btcusdt-arch-e-forensic-audit-v2'));cache=Path(os.getenv('BTC_CACHE',out/'data'));out.mkdir(parents=True,exist_ok=True)
 h1,manifest,mhash=load(cache);bars,kids=h4(h1);cl=[x.c for x in bars];e200=ema(cl,200);e100=ema(cl,100);a14=atr(bars)
 audits=[run(bars,kids,e200,e100,a14,c,*CONFIGS[c]) for c in CONFIGS]
 ident={'spec_commit':'1702a3b14f3f9df93715e18fb335d54d9b2eac7c','source_commit':'f974d17f9f69d3bd26f869612d4eb7cdaa4b2221','audit_head':git('rev-parse','HEAD'),'spec_git_blob':git('hash-object',SPEC),'source_git_blob':git('hash-object',SRC),'spec_sha256':fsha(SPEC),'source_sha256':fsha(SRC),'data_manifest_sha256':mhash}
 ok=all(a['strict_gate_pass'] for a in audits)
 res={'protocol':'Architecture E forensic audit v2','strategy_rules_changed':False,'oos_tested':False,'oos_locked':'2026-01-01 onward','identity':ident,'data_files':manifest,'audits':audits,'forensic_gate_pass':ok}
 (out/'audit_results.json').write_text(json.dumps(res,indent=2))
 with (out/'audit_summary.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['config','net','pf','trades','years','dd_realized_pct','dd_close_mtm_pct','dd_worstcase_pct','dd_worstcase_cash','recovery_worstcase','zero_duration','zero_h1_verified','baseline_match','strict_gate'])
  for a in audits:w.writerow([a['config'],a['net_profit'],a['profit_factor'],a['closed_trades'],a['profitable_years'],a['max_dd_realized_pct'],a['max_dd_close_mtm_pct'],a['max_dd_intrabar_worstcase_pct'],a['max_dd_intrabar_worstcase_cash'],a['recovery_intrabar_worstcase'],a['zero_duration_count'],a['zero_duration_all_h1_verified'],all(a['baseline_match'].values()),a['strict_gate_pass']])
 with (out/'zero_duration_trades.csv').open('w',newline='') as f:
  fields=['config','entry_ts','exit_ts','entry','stop','exit','pnl','first_h1_trigger_ts','h1_verified'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for a in audits:w.writerows(a['zero_duration_trades'])
 with (out/'data_hash_manifest.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']);w.writeheader();w.writerows(manifest)
 print(json.dumps({'forensic_gate_pass':ok,'audits':[{k:v for k,v in a.items() if k not in ('zero_duration_trades','annual_net_profit')} for a in audits],'identity':ident},indent=2))
if __name__=='__main__':main()
