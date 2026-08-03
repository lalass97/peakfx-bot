# MT5 compile evidence gate

The isolated long-only candidate must not enter Strategy Tester qualification until MetaEditor has compiled the exact downloaded source with **0 errors and 0 warnings**.

## Required evidence

1. Source file: `PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5`.
2. SHA-256 fingerprint of that source before compilation.
3. MetaEditor compiler output identifying that exact filename.
4. Compiler output explicitly showing `0 errors, 0 warnings`.
5. SHA-256 fingerprint of the saved compiler log.

The validator checks the immutable fingerprints, filename, version `1.43`, execution-level short-entry guard, and clean compiler result. It does not compile MQL5 itself and does not authorize live trading.

## Local procedure

1. In MT5 select **File → Open Data Folder**.
2. Open `MQL5\Experts` and copy the candidate `.mq5` file there.
3. Open MetaEditor with **F4**.
4. Open the candidate and press **F7**.
5. Confirm the Toolbox **Errors** tab reports `0 errors, 0 warnings`.
6. Save or copy the compiler output before changing the source.

Only after this evidence is preserved should the EURUSD H1 real-tick Strategy Tester run begin.
