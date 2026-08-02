# Long-only A/B evidence bundle

A long-only candidate cannot be scored from screenshots, copied totals, or manually edited CSV files. One immutable evidence bundle must be supplied for the unchanged baseline and the candidate.

## Required files

- Baseline MT5 Strategy Tester report.
- Candidate MT5 Strategy Tester report.
- Baseline completed-trade export.
- Candidate completed-trade export.
- Candidate open-equity snapshot export.

Every file must be fingerprinted with SHA-256 before qualification. Any changed byte invalidates the bundle.

## Required comparable settings

Both Strategy Tester runs must use EURUSD H1, the same test dates, initial deposit, leverage, broker data, real-tick modeling, risk, stop, target, session, spread assumptions, slippage assumptions, and safety settings. The only intended strategy difference is that the candidate blocks short entries.

A doubled-cost candidate result is mandatory. The candidate is not eligible for promotion when its tested cost stress is below 2.0x.

## Decision discipline

Validation does not make the candidate profitable. It only proves that the evidence being scored is complete, immutable, and suitable for a fair A/B comparison. Missing files, duplicate paths, changed fingerprints, inconsistent metadata, or weaker modeling fail closed.
