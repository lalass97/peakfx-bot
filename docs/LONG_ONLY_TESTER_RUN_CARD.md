# Long-only MT5 Strategy Tester run card

Run two separate tests and preserve both reports before changing any setting.

## Run A — unchanged baseline

- Strategy ID: `PeakFX_pullback_baseline_v142`
- Direction mode: both
- Symbol: EURUSD
- Timeframe: H1
- Modeling: Every tick based on real ticks
- Period: 2016-01-01 through 2025-07-31
- Initial deposit: 10,000 USD
- Leverage: 1:100
- Risk per trade: 0.25%
- ATR stop multiplier: 1.5
- Reward/risk: 1.5
- Session: 07:00–20:00 broker time
- Friday cutoff: 16:00 broker time
- Maximum trades per day: 2
- Demo/tester only: enabled

## Run B — long-only candidate

Use every Run A setting unchanged. The sole intended difference is:

- Strategy ID: `PeakFX_pullback_long_only_exp1`
- Direction mode: long only

## Required exports

Save both HTML Strategy Tester reports. Export completed trades for both runs and open-equity snapshots for the candidate. Record SHA-256 fingerprints before analysis.

Repeat the candidate under doubled trading costs. Do not tune settings after viewing the first candidate result. A failed candidate is evidence, not permission to change several variables at once.
