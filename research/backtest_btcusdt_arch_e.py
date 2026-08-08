#!/usr/bin/env python3
import csv, io, json, math, os, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL='https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
START_YEAR, END_YEAR = 2021, 2025
INITIAL_CAPITAL=10000.0
RISK_PCT=0.0025
COMMISSION=0.001
CONFIGS={'BE01':(48,3.0),'BE02':(96,3.0),'BE03':(48,4.0),'BE04':(96,4.0)}

@dataclass
class Bar:
    ts:int; o:float; h:float; l:float; c:float; v:float

def ts_to_ms(x:int)->int:
    return x//1000 if x>10_000_000_000_000 else x

def load_h1(cache:Path):
    cache.mkdir(parents=True,exist_ok=True); out=[]
    for y in range(START_YEAR,END_YEAR+1):
        for m in range(1,13):
            fn=f'BTCUSDT-1h-{y}-{m:02d}.zip'; p=cache/fn
            if not p.exists():
                with urllib.request.urlopen(f'{BASE_URL}/{fn}',timeout=60) as r: p.write_bytes(r.read())
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names)!=1: raise RuntimeError(f'Unexpected zip contents {fn}')
                for row in csv.reader(io.StringIO(z.read(names[0]).decode('utf-8'))):
                    if not row or not row[0].strip().isdigit(): continue
                    out.append(Bar(ts_to_ms(int(row[0])),float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5])))
    uniq={b.ts:b for b in out}; return [uniq[k] for k in sorted(uniq)]

