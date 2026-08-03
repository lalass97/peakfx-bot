from __future__ import annotations

import argparse
from pathlib import Path


BASELINE_VERSION = '#property version   "1.42"'
CANDIDATE_VERSION = '#property version   "1.43"'
BASELINE_MAGIC = "input long             MagicNumber                  = 26073004;"
CANDIDATE_MAGIC = "input long             MagicNumber                  = 26073014;"
BASELINE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_pullback_events.csv";'
CANDIDATE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_pullback_long_only_exp1_events.csv";'


def build_long_only_candidate(source: str) -> str:
    """Create one isolated long-only candidate from the exact v1.42 source.

    The transformation fails closed unless every expected baseline marker occurs
    exactly once. It does not alter stops, targets, risk, hours, expiry, or exits.
    """
    required_once = (
        BASELINE_VERSION,
        BASELINE_MAGIC,
        BASELINE_TELEMETRY,
        "void ExecuteEntry(bool isLong)\n  {\n",
        "else if(ShortPullbackCondition(shift))",
        "bool isLongSetup = (g_setup.state == STATE_LONG_PENDING);",
    )
    for marker in required_once:
        count = source.count(marker)
        if count != 1:
            raise ValueError(f"expected exactly one baseline marker, found {count}: {marker}")

    candidate = source
    candidate = candidate.replace(
        "//|                                  PeakFX_EURUSD_H1_PULLBACK.mq5   |",
        "//|                    PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5   |",
        1,
    )
    candidate = candidate.replace(
        "//|  Version 1.42                                                    |",
        "//|  Version 1.43 - isolated long-only experiment                    |",
        1,
    )
    candidate = candidate.replace(BASELINE_VERSION, CANDIDATE_VERSION, 1)
    candidate = candidate.replace(
        '#property description "Test 4 - trend + pullback + trigger entry. Frozen design, no optimization variables."',
        '#property description "Test 4 isolated experiment - unchanged pullback model with short entries blocked."',
        1,
    )
    candidate = candidate.replace(BASELINE_MAGIC, CANDIDATE_MAGIC, 1)
    candidate = candidate.replace(BASELINE_TELEMETRY, CANDIDATE_TELEMETRY, 1)

    candidate = candidate.replace(
        "void ExecuteEntry(bool isLong)\n  {\n",
        "void ExecuteEntry(bool isLong)\n  {\n"
        "   // Experiment invariant: this standalone candidate must never send short entries.\n"
        "   if(!isLong)\n"
        "     {\n"
        "      LogEvent(\"entry_blocked\",\"long_only_experiment_short_rejected\");\n"
        "      return;\n"
        "     }\n\n",
        1,
    )

    short_setup_block = '''      else if(ShortPullbackCondition(shift))
        {
         g_setup.state = STATE_SHORT_PENDING;
         g_setup.pullback_high = iHigh(InpSymbol,InpTimeframe,shift);
         g_setup.pullback_low  = iLow(InpSymbol,InpTimeframe,shift);
         g_setup.pullback_time = iTime(InpSymbol,InpTimeframe,shift);
         g_setup.bar_index = 0;
         LogEvent("pullback_new","short");
        }
      return;
     }

   bool isLongSetup = (g_setup.state == STATE_LONG_PENDING);
'''
    long_only_block = '''      // Short pullbacks are intentionally ignored in this isolated experiment.
      return;
     }

   // Fail closed if a stale or corrupted persisted state ever presents a short setup.
   if(g_setup.state == STATE_SHORT_PENDING)
     {
      LogEvent("setup_discarded","long_only_experiment_short_state");
      g_setup.state = STATE_NONE;
      g_setup.bar_index = 0;
      return;
     }

   bool isLongSetup = true;
'''
    if candidate.count(short_setup_block) != 1:
        raise ValueError("exact v1.42 short-setup block was not found")
    candidate = candidate.replace(short_setup_block, long_only_block, 1)

    if candidate.count(CANDIDATE_VERSION) != 1:
        raise ValueError("candidate version marker validation failed")
    if "else if(ShortPullbackCondition(shift))" in candidate:
        raise ValueError("short setup creation remains reachable")
    if "long_only_experiment_short_rejected" not in candidate:
        raise ValueError("execution-level short guard is missing")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the isolated PeakFX long-only MT5 candidate")
    parser.add_argument("baseline", help="Exact v1.42 .mq5 source path")
    parser.add_argument("output", help="Destination .mq5 path")
    args = parser.parse_args(argv)

    source = Path(args.baseline).read_text(encoding="utf-8")
    candidate = build_long_only_candidate(source)
    Path(args.output).write_text(candidate, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
