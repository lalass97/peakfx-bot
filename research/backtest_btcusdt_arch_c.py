#!/usr/bin/env python3
import csv, io, json, math, os, statistics, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h"
START_YEAR, END_YEAR = 2021, 2025
INITIAL_CAPITAL = 10000.0
RISK_PCT = 0.0025
COMMISSION = 0.001
ATR_LEN = 14
ATR_MULT = 2.0
CONFIGS = {
    "BC01": (48, 3.0),
    "BC02": (96, 3.0),
    "BC03": (48, 4.0),
    "BC04": (96, 4.0),
}

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def ts_to_ms(x:int)->int:
    return x//1000 if x>10_000_000_000_000 else x

def download_and_load(cache:Path):
    cache.mkdir(parents=True, exist_ok=True)
    bars=[]
    for y in range(START_YEAR, END_YEAR+1):
        for m in range(1,13):
            fn=f"BTCUSDT-1h-{y}-{m:02d}.zip"; p=cache/fn
            if not p.exists():
                with urllib.request.urlopen(f"{BASE_URL}/{fn}", timeout=60) as r: p.write_bytes(r.read())
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names)!=1: raise RuntimeError(f"Unexpected zip contents {fn}")
                rd=csv.reader(io.StringIO(z.read(names[0]).decode('utf-8')))
                for row in rd:
                    if not row or not row[0].strip().isdigit(): continue
                    bars.append(Bar(ts_to_ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    uniq={b.ts:b for b in bars}
    bars=[uniq[k] for k in sorted(uniq)]
    print('Loaded',len(bars),'bars')
    return bars

def ema(vals,n):
    out=[None]*len(vals)
    if len(vals)<n:return out
    out[n-1]=sum(vals[:n])/n; a=2/(n+1)
    for i in range(n,len(vals)): out[i]=vals[i]*a+out[i-1]*(1-a)
    return out

def atr(bars,n):
    tr=[]
    for i,b in enumerate(bars):
        pc=bars[i-1].c if i else b.c
        tr.append(max(b.h-b.l,abs(b.h-pc),abs(b.l-pc)))
    out=[None]*len(bars)
    if len(bars)<n:return out
    out[n-1]=sum(tr[:n])/n
    for i in range(n,len(bars)): out[i]=(out[i-1]*(n-1)+tr[i])/n
    return out,tr

def sma(vals,n):
    out=[None]*len(vals); s=0.0
    for i,x in enumerate(vals):
        s+=x
        if i>=n:s-=vals[i-n]
        if i>=n-1:out[i]=s/n
    return out

def bb_width(closes,n=20,mult=2.0):
    out=[None]*len(closes)
    for i in range(n-1,len(closes)):
        w=closes[i-n+1:i+1]; mid=sum(w)/n
        sd=statistics.pstdev(w)
        out[i]=(4.0*sd/mid) if mid else None
    return out

def percentile_nearest_rank(vals,p):
    vals=sorted(v for v in vals if v is not None)
    if not vals:return None
    k=max(1, math.ceil(p*len(vals)))
    return vals[k-1]

def build_h4_regime(bars):
    groups=[]; cur_key=None; cur=[]
    for b in bars:
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc); key=(dt.year,dt.month,dt.day,dt.hour//4)
        if key!=cur_key:
            if len(cur)==4: groups.append((cur[-1].ts,cur[-1].c))
            cur_key=key; cur=[b]
        else: cur.append(b)
    if len(cur)==4: groups.append((cur[-1].ts,cur[-1].c))
    e=ema([x[1] for x in groups],200); ok_by={}
    for i,(ts,c) in enumerate(groups): ok_by[ts]=bool(i>=203 and e[i] is not None and e[i-4] is not None and c>e[i] and e[i]>e[i-4])
    ends=sorted(ok_by); out=[False]*len(bars); j=-1
    for i,b in enumerate(bars):
        while j+1<len(ends) and ends[j+1]<=b.ts:j+=1
        out[i]=ok_by[ends[j]] if j>=0 else False
    return out

def bar_exit_path(bar,stop,target):
    hs=bar.l<=stop; ht=bar.h>=target
    if not hs and not ht:return None,None
    if hs and not ht:return 'stop',stop
    if ht and not hs:return 'target',target
    return ('target',target) if abs(bar.o-bar.h)<abs(bar.o-bar.l) else ('stop',stop)

def run_config(bars,atr14,tr20,bb,vol20,regime,cfg,lookback,target_r,commission=COMMISSION,write_detail=False):
    equity=INITIAL_CAPITAL; peak=equity; max_dd=0.0; max_dd_dollars=0.0
    gross_profit=0.0; gross_loss=0.0; commission_total=0.0
    pos=None; pending=None; trades=[]; annual={y:0.0 for y in range(START_YEAR,END_YEAR+1)}
    equity_curve=[]
    for i,b in enumerate(bars):
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc)
        if dt.year<START_YEAR or dt.year>END_YEAR: continue
        if pos is None and pending is not None and pending['entry_index']==i:
            entry=b.o; stop_dist=ATR_MULT*pending['atr']
            if stop_dist>0 and entry-stop_dist>0:
                risk_cash=equity*RISK_PCT; qty=min(risk_cash/stop_dist,equity/entry)
                if qty>0:
                    stop=entry-stop_dist; target=entry+target_r*stop_dist
                    ec=qty*entry*commission; equity-=ec; commission_total+=ec
                    pos={'entry':entry,'qty':qty,'stop':stop,'target':target,'entry_comm':ec,'entry_ts':b.ts,'risk_cash':qty*stop_dist}
            pending=None
        if pos is not None:
            reason,px=bar_exit_path(b,pos['stop'],pos['target'])
            if reason:
                xc=pos['qty']*px*commission; pnl_price=pos['qty']*(px-pos['entry']); pnl=pnl_price-pos['entry_comm']-xc
                equity+=pnl_price-xc; commission_total+=xc
                if pnl>=0:gross_profit+=pnl
                else:gross_loss+=pnl
                annual[dt.year]+=pnl
                trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'pnl':pnl,'reason':reason,'risk_cash':pos['risk_cash'],'realized_r':pnl/pos['risk_cash'] if pos['risk_cash'] else 0.0,'duration_hours':(b.ts-pos['entry_ts'])/3_600_000})
                pos=None
        peak=max(peak,equity); dd=peak-equity; max_dd_dollars=max(max_dd_dollars,dd); max_dd=max(max_dd,dd/peak if peak else 0)
        equity_curve.append((b.ts,equity))
        if pos is None and pending is None and i>=max(lookback+20,20):
            if not regime[i] or atr14[i] is None or bb[i-1] is None or vol20[i] is None: continue
            hist=bb[i-lookback:i]
            if len(hist)<lookback or any(x is None for x in hist): continue
            p20=percentile_nearest_rank(hist,0.20)
            compressed=bb[i-1] <= p20
            rng=b.h-b.l; clv=(b.c-b.l)/rng if rng>0 else 0.0
            bullish=b.c>b.o
            expansion=tr20[i] >= 1.5*(sum(tr20[max(0,i-19):i+1])/min(20,i+1))
            volsurge=b.v >= 1.5*vol20[i]
            if compressed and bullish and expansion and clv>=0.75 and volsurge and i+1<len(bars):
                pending={'entry_index':i+1,'atr':atr14[i]}
    net=equity-INITIAL_CAPITAL; pf=gross_profit/abs(gross_loss) if gross_loss<0 else (math.inf if gross_profit>0 else 0.0)
    recovery=net/max_dd_dollars if max_dd_dollars>0 else (math.inf if net>0 else 0.0)
    wins=[t for t in trades if t['pnl']>0]; losses=[t for t in trades if t['pnl']<=0]
    result={'configuration':cfg,'lookback':lookback,'target_r':target_r,'initial_capital':INITIAL_CAPITAL,'ending_equity':equity,'net_profit':net,'profit_factor':pf,'closed_trades':len(trades),'wins':len(wins),'losses':len(losses),'win_rate_pct':100*len(wins)/len(trades) if trades else 0.0,'avg_win':sum(t['pnl'] for t in wins)/len(wins) if wins else 0.0,'avg_loss':sum(t['pnl'] for t in losses)/len(losses) if losses else 0.0,'expectancy_per_trade':net/len(trades) if trades else 0.0,'max_equity_drawdown_pct':max_dd*100,'max_drawdown_dollars':max_dd_dollars,'recovery_factor':recovery,'annual_net_profit':annual,'profitable_years':sum(v>0 for v in annual.values()),'gross_profit':gross_profit,'gross_loss':gross_loss,'total_commission':commission_total,'open_position_at_end':pos is not None,'trades_detail':trades if write_detail else None,'equity_curve':equity_curve if write_detail else None}
    return result

