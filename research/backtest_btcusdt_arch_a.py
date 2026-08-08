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
    "BA01": (20, 2.0),
    "BA02": (40, 2.0),
    "BA03": (20, 3.0),
    "BA04": (40, 3.0),
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
    # Binance Spot timestamps are milliseconds before 2025 and microseconds from 2025-01-01 onward.
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
                raw = z.read(names[0]).decode('utf-8')
                rd = csv.reader(io.StringIO(raw))
                for row in rd:
                    if not row or not row[0].strip().isdigit():
                        continue
                    bars.append(Bar(ts_to_ms(int(row[0])), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])))
    bars.sort(key=lambda b: b.ts)
    # De-duplicate and enforce strictly hourly continuity where data exists.
    uniq = {}
    for b in bars:
        uniq[b.ts] = b
    bars = [uniq[k] for k in sorted(uniq)]
    print(f"Loaded {len(bars)} unique H1 bars from {datetime.fromtimestamp(bars[0].ts/1000,timezone.utc)} to {datetime.fromtimestamp(bars[-1].ts/1000,timezone.utc)}")
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


def atr14(bars):
    tr = [None] * len(bars)
    for i,b in enumerate(bars):
        if i == 0:
            tr[i] = b.h - b.l
        else:
            pc = bars[i-1].c
            tr[i] = max(b.h-b.l, abs(b.h-pc), abs(b.l-pc))
    out = [None]*len(bars)
    if len(bars) < ATR_LEN:
        return out
    seed = sum(tr[:ATR_LEN])/ATR_LEN
    out[ATR_LEN-1] = seed
    for i in range(ATR_LEN, len(bars)):
        out[i] = (out[i-1]*(ATR_LEN-1) + tr[i])/ATR_LEN
    return out


def build_h4_regime(bars):
    # Build UTC H4 bars from H1. Only complete groups of 4 consecutive hourly bars are used.
    groups = []
    cur_key = None
    cur = []
    for b in bars:
        dt = datetime.fromtimestamp(b.ts/1000, timezone.utc)
        key = (dt.year, dt.month, dt.day, dt.hour // 4)
        if key != cur_key:
            if len(cur) == 4:
                groups.append((cur[-1].ts, cur[-1].c))
            cur_key, cur = key, [b]
        else:
            cur.append(b)
    if len(cur) == 4:
        groups.append((cur[-1].ts, cur[-1].c))
    closes = [x[1] for x in groups]
    e = ema(closes, 200)
    regime_by_end = {}
    for i,(end_ts,c) in enumerate(groups):
        ok = False
        if i >= 203 and e[i] is not None and e[i-4] is not None:
            ok = c > e[i] and e[i] > e[i-4]
        regime_by_end[end_ts] = ok
    # For each H1 signal bar, use the most recently completed H4 bar at or before that H1 close.
    regime = [False]*len(bars)
    ends = sorted(regime_by_end)
    j = -1
    for i,b in enumerate(bars):
        while j+1 < len(ends) and ends[j+1] <= b.ts:
            j += 1
        regime[i] = regime_by_end[ends[j]] if j >= 0 else False
    return regime


def bar_exit_path(bar, stop, target):
    hit_s = bar.l <= stop
    hit_t = bar.h >= target
    if not hit_s and not hit_t:
        return None, None
    if hit_s and not hit_t:
        return 'stop', stop
    if hit_t and not hit_s:
        return 'target', target
    # Approximate TradingView broker emulator intrabar path:
    # open->high->low->close if open is closer to high, else open->low->high->close.
    if abs(bar.o - bar.h) < abs(bar.o - bar.l):
        return 'target', target
    return 'stop', stop


def run_config(bars, atr, regime, cfg, channel, target_r, commission=COMMISSION):
    equity = INITIAL_CAPITAL
    peak = equity
    max_dd = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    trades = []
    pos = None
    pending = None
    annual = {y:0.0 for y in range(START_YEAR, END_YEAR+1)}

    for i,b in enumerate(bars):
        dt = datetime.fromtimestamp(b.ts/1000, timezone.utc)
        if dt.year < START_YEAR or dt.year > END_YEAR:
            continue

        # Enter at this bar's open from previous completed signal bar.
        if pos is None and pending is not None and pending['entry_index'] == i:
            entry = b.o
            stop_dist = ATR_MULT * pending['atr']
            stop = entry - stop_dist
            if stop <= 0 or stop_dist <= 0:
                pending = None
            else:
                risk_cash = equity * RISK_PCT
                qty = risk_cash / stop_dist
                qty = min(qty, equity / entry)  # no leverage; cap gross notional to equity
                if qty > 0:
                    target = entry + target_r * stop_dist
                    entry_comm = qty * entry * commission
                    equity -= entry_comm
                    pos = {'entry':entry,'qty':qty,'stop':stop,'target':target,'entry_comm':entry_comm,'entry_ts':b.ts}
                pending = None

        if pos is not None:
            reason, px = bar_exit_path(b, pos['stop'], pos['target'])
            if reason:
                exit_comm = pos['qty'] * px * commission
                pnl_before_exit_comm = pos['qty'] * (px - pos['entry'])
                pnl_trade = pnl_before_exit_comm - pos['entry_comm'] - exit_comm
                # entry commission was already subtracted; apply price pnl and exit commission now
                equity += pnl_before_exit_comm - exit_comm
                if pnl_trade >= 0:
                    gross_profit += pnl_trade
                else:
                    gross_loss += pnl_trade
                annual[dt.year] += pnl_trade
                trades.append({'entry_ts':pos['entry_ts'],'exit_ts':b.ts,'pnl':pnl_trade,'reason':reason})
                pos = None

        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak-equity)/peak)

        # Signal only if flat, no pending entry, and enough completed history.
        if pos is None and pending is None and i >= max(channel, ATR_LEN):
            if atr[i] is None or not regime[i]:
                continue
            prev_high = max(x.h for x in bars[i-channel:i])
            # Frozen spec: close strictly above prior channel. No bullish-candle requirement in spec.
            if b.c > prev_high:
                if i+1 < len(bars):
                    pending = {'entry_index':i+1,'atr':atr[i]}

    # Mark open position to final close only for reporting? Frozen closed-trade metrics should not invent exit.
    net = equity - INITIAL_CAPITAL
    pf = gross_profit / abs(gross_loss) if gross_loss < 0 else (math.inf if gross_profit > 0 else 0.0)
    recovery = net / (max_dd * INITIAL_CAPITAL) if max_dd > 0 else (math.inf if net > 0 else 0.0)
    profitable_years = sum(1 for v in annual.values() if v > 0)
    return {
        'configuration': cfg,
        'channel': channel,
        'target_r': target_r,
        'commission_per_order': commission,
        'initial_capital': INITIAL_CAPITAL,
        'ending_equity': equity,
        'net_profit': net,
        'profit_factor': pf,
        'closed_trades': len(trades),
        'max_equity_drawdown_pct': max_dd*100,
        'recovery_factor': recovery,
        'annual_net_profit': annual,
        'profitable_years': profitable_years,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'open_position_at_end': pos is not None,
    }


