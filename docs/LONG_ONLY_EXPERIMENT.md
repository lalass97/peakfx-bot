# Controlled long-only experiment

The first strategy repair candidate changes exactly one behavior: short entries are rejected while qualifying long entries remain eligible.

## Frozen settings

The candidate must keep the baseline symbol, timeframe, indicators, signal timing, ATR stop, reward/risk, risk percentage, session, spread limit, cooldown, daily trade limit, Friday cutoff, margin rules, and safety locks unchanged.

## Required A/B evidence

Run the unchanged baseline and long-only candidate over the same declared historical period, broker data, modeling mode, deposit, leverage, spread, commission, slippage, and source version. Retain both complete reports and exports.

The candidate is not accepted merely because net profit improves. It must pass the existing profitability, open-equity, cost-stress, yearly-stability, out-of-sample, and sequence-risk gates. A smaller loss is still a failed strategy.

## Safety

This is a Strategy Tester and demo-only experiment. It does not authorize live trading. The stable baseline remains unchanged, and no other strategy setting may be altered in this experiment.
