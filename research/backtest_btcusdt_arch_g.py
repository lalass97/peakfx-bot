#!/usr/bin/env python3
import csv, hashlib, io, json, math, os, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_URL='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
INITIAL=10000.0; RISK=0.0025; COMM=0.001
DEV_START=int(datetime(2021,1,1,tzinfo=timezone.utc).timestamp()*1000)
DEV_END=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000)
CONFIGS={'BG01':(3,40,2.0),'BG02':(6,40,2.0),'BG03':(3,45,3.0),'BG04':(6,45,3.0)}

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def ms(x): return x//1000 if x>10_000_000_000_000 else x

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
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
                if len(names)!=1: raise RuntimeError(f'Unexpected zip contents {fn}')
                for row in csv.reader(io.StringIO(z.read(names[0]).decode())):
                    if row and row[0].strip().isdigit():
                        bars.append(Bar(ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    uniq={b.ts:b for b in bars}
    return [uniq[k] for k in sorted(uniq)],manifest

def aggregate_daily(h1):
    groups={}
    for b in h1:
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc)
        key=int(dt.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000)
        groups.setdefault(key,[]).append(b)
    out=[]; omitted=[]; H=3600000
    for key in sorted(groups):
        g=sorted(groups[key],key=lambda x:x.ts)
        if len(g)!=24 or [x.ts for x in g] != [key+j*H for j in range(24)]:
            omitted.append(key); continue
        out.append(Bar(key,g[0].o,max(x.h for x in g),min(x.l for x in g),g[-1].c,sum(x.v for x in g)))
    return out,omitted

def aggregate_weekly(days):
    groups={}
    D=86400000
    for b in days:
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc)
        monday=(dt-timedelta(days=dt.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
        key=int(monday.timestamp()*1000)
        groups.setdefault(key,[]).append(b)
    out=[]; omitted=[]
    for key in sorted(groups):
        g=sorted(groups[key],key=lambda x:x.ts)
        if len(g)!=7 or [x.ts for x in g] != [key+j*D for j in range(7)]:
            omitted.append(key); continue
        out.append(Bar(key,g[0].o,max(x.h for x in g),min(x.l for x in g),g[-1].c,sum(x.v for x in g)))
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

def rsi(closes,n=14):
    out=[None]*len(closes)
    if len(closes)<=n:return out
    gains=[]; losses=[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[:n])/n; al=sum(losses[:n])/n
    def val(g,l):
        if l==0:return 100.0
        rs=g/l; return 100-100/(1+rs)
    out[n]=val(ag,al)
    for i in range(n+1,len(closes)):
        ag=(ag*(n-1)+gains[i-1])/n; al=(al*(n-1)+losses[i-1])/n; out[i]=val(ag,al)
    return out

def update_dd(eq,peak,cash,pct):
    peak=max(peak,eq); d=peak-eq; p=d/peak if peak else 0
    return peak,max(cash,d),max(pct,p)

def build_week_regime(days,weeks,wema):
    regime=[False]*len(days); wi=-1
    for i,d in enumerate(days):
        dt=datetime.fromtimestamp(d.ts/1000,timezone.utc)
        week_start=int((dt-timedelta(days=dt.weekday())).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000)
        while wi+1<len(weeks) and weeks[wi+1].ts < week_start: wi+=1
        if wi>=4 and wema[wi] is not None and wema[wi-4] is not None:
            regime[i]=weeks[wi].c>wema[wi] and wema[wi]>wema[wi-4]
    return regime

def run(days,regime,e20,a14,r14,cfg,window,rsi_thr,target_r,detail=True):
    bal=INITIAL; pos=None; pending=None; pending_exit=False; gp=gl=comm_total=0.0
    trades=[]; curve=[]; annual={y:0.0 for y in range(2021,2026)}; integ=[]
    peak=INITIAL; dd_cash=dd_pct=0.0
    def close(px,ts,yr,reason):
        nonlocal bal,pos,pending_exit,gp,gl,comm_total
        xc=pos['qty']*px*COMM; pp=pos['qty']*(px-pos['entry']); pnl=pp-pos['ec']-xc
        bal+=pp-xc; comm_total+=xc; annual[yr]+=pnl; gp+=max(pnl,0); gl+=min(pnl,0)
        trades.append({'config':cfg,'entry_ts':pos['ts'],'exit_ts':ts,'entry':pos['entry'],'exit':px,'stop':pos['stop'],'target':pos['target'],'pnl':pnl,'reason':reason,'duration_days':(ts-pos['ts'])/86400000,'risk_cash':pos['risk_cash']})
        pos=None; pending_exit=False
    for i,b in enumerate(days):
        if b.ts<DEV_START or b.ts>=DEV_END: continue
        yr=datetime.fromtimestamp(b.ts/1000,timezone.utc).year
        if pos is not None and pending_exit:
            # At next open, protective gap logic has precedence if worse.
            if b.o<=pos['stop']: close(b.o,b.ts,yr,'stop_gap_on_ema_exit')
            elif b.o>=pos['target']: close(b.o,b.ts,yr,'target_gap_on_ema_exit')
            else: close(b.o,b.ts,yr,'ema20_exit')
        if pos is None and pending is not None and pending['i']==i:
            entry=b.o; dist=2.0*pending['atr']; stop=entry-dist
            if dist>0 and stop>0:
                risk_budget=bal*RISK; qty=min(risk_budget/dist,bal/entry)
                if qty>0:
                    ec=qty*entry*COMM; bal-=ec; comm_total+=ec
                    pos={'entry':entry,'ts':b.ts,'qty':qty,'stop':stop,'target':entry+target_r*dist,'ec':ec,'risk_cash':qty*dist}
            pending=None
        if pos is not None:
            stop_hit=b.l<=pos['stop']; tgt_hit=b.h>=pos['target']
            if b.o<=pos['stop']: close(b.o,b.ts,yr,'stop_gap')
            elif b.o>=pos['target']: close(b.o,b.ts,yr,'target_gap')
            elif stop_hit and tgt_hit: close(pos['stop'],b.ts,yr,'stop_both_touched_conservative')
            elif stop_hit: close(pos['stop'],b.ts,yr,'stop')
            elif tgt_hit: close(pos['target'],b.ts,yr,'target')
        mtm=bal if pos is None else bal+pos['qty']*(b.c-pos['entry'])-pos['qty']*b.c*COMM
        peak,dd_cash,dd_pct=update_dd(mtm,peak,dd_cash,dd_pct)
        if detail: curve.append({'config':cfg,'ts':b.ts,'equity_mtm':mtm,'balance':bal})
        if pos is not None:
            if e20[i] is not None and b.c<e20[i] and i+1<len(days): pending_exit=True
            continue
        if pending is not None: continue
        if i<max(21,window)+1 or i+1>=len(days): continue
        if not regime[i] or e20[i] is None or a14[i] is None or r14[i] is None: continue
        prev=range(i-window,i)
        touched=any(e20[j] is not None and days[j].l<=e20[j] for j in prev)
        oversold=any(r14[j] is not None and r14[j]<=rsi_thr for j in prev)
        if touched and oversold and b.c>e20[i] and b.c>days[i-1].h:
            pending={'i':i+1,'atr':a14[i]}
    last=next((b for b in reversed(days) if DEV_START<=b.ts<DEV_END),None)
    ending=bal if pos is None or last is None else bal+pos['qty']*(last.c-pos['entry'])-pos['qty']*last.c*COMM
    net=ending-INITIAL; pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0.0); rec=net/dd_cash if dd_cash>0 else (math.inf if net>0 else 0.0)
    years=sum(v>0 for v in annual.values()); wins=sum(t['pnl']>0 for t in trades)
    return {'configuration':cfg,'pullback_window_days':window,'rsi_pullback_threshold':rsi_thr,'target_r':target_r,'initial_capital':INITIAL,'ending_equity_mtm':ending,'net_profit_mtm':net,'profit_factor_closed_trades':pf,'closed_trades':len(trades),'wins':wins,'losses':len(trades)-wins,'win_rate_pct':100*wins/len(trades) if trades else 0.0,'gross_profit':gp,'gross_loss':gl,'total_commission':comm_total,'max_equity_drawdown_pct_mtm':dd_pct*100,'max_drawdown_dollars_mtm':dd_cash,'recovery_factor_mtm':rec,'annual_net_profit_closed':annual,'profitable_years':years,'open_position_at_end':pos is not None,'integrity_violations':integ,'trades_detail':trades,'equity_curve':curve}

def passes(r):
    return r['net_profit_mtm']>0 and r['profit_factor_closed_trades']>=1.20 and r['closed_trades']>=40 and r['max_equity_drawdown_pct_mtm']<=20 and r['recovery_factor_mtm']>=1.25 and r['profitable_years']>=4 and not r['integrity_violations']

def main():
    out=Path(os.getenv('BTC_OUT','artifacts/btcusdt-arch-g-baseline')); cache=Path(os.getenv('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True)
    h1,manifest=load_h1(cache); days,day_omit=aggregate_daily(h1); weeks,week_omit=aggregate_weekly(days)
    dc=[b.c for b in days]; wc=[b.c for b in weeks]; e20=ema(dc,20); a14=atr(days,14); r14=rsi(dc,14); wema=ema(wc,30); regime=build_week_regime(days,weeks,wema)
    results=[]; all_trades=[]; all_curve=[]
    for cfg,(window,thr,target) in CONFIGS.items():
        r=run(days,regime,e20,a14,r14,cfg,window,thr,target,True); r['daily_incomplete_groups_omitted']=len(day_omit); r['weekly_incomplete_groups_omitted']=len(week_omit); r['decision']='Advance' if passes(r) else 'Retire'
        all_trades+=r.pop('trades_detail'); all_curve+=r.pop('equity_curve'); results.append(r); print(json.dumps(r,indent=2))
    payload={'protocol':'BTCUSDT Architecture G frozen baseline','strategy':'Weekly Trend + Daily Pullback Recovery','development_period':'2021-01-01 through 2025-12-31 UTC','oos_2026_loaded':False,'source_data_manifest':manifest,'results':results,'architecture_decision':'Advance' if any(r['decision']=='Advance' for r in results) else 'Retire'}
    (out/'results.json').write_text(json.dumps(payload,indent=2))
    with (out/'summary.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['config','net_profit_mtm','pf_closed','trades','win_rate_pct','dd_mtm_pct','recovery_mtm','profitable_years','open_at_end','decision'])
        for r in results:w.writerow([r['configuration'],r['net_profit_mtm'],r['profit_factor_closed_trades'],r['closed_trades'],r['win_rate_pct'],r['max_equity_drawdown_pct_mtm'],r['recovery_factor_mtm'],r['profitable_years'],r['open_position_at_end'],r['decision']])
    with (out/'trades.csv').open('w',newline='') as f:
        fields=['config','entry_ts','exit_ts','entry','exit','stop','target','pnl','reason','duration_days','risk_cash']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_trades)
    with (out/'equity_curve.csv').open('w',newline='') as f:
        fields=['config','ts','equity_mtm','balance']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_curve)
    with (out/'data_hashes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']); w.writeheader(); w.writerows(manifest)
if __name__=='__main__': main()
