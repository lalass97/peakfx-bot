from pathlib import Path

import pytest

from research.build_confirmed_breakout_mt5_candidate import (
    build_confirmed_breakout_candidate,
)


SOURCE = Path('/mnt/data/does-not-exist')


def _baseline_fixture() -> str:
    return '''//|                                  PeakFX_EURUSD_H1_PULLBACK.mq5   |
//|  Version 1.42                                                    |
#property version   "1.42"
#property description "Test 4 - trend + pullback + trigger entry. Frozen design, no optimization variables."
input long             MagicNumber                  = 26073004;
input string           TelemetryFile                = "peakfx_pullback_events.csv";
bool LongTriggerCondition(int shift)
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


def test_builds_isolated_confirmed_breakout_candidate():
    candidate = build_confirmed_breakout_candidate(_baseline_fixture())

    assert '#property version   "1.44"' in candidate
    assert 'MagicNumber                  = 26073024;' in candidate
    assert 'peakfx_confirmed_breakout_exp1_events.csv' in candidate
    assert candidate.count('0.10*atr') == 2
    assert 'return(c > g_setup.pullback_high);' not in candidate
    assert 'return(c < g_setup.pullback_low);' not in candidate


def test_invalid_or_changed_source_fails_closed():
    with pytest.raises(ValueError):
        build_confirmed_breakout_candidate(_baseline_fixture().replace('26073004', '999'))


def test_duplicate_trigger_block_fails_closed():
    source = _baseline_fixture()
    trigger_start = source.index('bool LongTriggerCondition')
    duplicate = source[trigger_start:]
    with pytest.raises(ValueError):
        build_confirmed_breakout_candidate(source + duplicate)
