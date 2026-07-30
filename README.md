# PeakFX Bot

PeakFX is an EUR/USD H1 trend-following research and MetaTrader 5 project. Version 1 is intentionally configured for demo/paper trading first.

## Strategy

- Symbol: EURUSD
- Timeframe: H1
- Entry: EMA 12/50 crossover confirmed on a completed candle
- Trend filter: close relative to EMA 200 plus EMA 200 slope
- Stop loss: 1.5 ATR
- Target: 1.5R
- Initial risk: 0.25% of equity per trade
- Maximum open PeakFX positions: 1
- Maximum trades per day: 2
- Daily equity-loss lock: 1.5%
- Trading window: 07:00-20:00 broker/server time
- Late-Friday entry cutoff: 16:00 broker/server time

These settings are research defaults, not a claim of profitability.

## Repository layout

- `mt5/PeakFX_EURUSD_H1.mq5` — MetaTrader 5 Expert Advisor
- `research/backtest_eurusd_h1.py` — matching Python research backtester
- `strategy/EURUSD_H1_SPEC.md` — precise strategy and validation rules
- `tests/test_backtest.py` — no-look-ahead and risk-model tests

## Python setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
pytest
```

Run a backtest with an H1 CSV containing `time,open,high,low,close`:

```bash
python -m research.backtest_eurusd_h1 data/EURUSD_H1.csv --output reports
```

The backtester enters at the next bar open after a completed-candle signal and applies configurable spread and slippage costs.

## MetaTrader 5 setup

1. Copy `mt5/PeakFX_EURUSD_H1.mq5` into `MQL5/Experts/PeakFX/`.
2. Compile it in MetaEditor.
3. Attach it to an EURUSD H1 chart in a demo account.
4. Leave `DemoOnly=true` during all initial testing.
5. Confirm the broker's server time before using the session inputs.
6. Run MT5 Strategy Tester before demo-forward testing.

## Safety status

Version 1 does not autonomously rewrite its strategy, use Claude during live execution, or store brokerage credentials. Claude may help review code and reports, but the EA makes deterministic decisions from fixed rules.

The current news filter is operationally documented but not yet connected to a calendar feed. Do not run the EA unattended through major EUR or USD releases until that guard is implemented and verified.
