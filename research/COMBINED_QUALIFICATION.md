# Combined qualification gate

A PeakFX research run is eligible for a green decision only when both independent sections pass:

1. Completed, cost-inclusive trade results pass the profitability gates.
2. Ordered mark-to-market snapshots pass the open-equity risk gates.

Decision precedence is deliberately fail-closed:

- Any red section makes the combined decision red.
- Both sections must be green for the combined decision to be green.
- Otherwise the combined decision is inconclusive.

The runner does not sort, repair, optimize, or alter either input stream. Malformed exports are rejected before scoring.
