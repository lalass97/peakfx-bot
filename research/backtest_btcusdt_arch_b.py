#!/usr/bin/env python3
import csv, io, json, math, os, urllib.request, zipfile
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
    "BB01": (3, 2.0),
    "BB02": (6, 2.0),
    "BB03": (3, 3.0),
    "BB04": (6, 3.0),
}

@dataclass
class Bar:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float


def ts_to_ms(x: int) -> int:
    return x // 1000 if x > 10_000_000_000_000 else x


def download_and_load(cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    bars = []
    for y in range(START_YEAR, END_YEAR + 1):
        for m in range(1, 13):
            fn = f"BTCUSDT-1h-{y}-{m:02d}.zip"
            p = cache / fn
            if not p.exists():
                url = f"{BASE_URL}/{fn}"
                print("Downloading", url, flush=True)
                with urllib.request.urlopen(url, timeout=60) as r:
                    p.write_bytes(r.read())
            with zipfile.ZipFile(p) as z:
                names = [n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names) != 1:
                    raise RuntimeError(f"Unexpected zip contents in {fn}: {z.namelist()}")
                rd = csv.reader(io.StringIO(z.read(names[0]).decode('utf-8')))
                for row in rd:
                    if not row or not row[0].strip().isdigit():
                        continue
                    bars.append(Bar(ts_to_ms(int(row[0])), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])))
    uniq = {b.ts:b for b in bars}
    bars = [uniq[k] for k in sorted(uniq)]
    print(f"Loaded {len(bars)} H1 bars")
    return bars


def ema(values, length):
    out = [None] * len(values)
    if len(values) < length:
        return out
    seed = sum(values[:length]) / length
    out[length-1] = seed
    a = 2.0 / (length + 1.0)
    for i in range(length, len(values)):
        out[i] = values[i] * a + out[i-1] * (1-a)
    return out


def atr(bars, length=14):
    tr=[]
    for i,b in enumerate(bars):
        if i==0: tr.append(b.h-b.l)
        else:
            pc=bars[i-1].c
            tr.append(max(b.h-b.l, abs(b.h-pc), abs(b.l-pc)))
    out=[None]*len(bars)
    if len(bars)<length: return out
    out[length-1]=sum(tr[:length])/length
    for i in range(length,len(bars)):
        out[i]=(out[i-1]*(length-1)+tr[i])/length
    return out


