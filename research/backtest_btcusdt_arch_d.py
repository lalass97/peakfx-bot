#!/usr/bin/env python3
import csv, io, json, math, os, statistics, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
START_YEAR, END_YEAR = 2021, 2025
INITIAL_CAPITAL=10000.0
RISK_PCT=0.0025
COMMISSION=0.001
ATR_LEN=14
ATR_MULT=2.0
CONFIGS={'BD01':(25,1.5),'BD02':(30,1.5),'BD03':(25,2.0),'BD04':(30,2.0)}

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def ts_to_ms(x):
    return x//1000 if x>10_000_000_000_000 else x

def download_and_load(cache):
    cache.mkdir(parents=True,exist_ok=True); bars=[]
    for y in range(START_YEAR,END_YEAR+1):
        for m in range(1,13):
            fn=f'BTCUSDT-1h-{y}-{m:02d}.zip'; p=cache/fn
            if not p.exists():
                with urllib.request.urlopen(f'{BASE_URL}/{fn}',timeout=60) as r: p.write_bytes(r.read())
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names)!=1: raise RuntimeError(f'Unexpected zip contents: {fn}')
                for row in csv.reader(io.StringIO(z.read(names[0]).decode('utf-8'))):
                    if row and row[0].strip().isdigit():
                        bars.append(Bar(ts_to_ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    uniq={b.ts:b for b in bars}; bars=[uniq[k] for k in sorted(uniq)]
    print('Loaded',len(bars),'H1 bars')
    return bars

def wilder(values,n):
    out=[None]*len(values)
    if len(values)<n:return out
    out[n-1]=sum(values[:n])/n
    for i in range(n,len(values)): out[i]=(out[i-1]*(n-1)+values[i])/n
    return out

def atr(bars,n=14):
    tr=[]
    for i,b in enumerate(bars):
        pc=bars[i-1].c if i else b.c
        tr.append(max(b.h-b.l,abs(b.h-pc),abs(b.l-pc)))
    return wilder(tr,n)

def rsi(closes,n=14):
    gains=[0.0]*len(closes); losses=[0.0]*len(closes)
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]
        gains[i]=max(d,0.0); losses[i]=max(-d,0.0)
    ag=wilder(gains,n); al=wilder(losses,n); out=[None]*len(closes)
    for i in range(len(closes)):
        if ag[i] is None or al[i] is None: continue
        if al[i]==0: out[i]=100.0
        else:
            rs=ag[i]/al[i]; out[i]=100-100/(1+rs)
    return out

def bollinger(closes,n=20,mult=2.0):
    lower=[None]*len(closes); mid=[None]*len(closes); upper=[None]*len(closes)
    for i in range(n-1,len(closes)):
        w=closes[i-n+1:i+1]; m=sum(w)/n; sd=statistics.pstdev(w)
        mid[i]=m; lower[i]=m-mult*sd; upper[i]=m+mult*sd
    return lower,mid,upper

def aggregate_h4(bars):
    groups=[]; curkey=None; cur=[]
    for b in bars:
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc); key=(dt.year,dt.month,dt.day,dt.hour//4)
        if key!=curkey:
            if len(cur)==4:
                groups.append(Bar(cur[-1].ts,cur[0].o,max(x.h for x in cur),min(x.l for x in cur),cur[-1].c,sum(x.v for x in cur)))
            curkey=key; cur=[b]
        else: cur.append(b)
    if len(cur)==4: groups.append(Bar(cur[-1].ts,cur[0].o,max(x.h for x in cur),min(x.l for x in cur),cur[-1].c,sum(x.v for x in cur)))
    return groups

def adx(bars,n=14):
    tr=[0.0]*len(bars); pdm=[0.0]*len(bars); mdm=[0.0]*len(bars)
    for i in range(1,len(bars)):
        up=bars[i].h-bars[i-1].h; dn=bars[i-1].l-bars[i].l
        pdm[i]=up if up>dn and up>0 else 0.0
        mdm[i]=dn if dn>up and dn>0 else 0.0
        tr[i]=max(bars[i].h-bars[i].l,abs(bars[i].h-bars[i-1].c),abs(bars[i].l-bars[i-1].c))
    atrw=wilder(tr,n); p=wilder(pdm,n); m=wilder(mdm,n); dx=[None]*len(bars)
    for i in range(len(bars)):
        if atrw[i] is None or not atrw[i]: continue
        pdi=100*p[i]/atrw[i]; mdi=100*m[i]/atrw[i]; den=pdi+mdi
        dx[i]=100*abs(pdi-mdi)/den if den else 0.0
    out=[None]*len(bars)
    vals=[]
    for i,x in enumerate(dx):
        if x is None: continue
        vals.append((i,x))
    if len(vals)<n:return out
    seed=sum(x for _,x in vals[:n])/n; first_i=vals[n-1][0]; out[first_i]=seed; prev=seed
    for idx,x in vals[n:]:
        prev=(prev*(n-1)+x)/n; out[idx]=prev
    return out

def h4_range_regime(bars):
    h4=aggregate_h4(bars); a=adx(h4,14); by_end={h4[i].ts:(a[i] is not None and a[i]<=20.0) for i in range(len(h4))}
    ends=sorted(by_end); out=[False]*len(bars); j=-1
    for i,b in enumerate(bars):
        while j+1<len(ends) and ends[j+1]<=b.ts:j+=1
        out[i]=by_end[ends[j]] if j>=0 else False
    return out

def exit_hit(bar,stop,target):
    hs=bar.l<=stop; ht=bar.h>=target
    if not hs and not ht:return None,None
    if hs and not ht:return 'stop',stop
    if ht and not hs:return 'target',target
    return ('target',target) if abs(bar.o-bar.h)<abs(bar.o-bar.l) else ('stop',stop)

def run_config(bars,atr14,lower,rsi14,regime,cfg,rsi_threshold,target_r,commission=COMMISSION,details=False):
    equity=INITIAL_CAPITAL; peak=equity; max_dd_pct=0.0; max_dd_dollars=0.0
    gp=0.0; gl=0.0; comm_total=0.0; pos=None; pending=None; trades=[]; curve=[]
    annual={y:0.0 for y in range(START_YEAR,END_YEAR+1)}
    for i,b in enumerate(bars):
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc)
        if not (START_YEAR<=dt.year<=END_YEAR): continue
        if pos is None and pending and pending['entry_index']==i:
            entry=b.o; sd=ATR_MULT*pending['atr']
            if sd>0 and entry-sd>0:
                risk=equity*RISK_PCT; qty=min(risk/sd,equity/entry)
                if qty>0:
                    stop=entry-sd; target=entry+target_r*sd; ec=qty*entry*commission
                    equity-=ec; comm_total+=ec
                    pos={'entry':entry,'qty':qty,'stop':stop,'target':target,'entry_comm':ec,'entry_ts':b.ts,'risk_cash':qty*sd}
            pending=None
        if pos:
            reason,px=exit_hit(b,pos['stop'],pos['target'])
            if reason:
                xc=pos['qty']*px*commission; price_pnl=pos['qty']*(px-pos['entry']); pnl=price_pnl-pos['entry_comm']-xc
                equity+=price_pnl-xc; comm_total+=xc; annual[dt.year]+=pnl
                if pnl>0: gp+=pnl
                else: gl+=pnl
                trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'pnl':pnl,'reason':reason,'risk_cash':pos['risk_cash'],'realized_r':pnl/pos['risk_cash'] if pos['risk_cash'] else 0.0,'duration_hours':(b.ts-pos['entry_ts'])/3_600_000})
                pos=None
        peak=max(peak,equity); dd=peak-equity; max_dd_dollars=max(max_dd_dollars,dd); max_dd_pct=max(max_dd_pct,dd/peak if peak else 0)
        curve.append((b.ts,equity))
        if pos is None and pending is None and i>=21 and i+1<len(bars):
            prev=i-1
            if not regime[i] or atr14[i] is None or lower[prev] is None or lower[i] is None or rsi14[prev] is None: continue
            excursion=bars[prev].c < lower[prev] and rsi14[prev] <= rsi_threshold
            reclaim=b.c > lower[i] and b.c > b.o
            if excursion and reclaim: pending={'entry_index':i+1,'atr':atr14[i]}
    net=equity-INITIAL_CAPITAL; pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0.0); recovery=net/max_dd_dollars if max_dd_dollars>0 else (math.inf if net>0 else 0.0)
    wins=[t for t in trades if t['pnl']>0]; losses=[t for t in trades if t['pnl']<=0]
    return {'configuration':cfg,'rsi_threshold':rsi_threshold,'target_r':target_r,'initial_capital':INITIAL_CAPITAL,'ending_equity':equity,'net_profit':net,'profit_factor':pf,'closed_trades':len(trades),'wins':len(wins),'losses':len(losses),'win_rate_pct':100*len(wins)/len(trades) if trades else 0.0,'avg_win':sum(t['pnl'] for t in wins)/len(wins) if wins else 0.0,'avg_loss':sum(t['pnl'] for t in losses)/len(losses) if losses else 0.0,'expectancy_per_trade':net/len(trades) if trades else 0.0,'max_equity_drawdown_pct':max_dd_pct*100,'max_drawdown_dollars':max_dd_dollars,'recovery_factor':recovery,'annual_net_profit':annual,'profitable_years':sum(v>0 for v in annual.values()),'gross_profit':gp,'gross_loss':gl,'total_commission':comm_total,'open_position_at_end':pos is not None,'trades_detail':trades if details else None,'equity_curve':curve if details else None}

