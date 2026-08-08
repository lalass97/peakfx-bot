#!/usr/bin/env python3
import csv, hashlib, io, json, math, os, urllib.request, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = 'https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h'
INITIAL_CAPITAL = 10000.0
RISK_PCT = 0.0025
BASE_COMMISSION = 0.001
DEV_START_MS = int(datetime(2021,1,1,tzinfo=timezone.utc).timestamp()*1000)
DEV_END_MS = int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000)
CONFIGS = {
    'BF01': (18, 2, 2.0),
    'BF02': (36, 2, 2.0),
    'BF03': (18, 3, 3.0),
    'BF04': (36, 3, 3.0),
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_h1(cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    bars, manifest = [], []
    # 2020 is warm-up only. 2026 is deliberately never requested.
    for y in range(2020, 2026):
        for m in range(1, 13):
            fn = f'BTCUSDT-1h-{y}-{m:02d}.zip'
            p = cache / fn
            if not p.exists():
                with urllib.request.urlopen(f'{BASE_URL}/{fn}', timeout=60) as r:
                    p.write_bytes(r.read())
            manifest.append({'file': fn, 'sha256': sha256_file(p), 'bytes': p.stat().st_size})
            with zipfile.ZipFile(p) as z:
                names = [n for n in z.namelist() if n.lower().endswith('.csv')]
                if len(names) != 1:
                    raise RuntimeError(f'Unexpected zip contents: {fn}')
                for row in csv.reader(io.StringIO(z.read(names[0]).decode('utf-8'))):
                    if not row or not row[0].strip().isdigit():
                        continue
                    bars.append(Bar(ts_to_ms(int(row[0])), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])))
    uniq = {b.ts: b for b in bars}
    bars = [uniq[k] for k in sorted(uniq)]
    return bars, manifest


def aggregate_h4(h1):
    groups = {}
    for b in h1:
        dt = datetime.fromtimestamp(b.ts / 1000, timezone.utc)
        start_hour = (dt.hour // 4) * 4
        key_dt = dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        key = int(key_dt.timestamp() * 1000)
        groups.setdefault(key, []).append(b)
    out, violations = [], []
    one_hour = 3_600_000
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda x: x.ts)
        expected = [key + j * one_hour for j in range(4)]
        actual = [x.ts for x in g]
        if len(g) != 4 or actual != expected:
            violations.append({'h4_start': key, 'actual_h1_timestamps': actual})
            continue
        out.append(Bar(key, g[0].o, max(x.h for x in g), min(x.l for x in g), g[-1].c, sum(x.v for x in g)))
    return out, violations


def ema(values, n):
    out = [None] * len(values)
    if len(values) < n:
        return out
    out[n-1] = sum(values[:n]) / n
    a = 2 / (n + 1)
    for i in range(n, len(values)):
        out[i] = values[i] * a + out[i-1] * (1-a)
    return out


def atr(bars, n=14):
    tr = []
    for i, b in enumerate(bars):
        pc = bars[i-1].c if i else b.c
        tr.append(max(b.h-b.l, abs(b.h-pc), abs(b.l-pc)))
    out = [None] * len(bars)
    if len(bars) < n:
        return out
    out[n-1] = sum(tr[:n]) / n
    for i in range(n, len(bars)):
        out[i] = (out[i-1] * (n-1) + tr[i]) / n
    return out


def update_dd(eq, peak, max_dd_cash, max_dd_pct):
    peak = max(peak, eq)
    dd_cash = peak - eq
    dd_pct = dd_cash / peak if peak else 0.0
    return peak, max(max_dd_cash, dd_cash), max(max_dd_pct, dd_pct)