def aggregate_h4(h1):
    groups=[]; cur_key=None; cur=[]
    for b in h1:
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc); key=(dt.year,dt.month,dt.day,dt.hour//4)
        if key!=cur_key:
            if len(cur)==4:
                groups.append(Bar(cur[0].ts,cur[0].o,max(x.h for x in cur),min(x.l for x in cur),cur[-1].c,sum(x.v for x in cur)))
            cur_key=key; cur=[b]
        else: cur.append(b)
    if len(cur)==4:
        groups.append(Bar(cur[0].ts,cur[0].o,max(x.h for x in cur),min(x.l for x in cur),cur[-1].c,sum(x.v for x in cur)))
    return groups

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

def run_config(bars,ema200,ema100,atr14,cfg,roc_lb,trail_mult,commission=COMMISSION,detail=False):
    equity=INITIAL_CAPITAL; peak=equity; max_dd=0.0; max_dd_dollars=0.0
    gp=gl=comm_total=0.0; pos=None; pending_entry=None; pending_market_exit=False
    annual={y:0.0 for y in range(START_YEAR,END_YEAR+1)}; trades=[]; curve=[]
    for i,b in enumerate(bars):
        dt=datetime.fromtimestamp(b.ts/1000,timezone.utc)
        if not (START_YEAR<=dt.year<=END_YEAR): continue

        # Market exit at this H4 open from prior completed close < EMA100.
        if pos is not None and pending_market_exit:
            px=b.o; xc=pos['qty']*px*commission; pnl_price=pos['qty']*(px-pos['entry']); pnl=pnl_price-pos['entry_comm']-xc
            equity+=pnl_price-xc; comm_total+=xc; annual[dt.year]+=pnl; gp+=max(pnl,0); gl+=min(pnl,0)
            trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'pnl':pnl,'reason':'ema100_exit','duration_hours':(b.ts-pos['entry_ts'])/3_600_000,'risk_cash':pos['risk_cash'],'realized_r':pnl/pos['risk_cash'] if pos['risk_cash'] else 0.0})
            pos=None; pending_market_exit=False

        # Entry at this H4 open from prior signal.
        if pos is None and pending_entry is not None and pending_entry['index']==i:
            entry=b.o; stop_dist=trail_mult*pending_entry['atr']; stop=entry-stop_dist
            if stop_dist>0 and stop>0:
                risk_cash=equity*RISK_PCT; qty=min(risk_cash/stop_dist,equity/entry)
                if qty>0:
                    ec=qty*entry*commission; equity-=ec; comm_total+=ec
                    pos={'entry':entry,'qty':qty,'stop':stop,'entry_comm':ec,'entry_ts':b.ts,'risk_cash':qty*stop_dist,'highest_close':entry}
            pending_entry=None

        # Intrabar stop uses stop frozen from prior completed bar.
        if pos is not None and b.l<=pos['stop']:
            px=pos['stop']
            # conservative gap handling
            if b.o<px: px=b.o
            xc=pos['qty']*px*commission; pnl_price=pos['qty']*(px-pos['entry']); pnl=pnl_price-pos['entry_comm']-xc
            equity+=pnl_price-xc; comm_total+=xc; annual[dt.year]+=pnl; gp+=max(pnl,0); gl+=min(pnl,0)
            trades.append({'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'pnl':pnl,'reason':'chandelier_stop','duration_hours':(b.ts-pos['entry_ts'])/3_600_000,'risk_cash':pos['risk_cash'],'realized_r':pnl/pos['risk_cash'] if pos['risk_cash'] else 0.0})
            pos=None; pending_market_exit=False

        peak=max(peak,equity); dd=peak-equity; max_dd_dollars=max(max_dd_dollars,dd); max_dd=max(max_dd,dd/peak if peak else 0.0); curve.append((b.ts,equity))

        # Completed-bar updates/signals for next H4 bar.
        if pos is not None:
            pos['highest_close']=max(pos['highest_close'],b.c)
            if atr14[i] is not None:
                candidate=pos['highest_close']-trail_mult*atr14[i]
                pos['stop']=max(pos['stop'],candidate)
            if ema100[i] is not None and b.c<ema100[i] and i+1<len(bars):
                pending_market_exit=True
        elif pending_entry is None and i>=max(200,roc_lb,6):
            if ema200[i] is None or ema200[i-6] is None or atr14[i] is None: continue
            trend=b.c>ema200[i] and ema200[i]>ema200[i-6]
            roc=b.c/bars[i-roc_lb].c-1.0 if bars[i-roc_lb].c else 0.0
            if trend and roc>0 and i+1<len(bars): pending_entry={'index':i+1,'atr':atr14[i]}

    net=equity-INITIAL_CAPITAL; pf=gp/abs(gl) if gl<0 else (math.inf if gp>0 else 0.0); recovery=net/max_dd_dollars if max_dd_dollars>0 else (math.inf if net>0 else 0.0)
    wins=[t for t in trades if t['pnl']>0]; losses=[t for t in trades if t['pnl']<=0]
    return {'configuration':cfg,'roc_lookback':roc_lb,'trail_atr':trail_mult,'initial_capital':INITIAL_CAPITAL,'ending_equity':equity,'net_profit':net,'profit_factor':pf,'closed_trades':len(trades),'wins':len(wins),'losses':len(losses),'win_rate_pct':100*len(wins)/len(trades) if trades else 0.0,'avg_win':sum(t['pnl'] for t in wins)/len(wins) if wins else 0.0,'avg_loss':sum(t['pnl'] for t in losses)/len(losses) if losses else 0.0,'expectancy_per_trade':net/len(trades) if trades else 0.0,'max_equity_drawdown_pct':max_dd*100,'max_drawdown_dollars':max_dd_dollars,'recovery_factor':recovery,'annual_net_profit':annual,'profitable_years':sum(v>0 for v in annual.values()),'gross_profit':gp,'gross_loss':gl,'total_commission':comm_total,'open_position_at_end':pos is not None,'trades_detail':trades if detail else None,'equity_curve':curve if detail else None}

def passes(r):
    return r['net_profit']>0 and r['profit_factor']>=1.20 and r['closed_trades']>=50 and r['max_equity_drawdown_pct']<=20 and r['recovery_factor']>=1.25 and r['profitable_years']>=4

def main():
    out=Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-e-baseline')); cache=Path(os.environ.get('BTC_CACHE',out/'data')); out.mkdir(parents=True,exist_ok=True)
    h1=load_h1(cache); bars=aggregate_h4(h1); closes=[b.c for b in bars]; e200=ema(closes,200); e100=ema(closes,100); a14=atr(bars,14)
    baseline=[]; all_trades=[]; all_curve=[]
    for cfg,(roc_lb,trail) in CONFIGS.items():
        r=run_config(bars,e200,e100,a14,cfg,roc_lb,trail,COMMISSION,True); r['decision']='Advance' if passes(r) else 'Retire'
        baseline.append({k:v for k,v in r.items() if k not in ('trades_detail','equity_curve')}); all_trades.extend(r['trades_detail']); all_curve.extend((cfg,ts,eq) for ts,eq in r['equity_curve']); print(json.dumps(baseline[-1],indent=2))
    stress=[]
    for r0 in baseline:
        if r0['decision']=='Advance':
            rs=run_config(bars,e200,e100,a14,r0['configuration'],r0['roc_lookback'],r0['trail_atr'],0.0015,False); rs['stress_pass']=rs['net_profit']>0 and rs['profit_factor']>=1.15; stress.append({k:v for k,v in rs.items() if k not in ('trades_detail','equity_curve')})
    result={'protocol':'BTCUSDT Architecture E frozen baseline','source':'Binance public Spot monthly 1h klines aggregated to H4','development_period':'2021-01-01 through 2025-12-31','oos_locked':'2026-01-01 onward','oos_tested':False,'baseline':baseline,'cost_stress':stress,'architecture_decision':'Advance' if any(r['decision']=='Advance' for r in baseline) else 'Retire'}
    (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','net_profit','profit_factor','closed_trades','win_rate_pct','expectancy','max_dd_pct','recovery_factor','profitable_years','decision'])
        for r in baseline:w.writerow([r['configuration'],f"{r['net_profit']:.2f}",f"{r['profit_factor']:.4f}",r['closed_trades'],f"{r['win_rate_pct']:.2f}",f"{r['expectancy_per_trade']:.2f}",f"{r['max_equity_drawdown_pct']:.4f}",f"{r['recovery_factor']:.4f}",r['profitable_years'],r['decision']])
    with (out/'trades.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['config','entry_ts','exit_ts','pnl','reason','duration_hours','risk_cash','realized_r']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_trades)
    with (out/'equity_curve.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','ts','equity']); w.writerows(all_curve)

if __name__=='__main__': main()
