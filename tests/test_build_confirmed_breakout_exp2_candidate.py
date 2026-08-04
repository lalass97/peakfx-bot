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

    assert "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5" in candidate
    assert "Version 1.45 - stronger confirmed-breakout experiment" in candidate
    assert '#property version   "1.45"' in candidate
    assert "trigger close must clear pullback extreme by 0.20 ATR" in candidate
    assert candidate.count("0.20*atr") == 2
    assert "26073025" in candidate
    assert "peakfx_confirmed_breakout_exp2_events.csv" in candidate

    assert "CONFIRMED_BREAKOUT_EXP1" not in candidate
    assert "Version 1.44" not in candidate
    assert "0.10 ATR" not in candidate
    assert "0.10*atr" not in candidate
    assert "26073024" not in candidate
    assert "peakfx_confirmed_breakout_exp1_events.csv" not in candidate


@pytest.mark.parametrize(
    "damaged_source",
    [
        SOURCE.replace("0.10*atr", "0.11*atr", 1),
        SOURCE.replace("PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP1.mq5", "wrong.mq5"),
        SOURCE.replace("Version 1.44 - confirmed-breakout experiment", "Version 1.44"),
        SOURCE.replace("26073024", "26073099"),
        SOURCE.replace("peakfx_confirmed_breakout_exp1_events.csv", "wrong.csv"),
    ],
)
def test_fails_closed_on_changed_source_markers(damaged_source: str) -> None:
    with pytest.raises(ValueError):
        build_confirmed_breakout_exp2(damaged_source)


def test_fails_closed_on_duplicate_identity_marker() -> None:
    duplicated = SOURCE + "// PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP1.mq5\n"
    with pytest.raises(ValueError):
        build_confirmed_breakout_exp2(duplicated)