def run_config(bars, e200, a14, cfg, lookback, reclaim_window, target_r, commission=BASE_COMMISSION, detail=False):
    balance = INITIAL_CAPITAL
    pos = None
    candidate = None
    pending_entry = None
    pending_time_exit = False
    trades = []
    curve = []
    annual = {y: 0.0 for y in range(2021, 2026)}
    gp = gl = total_commission = 0.0
    peak_mtm = INITIAL_CAPITAL
    max_dd_cash = max_dd_pct = 0.0
    integrity = []

    def close_position(px, ts, year, reason):
        nonlocal balance, pos, gp, gl, total_commission, pending_time_exit
        xc = pos['qty'] * px * commission
        price_pnl = pos['qty'] * (px - pos['entry'])
        pnl = price_pnl - pos['entry_comm'] - xc
        balance += price_pnl - xc
        total_commission += xc
        annual[year] += pnl
        gp += max(pnl, 0.0)
        gl += min(pnl, 0.0)
        trades.append({
            'config': cfg,
            'entry_ts': pos['entry_ts'],
            'exit_ts': ts,
            'entry': pos['entry'],
            'exit': px,
            'stop': pos['stop'],
            'target': pos['target'],
            'pnl': pnl,
            'reason': reason,
            'duration_hours': (ts - pos['entry_ts']) / 3_600_000,
            'risk_cash': pos['risk_cash'],
            'realized_r': pnl / pos['risk_cash'] if pos['risk_cash'] else 0.0,
        })
        pos = None
        pending_time_exit = False

    for i, b in enumerate(bars):
        if b.ts < DEV_START_MS or b.ts >= DEV_END_MS:
            continue
        year = datetime.fromtimestamp(b.ts/1000, timezone.utc).year

        # Time exit was decided only after the prior completed H4 bar.
        if pos is not None and pending_time_exit:
            close_position(b.o, b.ts, year, 'time_exit')

        # Entry executes only at the next H4 open after a completed reclaim signal.
        if pos is None and pending_entry is not None and pending_entry['entry_index'] == i:
            entry = b.o
            stop = pending_entry['breakdown_low'] - 0.25 * pending_entry['reclaim_atr']
            stop_dist = entry - stop
            if stop_dist > 0 and stop > 0:
                risk_budget = balance * RISK_PCT
                qty = min(risk_budget / stop_dist, balance / entry)
                if qty > 0:
                    entry_comm = qty * entry * commission
                    balance -= entry_comm
                    total_commission += entry_comm
                    pos = {
                        'entry': entry,
                        'entry_ts': b.ts,
                        'entry_index': i,
                        'qty': qty,
                        'stop': stop,
                        'target': entry + target_r * stop_dist,
                        'entry_comm': entry_comm,
                        'risk_cash': qty * stop_dist,
                    }
            pending_entry = None

        # Protective stop/target evaluation. Initial stop and target are fixed.
        if pos is not None:
            stop_hit = b.l <= pos['stop']
            target_hit = b.h >= pos['target']
            if b.o < pos['stop']:
                close_position(b.o, b.ts, year, 'stop_gap')
            elif b.o > pos['target']:
                close_position(b.o, b.ts, year, 'target_gap')
            elif stop_hit and target_hit:
                close_position(pos['stop'], b.ts, year, 'stop_both_touched_conservative')
            elif stop_hit:
                close_position(pos['stop'], b.ts, year, 'stop')
            elif target_hit:
                close_position(pos['target'], b.ts, year, 'target')

        # Mark-to-market after protective execution on this completed bar.
        mtm = balance
        if pos is not None:
            mtm = balance + pos['qty'] * (b.c - pos['entry']) - pos['qty'] * b.c * commission
        peak_mtm, max_dd_cash, max_dd_pct = update_dd(mtm, peak_mtm, max_dd_cash, max_dd_pct)
        if detail:
            curve.append({'config': cfg, 'ts': b.ts, 'equity_mtm': mtm, 'balance': balance})

        # If still in position, arm time exit only after 18 completed entry-and-later H4 bars survive.
        if pos is not None:
            bars_survived = i - pos['entry_index'] + 1
            if bars_survived >= 18 and i + 1 < len(bars):
                pending_time_exit = True
            continue

        if pending_entry is not None:
            continue

        # Candidate expiry occurs before evaluating a new completed H4 bar.
        if candidate is not None and i > candidate['breakdown_index'] + candidate['window']:
            candidate = None

        # A newer qualifying breakdown replaces any older candidate before reclaim evaluation.
        new_breakdown = False
        if i >= max(200, lookback, 12) and e200[i] is not None and e200[i-12] is not None and a14[i] is not None:
            support = min(x.l for x in bars[i-lookback:i])
            if b.c > e200[i] and e200[i] > e200[i-12] and b.l < support and b.c <= support:
                candidate = {
                    'breakdown_index': i,
                    'support': support,
                    'breakdown_low': b.l,
                    'window': reclaim_window,
                }
                new_breakdown = True

        if new_breakdown or candidate is None:
            continue

        # Reclaim must occur on a later completed H4 bar within the frozen window.
        if i <= candidate['breakdown_index']:
            continue
        if i > candidate['breakdown_index'] + candidate['window']:
            candidate = None
            continue
        if a14[i] is None:
            continue
        if b.c > candidate['support'] and b.c > b.o and b.c > bars[i-1].c and i + 1 < len(bars):
            pending_entry = {
                'entry_index': i + 1,
                'breakdown_low': candidate['breakdown_low'],
                'reclaim_atr': a14[i],
            }
            candidate = None

    # Mark any surviving development-end position to market at the last development H4 close.
    last_dev = None
    for b in reversed(bars):
        if DEV_START_MS <= b.ts < DEV_END_MS:
            last_dev = b
            break
    ending_equity = balance
    if pos is not None and last_dev is not None:
        ending_equity = balance + pos['qty'] * (last_dev.c - pos['entry']) - pos['qty'] * last_dev.c * commission

    net = ending_equity - INITIAL_CAPITAL
    pf = gp / abs(gl) if gl < 0 else (math.inf if gp > 0 else 0.0)
    recovery = net / max_dd_cash if max_dd_cash > 0 else (math.inf if net > 0 else 0.0)
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    profitable_years = sum(v > 0 for v in annual.values())
    result = {
        'configuration': cfg,
        'support_lookback_h4': lookback,
        'reclaim_window_h4': reclaim_window,
        'target_r': target_r,
        'initial_capital': INITIAL_CAPITAL,
        'ending_equity_mtm': ending_equity,
        'net_profit_mtm': net,
        'profit_factor_closed_trades': pf,
        'closed_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate_pct': (100 * len(wins) / len(trades)) if trades else 0.0,
        'gross_profit': gp,
        'gross_loss': gl,
        'total_commission': total_commission,
        'max_equity_drawdown_pct_mtm': max_dd_pct * 100,
        'max_drawdown_dollars_mtm': max_dd_cash,
        'recovery_factor_mtm': recovery,
        'annual_net_profit_closed': annual,
        'profitable_years': profitable_years,
        'open_position_at_end': pos is not None,
        'integrity_violations': integrity,
        'trades_detail': trades if detail else None,
        'equity_curve': curve if detail else None,
    }
    return result


