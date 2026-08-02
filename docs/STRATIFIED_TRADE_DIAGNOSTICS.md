# Stratified trade diagnostics

Before changing entry or exit rules, PeakFX must identify where realized losses are concentrated.

The diagnostic report splits the strict completed-trade export by:

- trade direction (`long` and `short`), and
- calendar year derived from `closed_at`.

For every segment it retains trade count, net profit, average trade, win rate, and profit factor. It also identifies the weakest direction and weakest year by net profit.

This report is diagnostic evidence only. A profitable historical subset does not authorize deleting the other subset. Any candidate restriction must be implemented as a separate experiment and retested chronologically with costs, untouched out-of-sample evidence, block-bootstrap sequence risk, and demo-forward validation.

The analyzer does not sort, repair, optimize, or silently discard malformed rows.