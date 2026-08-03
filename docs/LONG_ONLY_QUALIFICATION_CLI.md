# Long-only A/B qualification command

Validate one immutable evidence bundle and apply the predeclared long-only promotion gates:

```bash
python -m research.run_long_only_qualification \
  path/to/manifest.json \
  path/to/metrics.json \
  --output qualification.json
```

Exit codes:

- `0`: candidate meets every gate and may advance to further demo research.
- `2`: candidate is rejected by one or more measured gates.
- `3`: evidence is structurally valid but qualification is inconclusive.
- `4`: evidence or metrics are missing, malformed, changed, or incompatible.

The metrics document must contain exactly `baseline` and `candidate`. Each section must contain trade count, cost-inclusive net profit, profit factor, maximum drawdown fraction, profitable-year fraction, doubled-cost net profit, and sequence-risk decision.

The command validates evidence fingerprints before scoring. It does not run MT5, derive metrics from screenshots, repair exports, tune parameters, merge code, or authorize live trading.