def passes(r):
    return (
        r['net_profit_mtm'] > 0
        and r['profit_factor_closed_trades'] >= 1.20
        and r['closed_trades'] >= 40
        and r['max_equity_drawdown_pct_mtm'] <= 20
        and r['recovery_factor_mtm'] >= 1.25
        and r['profitable_years'] >= 4
        and not r['integrity_violations']
    )


def main():
    out = Path(os.environ.get('BTC_OUT', 'artifacts/btcusdt-arch-f-baseline'))
    cache = Path(os.environ.get('BTC_CACHE', out / 'data'))
    out.mkdir(parents=True, exist_ok=True)
    h1, manifest = load_h1(cache)
    bars, h4_violations = aggregate_h4(h1)
    closes = [b.c for b in bars]
    e200 = ema(closes, 200)
    a14 = atr(bars, 14)

    results, all_trades, all_curve = [], [], []
    for cfg, (lb, window, target) in CONFIGS.items():
        r = run_config(bars, e200, a14, cfg, lb, window, target, BASE_COMMISSION, True)
        if h4_violations:
            # Missing/nonconsecutive groups are omitted rather than fabricated. Report count for transparency.
            r['h4_incomplete_groups_omitted'] = len(h4_violations)
        else:
            r['h4_incomplete_groups_omitted'] = 0
        r['decision'] = 'Advance' if passes(r) else 'Retire'
        all_trades.extend(r['trades_detail'])
        all_curve.extend(r['equity_curve'])
        results.append({k:v for k,v in r.items() if k not in ('trades_detail','equity_curve')})
        print(json.dumps(results[-1], indent=2))

    architecture_decision = 'Advance' if any(r['decision'] == 'Advance' for r in results) else 'Retire'
    payload = {
        'protocol': 'BTCUSDT Architecture F frozen baseline',
        'strategy': 'Failed-Breakdown Reversal',
        'development_period': '2021-01-01 through 2025-12-31 UTC',
        'oos_2026_loaded': False,
        'source_data_manifest': manifest,
        'h4_incomplete_groups_omitted': h4_violations,
        'results': results,
        'architecture_decision': architecture_decision,
    }
    (out / 'results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    with (out / 'summary.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['config','net_profit_mtm','pf_closed','trades','win_rate_pct','dd_mtm_pct','recovery_mtm','profitable_years','open_at_end','decision'])
        for r in results:
            w.writerow([r['configuration'],r['net_profit_mtm'],r['profit_factor_closed_trades'],r['closed_trades'],r['win_rate_pct'],r['max_equity_drawdown_pct_mtm'],r['recovery_factor_mtm'],r['profitable_years'],r['open_position_at_end'],r['decision']])
    with (out / 'trades.csv').open('w', newline='', encoding='utf-8') as f:
        fields = ['config','entry_ts','exit_ts','entry','exit','stop','target','pnl','reason','duration_hours','risk_cash','realized_r']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(all_trades)
    with (out / 'equity_curve.csv').open('w', newline='', encoding='utf-8') as f:
        fields = ['config','ts','equity_mtm','balance']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(all_curve)
    with (out / 'data_hashes.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['file','sha256','bytes'])
        w.writeheader(); w.writerows(manifest)

if __name__ == '__main__':
    main()