def passes(r):
    return r['net_profit']>0 and r['profit_factor']>=1.20 and r['closed_trades']>=100 and r['max_equity_drawdown_pct']<=20 and r['recovery_factor']>=1.25 and r['profitable_years']>=4

def main():
    out=Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-c-baseline')); cache=Path(os.environ.get('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True)
    bars=download_and_load(cache); atr14,_=atr(bars,14); _,tr20=atr(bars,20); bb=bb_width([b.c for b in bars]); vol20=sma([b.v for b in bars],20); regime=build_h4_regime(bars)
    baseline=[]; all_trades=[]; all_equity=[]
    for cfg,(lb,trg) in CONFIGS.items():
        r=run_config(bars,atr14,tr20,bb,vol20,regime,cfg,lb,trg,COMMISSION,True); r['decision']='Advance' if passes(r) else 'Retire'; baseline.append({k:v for k,v in r.items() if k not in ('trades_detail','equity_curve')}); all_trades.extend(r['trades_detail']); all_equity.extend((cfg,ts,eq) for ts,eq in r['equity_curve']); print(json.dumps(baseline[-1],indent=2))
    stress=[]
    for r0 in baseline:
        if r0['decision']=='Advance':
            rs=run_config(bars,atr14,tr20,bb,vol20,regime,r0['configuration'],r0['lookback'],r0['target_r'],0.0015,False); rs['stress_pass']=rs['net_profit']>0 and rs['profit_factor']>=1.15; stress.append({k:v for k,v in rs.items() if k not in ('trades_detail','equity_curve')})
    result={'protocol':'BTCUSDT Architecture C frozen baseline','source':'Binance public Spot monthly 1h klines','development_period':'2021-01-01 through 2025-12-31','oos_locked':'2026-01-01 onward','oos_tested':False,'baseline':baseline,'cost_stress':stress,'architecture_decision':'Advance' if any(r['decision']=='Advance' for r in baseline) else 'Retire'}
    (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','net_profit','profit_factor','closed_trades','win_rate_pct','expectancy','max_dd_pct','recovery_factor','profitable_years','decision'])
        for r in baseline:w.writerow([r['configuration'],f"{r['net_profit']:.2f}",f"{r['profit_factor']:.4f}",r['closed_trades'],f"{r['win_rate_pct']:.2f}",f"{r['expectancy_per_trade']:.2f}",f"{r['max_equity_drawdown_pct']:.4f}",f"{r['recovery_factor']:.4f}",r['profitable_years'],r['decision']])
    with (out/'trades.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['config','entry_ts','exit_ts','pnl','reason','risk_cash','realized_r','duration_hours']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_trades)
    with (out/'equity_curve.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','ts','equity']); w.writerows(all_equity)

if __name__=='__main__': main()
