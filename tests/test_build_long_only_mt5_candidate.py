import pytest

from research.build_long_only_mt5_candidate import build_long_only_candidate


def baseline_source() -> str:
    return '''//|                                  PeakFX_EURUSD_H1_PULLBACK.mq5   |
//|  Version 1.42                                                    |
#property version   "1.42"
#property description "Test 4 - trend + pullback + trigger entry. Frozen design, no optimization variables."
input long             MagicNumber                  = 26073004;
input string           TelemetryFile                = "peakfx_pullback_events.csv";
void ExecuteEntry(bool isLong)
  {
   if(isLong) trade.Buy(); else trade.Sell();
  }
void ProcessCompletedBar()
  {
   if(g_setup.state == STATE_NONE)
     {
      if(LongPullbackCondition(shift))
        {
         g_setup.state = STATE_LONG_PENDING;
        }
      else if(ShortPullbackCondition(shift))
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
  }
'''


def test_builder_blocks_short_setup_and_execution_paths():
    candidate = build_long_only_candidate(baseline_source())

    assert '#property version   "1.43"' in candidate
    assert "MagicNumber                  = 26073014" in candidate
    assert "peakfx_pullback_long_only_exp1_events.csv" in candidate
    assert "else if(ShortPullbackCondition(shift))" not in candidate
    assert "long_only_experiment_short_rejected" in candidate
    assert "STATE_SHORT_PENDING" in candidate
    assert "setup_discarded" in candidate


def test_builder_does_not_change_core_risk_parameters():
    source = baseline_source() + "\ninput double RiskPercent = 0.25;\ninput double ATRStopMultiplier = 1.5;\ninput double RewardRisk = 1.5;\n"
    candidate = build_long_only_candidate(source)

    for marker in (
        "RiskPercent = 0.25",
        "ATRStopMultiplier = 1.5",
        "RewardRisk = 1.5",
    ):
        assert marker in candidate


def test_builder_rejects_already_modified_or_unknown_source():
    with pytest.raises(ValueError, match="baseline marker"):
        build_long_only_candidate(baseline_source().replace('#property version   "1.42"', '#property version   "1.41"'))
