from __future__ import annotations

import argparse
from pathlib import Path

BASELINE_VERSION = '#property version   "1.42"'
CANDIDATE_VERSION = '#property version   "1.44"'
BASELINE_MAGIC = "input long             MagicNumber                  = 26073004;"
CANDIDATE_MAGIC = "input long             MagicNumber                  = 26073024;"
BASELINE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_pullback_events.csv";'
CANDIDATE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_confirmed_breakout_exp1_events.csv";'

BASELINE_TRIGGER_BLOCK = '''bool LongTriggerCondition(int shift)
  {
   if(!UptrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   return(c > g_setup.pullback_high);
  }

bool ShortTriggerCondition(int shift)
  {
   if(!DowntrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   return(c < g_setup.pullback_low);
  }
'''

CANDIDATE_TRIGGER_BLOCK = '''bool LongTriggerCondition(int shift)
  {
   if(!UptrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   if(!IsValidValue(atr) || atr<=0.0)
      return(false);
   return(c > g_setup.pullback_high + (0.10*atr));
  }

bool ShortTriggerCondition(int shift)
  {
   if(!DowntrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   if(!IsValidValue(atr) || atr<=0.0)
      return(false);
   return(c < g_setup.pullback_low - (0.10*atr));
  }
'''


def build_confirmed_breakout_candidate(source: str) -> str:
    required_once = (
        BASELINE_VERSION,
        BASELINE_MAGIC,
        BASELINE_TELEMETRY,
        BASELINE_TRIGGER_BLOCK,
    )
    for marker in required_once:
        count = source.count(marker)
        if count != 1:
            raise ValueError(f"expected exactly one baseline marker, found {count}")

    candidate = source
    candidate = candidate.replace(
        "//|                                  PeakFX_EURUSD_H1_PULLBACK.mq5   |",
        "//|               PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP1.mq5   |",
        1,
    )
    candidate = candidate.replace(
        "//|  Version 1.42                                                    |",
        "//|  Version 1.44 - confirmed-breakout experiment                    |",
        1,
    )
    candidate = candidate.replace(BASELINE_VERSION, CANDIDATE_VERSION, 1)
    candidate = candidate.replace(
        '#property description "Test 4 - trend + pullback + trigger entry. Frozen design, no optimization variables."',
        '#property description "Test 4 isolated experiment - trigger close must clear pullback extreme by 0.10 ATR."',
        1,
    )
    candidate = candidate.replace(BASELINE_MAGIC, CANDIDATE_MAGIC, 1)
    candidate = candidate.replace(BASELINE_TELEMETRY, CANDIDATE_TELEMETRY, 1)
    candidate = candidate.replace(BASELINE_TRIGGER_BLOCK, CANDIDATE_TRIGGER_BLOCK, 1)

    if candidate.count(CANDIDATE_VERSION) != 1:
        raise ValueError("candidate version validation failed")
    if candidate.count("0.10*atr") != 2:
        raise ValueError("confirmed-breakout margin was not applied to both directions")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build confirmed-breakout PeakFX MT5 candidate")
    parser.add_argument("baseline", help="Exact recovered v1.42 source")
    parser.add_argument("output", help="Destination .mq5 path")
    args = parser.parse_args(argv)

    source = Path(args.baseline).read_text(encoding="utf-8")
    candidate = build_confirmed_breakout_candidate(source)
    Path(args.output).write_text(candidate, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
