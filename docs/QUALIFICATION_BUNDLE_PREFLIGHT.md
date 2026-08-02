# Qualification bundle preflight

A PeakFX result is not eligible for scoring until one immutable bundle passes all gates in order:

1. Validate the versioned run manifest with no hidden defaults.
2. Verify the exact SHA-256 fingerprints of both CSV exports.
3. Verify completed trades and open-equity snapshots describe the same run timeline.
4. Verify open-equity snapshots span the entire test period declared by the manifest.
5. Apply the combined profitability and open-risk qualification.

Any failure stops the run. The preflight does not sort, repair, truncate, optimize, or alter evidence.