def passes(r):
    return (
        r['net_profit'] > 0 and
        r['profit_factor'] >= 1.20 and
        r['closed_trades'] >= 100 and
        r['max_equity_drawdown_pct'] <= 20.0 and
        r['recovery_factor'] >= 1.25 and
        r['profitable_years'] >= 4
    )


def main():
    out = Path(os.environ.get('BTC_OUT','artifacts/btcusdt-arch-a-baseline'))
    cache = Path(os.environ.get('BTC_CACHE', out/'data'))
    out.mkdir(parents=True, exist_ok=True)
    bars = download_and_load(cache)
    atr = atr14(bars)
    regime = build_h4_regime(bars)

    baseline = []
    for cfg,(channel,target_r) in CONFIGS.items():
        r = run_config(bars, atr, regime, cfg, channel, target_r, COMMISSION)
        r['decision'] = 'Advance' if passes(r) else 'Retire'
        baseline.append(r)
        print(json.dumps(r, indent=2))

    any_pass = any(r['decision']=='Advance' for r in baseline)
    stress = []
    if any_pass:
        for r0 in baseline:
            if r0['decision']=='Advance':
                r = run_config(bars, atr, regime, r0['configuration'], r0['channel'], r0['target_r'], 0.0015)
                r['stress_pass'] = r['net_profit'] > 0 and r['profit_factor'] >= 1.15
                stress.append(r)

    result = {
        'protocol':'BTCUSDT Architecture A frozen baseline',
        'source':'Binance public Spot monthly 1h klines',
        'development_period':'2021-01-01 through 2025-12-31',
        'oos_locked':'2026-01-01 onward',
        'oos_tested':False,
        'baseline':baseline,
        'cost_stress':stress,
        'architecture_decision':'Advance' if any_pass else 'Retire',
        'notes':[
            'Long-only; entry on next H1 bar open after completed-bar breakout signal.',
            'H4 regime requires completed H4 close > EMA200 and EMA200 rising versus four completed H4 bars earlier.',
            'No leverage; notional capped at current equity.',
            '0.10% commission per order baseline; no slippage.',
            'If both stop and target are touched within one H1 bar, TradingView-style OHLC path approximation is used.'
        ]
    }
    (out/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    with (out/'summary.csv').open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['config','net_profit','profit_factor','closed_trades','max_dd_pct','recovery_factor','profitable_years','decision'])
        for r in baseline:
            w.writerow([r['configuration'],f"{r['net_profit']:.2f}",f"{r['profit_factor']:.4f}",r['closed_trades'],f"{r['max_equity_drawdown_pct']:.4f}",f"{r['recovery_factor']:.4f}",r['profitable_years'],r['decision']])
    print('Wrote', out/'results.json')

if __name__ == '__main__':
    main()
