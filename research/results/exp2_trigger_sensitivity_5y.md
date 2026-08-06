# EXP2 Trigger-Clearance Sensitivity — Five-Year In-Sample Result

## Protocol

- Source: verified EXP2 diagnostic telemetry artifact
- Trades reconstructed: 465
- Baseline net: +$552.44
- Parameter grid fixed before evaluation:
  - Lower bounds: 0.45, 0.50, 0.55, 0.5667, 0.60, 0.65 ATR
  - Upper bounds: 0.85, 0.90, 0.933, 0.95, 1.00, 1.05 ATR
- Candidate action: reject entries whose trigger clearance falls inside the tested interval
- Reserved OOS: locked and untouched

## Best candidate passing the three-tier stability screen

Reject trigger clearance from **0.5667 through 0.85 ATR**, inclusive.

| Metric | Result |
|---|---:|
| Trades retained | 369 |
| Trades filtered | 96 |
| Five-year net | +$888.93 |
| 2021–2022 net | -$198.28 |
| 2021–2022 loss reduction | 59.11% |
| 2022–2023 retention | 97.94% |
| 2024–2025 retention | 116.92% |
| Profitable years | 4 of 5 |
| Retrospective trade-level PF | 1.17335 |
| Retrospective max consecutive losses | 9 |

Yearly net:

- 2020–2021: +$198.22
- 2021–2022: -$198.28
- 2022–2023: +$524.53
- 2023–2024: +$79.87
- 2024–2025: +$284.59

## Gate decision

The candidate passes the preliminary three-tier stability screen:

1. Cuts the 2021–2022 loss by at least 50%.
2. Preserves at least 80% of both benchmark profitable years.
3. Retains at least 100 trades.

It does **not** project to pass the formal robustness gate from the reconstructed trades:

- Profit factor is approximately 1.17, below 1.25.
- Maximum consecutive losses are 9, above 8.

No tested interval passed every formal requirement. Therefore EXP7 is **not yet authorized for OOS**. A genuine MT5 EXP7 batch may be used only to confirm execution fidelity of this single frozen rule; it must not be presented as a passing strategy unless its native MT5 reports satisfy all gates. OOS remains strictly locked.