def passes(r):
    return r['net_profit']>0 and r['profit_factor']>=1.20 and r['closed_trades']>=100 and r['max_equity_drawdown_pct']<=20 and r['recovery_factor']>=1.25 and r['profitable_years']>=4

def main():
    out=Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-d-baseline')); cache=Path(os.environ.get('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True)
    bars=download_and_load(cache); closes=[b.c for b in bars]; atr14=atr(bars,14); lower,_,_=bollinger(closes,20,2.0); rsi14=rsi(closes,14); regime=h4_range_regime(bars)
    baseline=[]; all_trades=[]; all_curve=[]
    for cfg,(thr,trg) in CONFIGS.items():
        r=run_config(bars,atr14,lower,rsi14,regime,cfg,thr,trg,COMMISSION,True); r['decision']='Advance' if passes(r) else 'Retire'
        baseline.append({k:v for k,v in r.items() if k not in ('trades_detail','equity_curve')}); all_trades.extend(r['trades_detail']); all_curve.extend((cfg,ts,eq) for ts,eq in r['equity_curve']); print(json.dumps(baseline[-1],indent=2))
    stress=[]
    for r0 in baseline:
        if r0['decision']=='Advance':
            rs=run_config(bars,atr14,lower,rsi14,regime,r0['configuration'],r0['rsi_threshold'],r0['target_r'],0.0015,False); rs['stress_pass']=rs['net_profit']>0 and rs['profit_factor']>=1.15; stress.append({k:v for k,v in rs.items() if k not in ('trades_detail','equity_curve')})
    result={'protocol':'BTCUSDT Architecture D frozen baseline','source':'Binance public Spot monthly 1h klines','development_period':'2021-01-01 through 2025-12-31','oos_locked':'2026-01-01 onward','oos_tested':False,'baseline':baseline,'cost_stress':stress,'architecture_decision':'Advance' if any(r['decision']=='Advance' for r in baseline) else 'Retire'}
    (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','net_profit','profit_factor','closed_trades','win_rate_pct','expectancy','max_dd_pct','recovery_factor','profitable_years','decision'])
        for r in baseline:w.writerow([r['configuration'],f"{r['net_profit']:.2f}",f"{r['profit_factor']:.4f}",r['closed_trades'],f"{r['win_rate_pct']:.2f}",f"{r['expectancy_per_trade']:.2f}",f"{r['max_equity_drawdown_pct']:.4f}",f"{r['recovery_factor']:.4f}",r['profitable_years'],r['decision']])
    with (out/'trades.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['config','entry_ts','exit_ts','pnl','reason','risk_cash','realized_r','duration_hours']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_trades)
    with (out/'equity_curve.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','ts','equity']); w.writerows(all_curve)

if __name__=='__main__': main()
