# Long-only evidence-bundle validation command

Validate the immutable A/B evidence bundle before any profitability or promotion scoring:

```bash
python -m research.run_long_only_bundle_validation path/to/manifest.json --output validation.json
```

Exit codes:

- `0`: bundle is complete, immutable, and structurally valid.
- `4`: missing, malformed, changed, duplicated, or incomparable evidence.

A valid result does not mean the long-only candidate is profitable. It only permits the separate A/B qualification stage to examine the evidence. The command never edits evidence, guesses missing fields, sorts exports, runs MT5, or enables live trading.
