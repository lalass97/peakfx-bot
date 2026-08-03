from __future__ import annotations

import pytest

from research.build_confirmed_breakout_exp2_candidate import build_confirmed_breakout_exp2


SOURCE = '''//| PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP1.mq5 |
//| Version 1.44 - confirmed-breakout experiment |
#property version   "1.44"
#property description "Test 4 isolated experiment - trigger close must clear pullback extreme by 0.10 ATR."
input long             MagicNumber                  = 26073024;
input string           TelemetryFile                = "peakfx_confirmed_breakout_exp1_events.csv";
bool LongTriggerCondition(int shift) { return(c > g_setup.pullback_high + (0.10*atr)); }
bool ShortTriggerCondition(int shift) { return(c < g_setup.pullback_low - (0.10*atr)); }
'''


def test_builds_isolated_exp2() -> None:
    candidate = build_confirmed_breakout_exp2(SOURCE)
    assert '#property version   "1.45"' in candidate
    assert candidate.count("0.20*atr") == 2
    assert "0.10*atr" not in candidate
    assert "26073025" in candidate
    assert "peakfx_confirmed_breakout_exp2_events.csv" in candidate


def test_fails_closed_on_missing_direction_marker() -> None:
    with pytest.raises(ValueError):
        build_confirmed_breakout_exp2(SOURCE.replace("0.10*atr", "0.11*atr", 1))
