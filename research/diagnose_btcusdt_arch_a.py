#!/usr/bin/env python3
"""Post-baseline diagnostics for frozen BTCUSDT Architecture A.

This module DOES NOT change signal, sizing, execution, cost, or date rules. It
replays the frozen baseline and emits richer diagnostics, then verifies its
headline metrics against the baseline results.json before writing artifacts.
2026+ remains untouched.
"""
import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import backtest_btcusdt_arch_a as base


def iso(ts):
    return datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat()


def month_key(ts):
    return datetime.fromtimestamp(ts / 1000, timezone.utc).strftime('%Y-%m')


def year_of(ts):
    return datetime.fromtimestamp(ts / 1000, timezone.utc).year


def max_streak(values, predicate):
    best = cur = 0
    for v in values:
        if predicate(v):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def run_diagnostic(bars, atr, regime, cfg, channel, target_r, commission=base.COMMISSION):
    equity = base.INITIAL_CAPITAL
    peak = equity
    max_dd = 0.0
    max_dd_cash = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    trades = []
    equity_curve = []
    pos = None
    pending = None
    annual = {y: 0.0 for y in range(base.START_YEAR, base.END_YEAR + 1)}

    for i, b in enumerate(bars):
        dt = datetime.fromtimestamp(b.ts / 1000, timezone.utc)
        if dt.year < base.START_YEAR or dt.year > base.END_YEAR:
            continue

        if pos is None and pending is not None and pending['entry_index'] == i:
            entry = b.o
            stop_dist = base.ATR_MULT * pending['atr']
            stop = entry - stop_dist
            if stop <= 0 or stop_dist <= 0:
                pending = None
            else:
                risk_cash = equity * base.RISK_PCT
                qty = risk_cash / stop_dist
                qty = min(qty, equity / entry)
                if qty > 0:
                    target = entry + target_r * stop_dist
                    entry_comm = qty * entry * commission
                    equity_before_entry = equity
                    equity -= entry_comm
                    pos = {
                        'entry': entry, 'qty': qty, 'stop': stop, 'target': target,
                        'entry_comm': entry_comm, 'entry_ts': b.ts,
                        'signal_ts': pending['signal_ts'], 'signal_atr': pending['atr'],
                        'risk_cash_intended': risk_cash,
                        'equity_before_entry': equity_before_entry,
                        'notional': qty * entry,
                    }
                pending = None

        if pos is not None:
            reason, px = base.bar_exit_path(b, pos['stop'], pos['target'])
            if reason:
                exit_comm = pos['qty'] * px * commission
                price_pnl = pos['qty'] * (px - pos['entry'])
                pnl = price_pnl - pos['entry_comm'] - exit_comm
                equity += price_pnl - exit_comm
                if pnl >= 0:
                    gross_profit += pnl
                else:
                    gross_loss += pnl
                annual[dt.year] += pnl
                duration_hours = (b.ts - pos['entry_ts']) / 3_600_000.0
                initial_stop_risk = pos['qty'] * (pos['entry'] - pos['stop'])
                realized_r = pnl / initial_stop_risk if initial_stop_risk > 0 else None
                trades.append({
                    'config': cfg,
                    'entry_time_utc': iso(pos['entry_ts']),
                    'exit_time_utc': iso(b.ts),
                    'signal_time_utc': iso(pos['signal_ts']),
                    'entry_price': pos['entry'],
                    'exit_price': px,
                    'stop_price': pos['stop'],
                    'target_price': pos['target'],
                    'quantity_btc': pos['qty'],
                    'notional_usdt': pos['notional'],
                    'entry_commission': pos['entry_comm'],
                    'exit_commission': exit_comm,
                    'total_commission': pos['entry_comm'] + exit_comm,
                    'pnl_usdt': pnl,
                    'realized_r_after_costs': realized_r,
                    'duration_hours': duration_hours,
                    'exit_reason': reason,
                    'exit_month': month_key(b.ts),
                    'exit_year': year_of(b.ts),
                    'equity_after_exit': equity,
                })
                equity_curve.append({'time_utc': iso(b.ts), 'equity': equity, 'config': cfg})
                pos = None

        peak = max(peak, equity)
        dd_cash = peak - equity
        max_dd_cash = max(max_dd_cash, dd_cash)
        if peak > 0:
            max_dd = max(max_dd, dd_cash / peak)

        if pos is None and pending is None and i >= max(channel, base.ATR_LEN):
            if atr[i] is None or not regime[i]:
                continue
            prev_high = max(x.h for x in bars[i-channel:i])
            if b.c > prev_high and i + 1 < len(bars):
                pending = {'entry_index': i + 1, 'atr': atr[i], 'signal_ts': b.ts}

    pnls = [t['pnl_usdt'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    breakeven = [p for p in pnls if p == 0]
    durations = [t['duration_hours'] for t in trades]
    commissions = [t['total_commission'] for t in trades]
    realized_rs = [t['realized_r_after_costs'] for t in trades if t['realized_r_after_costs'] is not None]
    targets = sum(t['exit_reason'] == 'target' for t in trades)
    stops = sum(t['exit_reason'] == 'stop' for t in trades)

    monthly = defaultdict(float)
    for t in trades:
        monthly[t['exit_month']] += t['pnl_usdt']
    all_months = []
    for y in range(base.START_YEAR, base.END_YEAR + 1):
        for m in range(1, 13):
            k = f'{y}-{m:02d}'
            all_months.append({'month': k, 'net_profit': monthly.get(k, 0.0)})

    net = equity - base.INITIAL_CAPITAL
    pf = gross_profit / abs(gross_loss) if gross_loss < 0 else (math.inf if gross_profit > 0 else 0.0)
    recovery = net / (max_dd * base.INITIAL_CAPITAL) if max_dd > 0 else (math.inf if net > 0 else 0.0)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    win_rate = len(wins) / len(trades) if trades else 0.0
    payoff = avg_win / abs(avg_loss) if avg_loss < 0 else math.inf
    expectancy = sum(pnls) / len(trades) if trades else 0.0

    return {
        'configuration': cfg,
        'channel': channel,
        'target_r': target_r,
        'commission_per_order': commission,
        'initial_capital': base.INITIAL_CAPITAL,
        'ending_equity': equity,
        'net_profit': net,
        'return_pct': net / base.INITIAL_CAPITAL * 100.0,
        'profit_factor': pf,
        'closed_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'breakeven_trades': len(breakeven),
        'win_rate_pct': win_rate * 100.0,
        'avg_win_usdt': avg_win,
        'avg_loss_usdt': avg_loss,
        'payoff_ratio': payoff,
        'expectancy_usdt_per_trade': expectancy,
        'avg_realized_r_after_costs': sum(realized_rs) / len(realized_rs) if realized_rs else 0.0,
        'max_consecutive_wins': max_streak(pnls, lambda x: x > 0),
        'max_consecutive_losses': max_streak(pnls, lambda x: x < 0),
        'target_exits': targets,
        'stop_exits': stops,
        'avg_duration_hours': sum(durations) / len(durations) if durations else 0.0,
        'median_duration_hours': sorted(durations)[len(durations)//2] if durations else 0.0,
        'max_duration_hours': max(durations) if durations else 0.0,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'total_commission_usdt': sum(commissions),
        'avg_commission_per_trade_usdt': sum(commissions)/len(commissions) if commissions else 0.0,
        'max_equity_drawdown_pct': max_dd * 100.0,
        'max_drawdown_cash_usdt': max_dd_cash,
        'recovery_factor': recovery,
        'annual_net_profit': annual,
        'profitable_years': sum(v > 0 for v in annual.values()),
        'profitable_months': sum(x['net_profit'] > 0 for x in all_months),
        'losing_months': sum(x['net_profit'] < 0 for x in all_months),
        'flat_months': sum(x['net_profit'] == 0 for x in all_months),
        'best_month': max(all_months, key=lambda x: x['net_profit']) if all_months else None,
        'worst_month': min(all_months, key=lambda x: x['net_profit']) if all_months else None,
        'open_position_at_end': pos is not None,
        'monthly_net_profit': all_months,
        'trades': trades,
        'equity_curve': equity_curve,
    }


def close_enough(a, b, tol=1e-7):
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def verify_against_baseline(diag, baseline_result):
    by_cfg = {r['configuration']: r for r in baseline_result['baseline']}
    checks = []
    for r in diag:
        b = by_cfg[r['configuration']]
        fields = ['ending_equity','net_profit','profit_factor','closed_trades','max_equity_drawdown_pct','recovery_factor','gross_profit','gross_loss']
        for f in fields:
            ok = (r[f] == b[f]) if f == 'closed_trades' else close_enough(r[f], b[f])
            checks.append({'config': r['configuration'], 'field': f, 'diagnostic': r[f], 'baseline': b[f], 'match': ok})
            if not ok:
                raise RuntimeError(f"Diagnostic replay mismatch {r['configuration']} {f}: {r[f]} != {b[f]}")
    return checks


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fields})


def main():
    out = Path(os.environ.get('BTC_OUT', 'artifacts/btcusdt-arch-a-baseline'))
    cache = Path(os.environ.get('BTC_CACHE', out / 'data'))
    baseline_path = out / 'results.json'
    if not baseline_path.exists():
        raise RuntimeError(f'Missing baseline artifact: {baseline_path}')

    baseline_result = json.loads(baseline_path.read_text(encoding='utf-8'))
    bars = base.download_and_load(cache)
    atr = base.atr14(bars)
    regime = base.build_h4_regime(bars)

    diagnostics = []
    for cfg, (channel, target_r) in base.CONFIGS.items():
        diagnostics.append(run_diagnostic(bars, atr, regime, cfg, channel, target_r, base.COMMISSION))

    verification = verify_against_baseline(diagnostics, baseline_result)

    compact = []
    all_trades = []
    all_monthly = []
    all_equity = []
    for r in diagnostics:
        compact.append({k: v for k, v in r.items() if k not in ('trades','monthly_net_profit','equity_curve')})
        all_trades.extend(r['trades'])
        all_monthly.extend({'config': r['configuration'], **x} for x in r['monthly_net_profit'])
        all_equity.extend(r['equity_curve'])

    payload = {
        'protocol': 'BTCUSDT Architecture A frozen baseline diagnostics',
        'source': 'Binance public Spot monthly 1h klines',
        'development_period': '2021-01-01 through 2025-12-31',
        'oos_locked': '2026-01-01 onward',
        'oos_tested': False,
        'strategy_rules_changed': False,
        'baseline_replay_verified': all(x['match'] for x in verification),
        'verification': verification,
        'diagnostics': compact,
    }
    (out / 'diagnostics.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')

    summary_fields = [
        'configuration','ending_equity','net_profit','return_pct','profit_factor','closed_trades',
        'wins','losses','breakeven_trades','win_rate_pct','avg_win_usdt','avg_loss_usdt','payoff_ratio',
        'expectancy_usdt_per_trade','avg_realized_r_after_costs','max_consecutive_wins','max_consecutive_losses',
        'target_exits','stop_exits','avg_duration_hours','median_duration_hours','max_duration_hours',
        'gross_profit','gross_loss','total_commission_usdt','avg_commission_per_trade_usdt',
        'max_equity_drawdown_pct','max_drawdown_cash_usdt','recovery_factor','profitable_years',
        'profitable_months','losing_months','flat_months','open_position_at_end'
    ]
    write_csv(out / 'diagnostic_summary.csv', compact, summary_fields)

    trade_fields = [
        'config','signal_time_utc','entry_time_utc','exit_time_utc','entry_price','exit_price','stop_price',
        'target_price','quantity_btc','notional_usdt','entry_commission','exit_commission','total_commission',
        'pnl_usdt','realized_r_after_costs','duration_hours','exit_reason','exit_month','exit_year','equity_after_exit'
    ]
    write_csv(out / 'trades.csv', all_trades, trade_fields)
    write_csv(out / 'monthly.csv', all_monthly, ['config','month','net_profit'])
    write_csv(out / 'equity_curve.csv', all_equity, ['config','time_utc','equity'])

    print(json.dumps(compact, indent=2))
    print('Baseline replay verified: TRUE')
    print('2026 OOS tested: FALSE')


if __name__ == '__main__':
    main()