def build_h4_regime(bars):
    groups=[]; cur_key=None; cur=[]
    for b in bars:
        dt=datetime.fromtimestamp(b.ts/1000, timezone.utc)
        key=(dt.year,dt.month,dt.day,dt.hour//4)
        if key!=cur_key:
            if len(cur)==4: groups.append((cur[-1].ts, cur[-1].c))
            cur_key=key; cur=[b]
        else: cur.append(b)
    if len(cur)==4: groups.append((cur[-1].ts, cur[-1].c))
    closes=[x[1] for x in groups]
    e50=ema(closes,50); e200=ema(closes,200)
    state={}
    for i,(ts,c) in enumerate(groups):
        ok=False
        if i>=203 and e50[i] is not None and e200[i] is not None and e50[i-4] is not None:
            ok = c > e200[i] and e50[i] > e200[i] and e50[i] > e50[i-4]
        state[ts]=ok
    ends=sorted(state); regime=[False]*len(bars); j=-1
    for i,b in enumerate(bars):
        while j+1<len(ends) and ends[j+1] <= b.ts: j+=1
        regime[i]=state[ends[j]] if j>=0 else False
    return regime


def bar_exit_path(bar, stop, target):
    hs=bar.l<=stop; ht=bar.h>=target
    if not hs and not ht: return None,None
    if hs and not ht: return 'stop',stop
    if ht and not hs: return 'target',target
    if abs(bar.o-bar.h) < abs(bar.o-bar.l): return 'target',target
    return 'stop',stop


def run_config(bars, atrv, regime, e20, e50, cfg, pullback_window, target_r, commission=COMMISSION, detail=False):
    equity=INITIAL_CAPITAL; peak=equity; max_dd=0.0; max_dd_dollars=0.0
    gross_profit=0.0; gross_loss=0.0; total_commission=0.0
    annual={y:0.0 for y in range(START_YEAR,END_YEAR+1)}
    monthly={f"{y}-{m:02d}":0.0 for y in range(START_YEAR,END_YEAR+1) for m in range(1,13)}
    trades=[]; equity_points=[]; pos=None; pending=None

    for i,b in enumerate(bars):
        dt=datetime.fromtimestamp(b.ts/1000, timezone.utc)
        if not (START_YEAR <= dt.year <= END_YEAR): continue

        if pos is None and pending is not None and pending['entry_index']==i:
            entry=b.o; stop_dist=ATR_MULT*pending['atr']; stop=entry-stop_dist
            if stop_dist>0 and stop>0:
                risk_cash=equity*RISK_PCT
                qty=min(risk_cash/stop_dist, equity/entry)
                if qty>0:
                    target=entry+target_r*stop_dist
                    entry_comm=qty*entry*commission
                    equity-=entry_comm; total_commission+=entry_comm
                    pos={'entry':entry,'qty':qty,'stop':stop,'target':target,'entry_comm':entry_comm,'entry_ts':b.ts,'risk_cash':qty*stop_dist,'entry_index':i}
            pending=None

        if pos is not None:
            reason,px=bar_exit_path(b,pos['stop'],pos['target'])
            if reason:
                exit_comm=pos['qty']*px*commission; total_commission+=exit_comm
                price_pnl=pos['qty']*(px-pos['entry'])
                pnl=price_pnl-pos['entry_comm']-exit_comm
                equity += price_pnl-exit_comm
                gross_profit += max(pnl,0.0); gross_loss += min(pnl,0.0)
                annual[dt.year]+=pnl; monthly[f"{dt.year}-{dt.month:02d}"]+=pnl
                trades.append({
                    'config':cfg,'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'entry_price':pos['entry'],'exit_price':px,'qty':pos['qty'],
                    'pnl':pnl,'r_multiple':(pnl/pos['risk_cash']) if pos['risk_cash']>0 else 0.0,'reason':reason,
                    'duration_hours':i-pos['entry_index'],'entry_commission':pos['entry_comm'],'exit_commission':exit_comm
                })
                pos=None

        peak=max(peak,equity)
        dd_dollars=peak-equity
        dd_pct=dd_dollars/peak if peak>0 else 0.0
        max_dd=max(max_dd,dd_pct); max_dd_dollars=max(max_dd_dollars,dd_dollars)
        if detail: equity_points.append({'config':cfg,'ts':b.ts,'equity':equity})

        if pos is None and pending is None and i >= max(200,pullback_window,ATR_LEN)+1:
            if atrv[i] is None or e20[i] is None or e50[i] is None or not regime[i]: continue
            if not (b.c > e50[i] and e20[i] > e50[i] and b.c > e20[i] and b.c > bars[i-1].h and b.c > b.o): continue
            touched=False
            for j in range(i-pullback_window+1, i+1):
                if j>=0 and e20[j] is not None and bars[j].l <= e20[j]:
                    touched=True; break
            if touched and i+1 < len(bars): pending={'entry_index':i+1,'atr':atrv[i]}

    net=equity-INITIAL_CAPITAL
    pf=gross_profit/abs(gross_loss) if gross_loss<0 else (math.inf if gross_profit>0 else 0.0)
    recovery=net/max_dd_dollars if max_dd_dollars>0 else (math.inf if net>0 else 0.0)
    wins=[t for t in trades if t['pnl']>0]; losses=[t for t in trades if t['pnl']<0]
    win_rate=len(wins)/len(trades)*100 if trades else 0.0
    avg_win=sum(t['pnl'] for t in wins)/len(wins) if wins else 0.0
    avg_loss=sum(t['pnl'] for t in losses)/len(losses) if losses else 0.0
    payoff=avg_win/abs(avg_loss) if avg_loss<0 else 0.0
    expectancy=net/len(trades) if trades else 0.0
    durations=[t['duration_hours'] for t in trades]
    profitable_months=sum(1 for v in monthly.values() if v>0); losing_months=sum(1 for v in monthly.values() if v<0)
    max_win_streak=max_loss_streak=curw=curl=0
    for t in trades:
        if t['pnl']>0: curw+=1; curl=0; max_win_streak=max(max_win_streak,curw)
        elif t['pnl']<0: curl+=1; curw=0; max_loss_streak=max(max_loss_streak,curl)
    best_month=max(monthly.items(), key=lambda kv:kv[1]) if monthly else ('',0.0)
    worst_month=min(monthly.items(), key=lambda kv:kv[1]) if monthly else ('',0.0)
    result={
        'configuration':cfg,'pullback_window':pullback_window,'target_r':target_r,'commission_per_order':commission,
        'initial_capital':INITIAL_CAPITAL,'ending_equity':equity,'net_profit':net,'return_pct':net/INITIAL_CAPITAL*100,
        'profit_factor':pf,'closed_trades':len(trades),'wins':len(wins),'losses':len(losses),'win_rate_pct':win_rate,
        'gross_profit':gross_profit,'gross_loss':gross_loss,'avg_win':avg_win,'avg_loss':avg_loss,'payoff_ratio':payoff,
        'expectancy_per_trade':expectancy,'max_equity_drawdown_pct':max_dd*100,'max_drawdown_dollars':max_dd_dollars,
        'recovery_factor':recovery,'profitable_years':sum(1 for v in annual.values() if v>0),'annual_net_profit':annual,
        'profitable_months':profitable_months,'losing_months':losing_months,'best_month':best_month,'worst_month':worst_month,
        'max_win_streak':max_win_streak,'max_loss_streak':max_loss_streak,'avg_duration_hours':sum(durations)/len(durations) if durations else 0.0,
        'max_duration_hours':max(durations) if durations else 0,'total_commission':total_commission,'open_position_at_end':pos is not None,
    }
    return result,trades,monthly,equity_points


def passes(r):
    return r['net_profit']>0 and r['profit_factor']>=1.20 and r['closed_trades']>=100 and r['max_equity_drawdown_pct']<=20 and r['recovery_factor']>=1.25 and r['profitable_years']>=4


def main():
    out=Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-b-baseline')); cache=Path(os.environ.get('BTC_CACHE',out/'data'))
    out.mkdir(parents=True,exist_ok=True)
    bars=download_and_load(cache); closes=[b.c for b in bars]
    atrv=atr(bars,ATR_LEN); e20=ema(closes,20); e50=ema(closes,50); regime=build_h4_regime(bars)
    baseline=[]; all_trades=[]; all_monthly=[]; all_equity=[]
    for cfg,(window,target_r) in CONFIGS.items():
        r,tr,mo,eq=run_config(bars,atrv,regime,e20,e50,cfg,window,target_r,COMMISSION,detail=True)
        r['decision']='Advance' if passes(r) else 'Retire'; baseline.append(r); all_trades.extend(tr); all_equity.extend(eq)
        for month,pnl in mo.items(): all_monthly.append({'config':cfg,'month':month,'pnl':pnl})
        print(json.dumps(r,indent=2))
    stress=[]
    for r0 in baseline:
        if r0['decision']=='Advance':
            r,_,_,_=run_config(bars,atrv,regime,e20,e50,r0['configuration'],r0['pullback_window'],r0['target_r'],0.0015,False)
            r['stress_pass']=r['net_profit']>0 and r['profit_factor']>=1.15; stress.append(r)
    result={'protocol':'BTCUSDT Architecture B frozen baseline','source':'Binance public Spot monthly 1h klines','development_period':'2021-01-01 through 2025-12-31','oos_locked':'2026-01-01 onward','oos_tested':False,'baseline':baseline,'cost_stress':stress,'architecture_decision':'Advance' if any(r['decision']=='Advance' for r in baseline) else 'Retire'}
    (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        cols=['configuration','net_profit','return_pct','profit_factor','closed_trades','win_rate_pct','expectancy_per_trade','max_equity_drawdown_pct','recovery_factor','profitable_years','total_commission','decision']
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader();
        for r in baseline: w.writerow({k:r[k] for k in cols})
    if all_trades:
        with (out/'trades.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(all_trades[0].keys())); w.writeheader(); w.writerows(all_trades)
    with (out/'monthly.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['config','month','pnl']); w.writeheader(); w.writerows(all_monthly)
    with (out/'equity_curve.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['config','ts','equity']); w.writeheader(); w.writerows(all_equity)
    print('Wrote Architecture B artifacts')

if __name__=='__main__': main()
