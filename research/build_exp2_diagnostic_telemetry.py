from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TELEMETRY_INPUT = 'input string           TelemetryFile                = "peakfx_confirmed_breakout_exp2_events.csv";'
TRADE_INPUT = 'input string           TradeTelemetryFile           = "peakfx_exp2_trade_deals.csv";'
ON_TRADE_MARKER = '//------------------------------------------------------------------+\n// Trade transaction handling - cooldown timestamp on close           |\n//------------------------------------------------------------------+\nvoid OnTradeTransaction'
CALL_MARKER = '   long entry = HistoryDealGetInteger(trans.deal,DEAL_ENTRY);\n'

LOGGER = r'''
//------------------------------------------------------------------+
// Logging-only per-deal diagnostic telemetry                        |
//------------------------------------------------------------------+
void LogTradeDeal(const ulong deal)
  {
   if(!EnableTelemetry)
      return;

   string path = TelemetryFolder+"\\"+TradeTelemetryFile;
   int handle = FileOpen(path,FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_CSV|FILE_ANSI,',');
   if(handle==INVALID_HANDLE)
     {
      handle = FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
      if(handle==INVALID_HANDLE)
         return;
     }

   bool empty = (FileSize(handle)==0);
   FileSeek(handle,0,SEEK_END);
   if(empty)
      FileWrite(handle,
                "deal_time","deal_ticket","position_id","deal_entry","deal_type","deal_reason",
                "price","volume","profit","commission","swap","fee",
                "setup_state","pullback_time","pullback_high","pullback_low","setup_bar_index",
                "ema_fast","ema_slow","ema_trend","atr","bar_open","bar_high","bar_low","bar_close",
                "ema_fast_slow_atr","ema_slow_trend_atr","pullback_range_atr","trigger_clearance_atr");

   datetime dealTime = (datetime)HistoryDealGetInteger(deal,DEAL_TIME);
   long entryType = HistoryDealGetInteger(deal,DEAL_ENTRY);
   long dealType = HistoryDealGetInteger(deal,DEAL_TYPE);
   long dealReason = HistoryDealGetInteger(deal,DEAL_REASON);
   ulong positionId = (ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   double emaFast = GetIndicatorValue(hEmaFast,1);
   double emaSlow = GetIndicatorValue(hEmaSlow,1);
   double emaTrend = GetIndicatorValue(hEmaTrend,1);
   double atr = GetIndicatorValue(hAtr,1);
   double o = iOpen(InpSymbol,InpTimeframe,1);
   double h = iHigh(InpSymbol,InpTimeframe,1);
   double l = iLow(InpSymbol,InpTimeframe,1);
   double c = iClose(InpSymbol,InpTimeframe,1);
   double fastSlowAtr = (atr>0.0 ? (emaFast-emaSlow)/atr : 0.0);
   double slowTrendAtr = (atr>0.0 ? (emaSlow-emaTrend)/atr : 0.0);
   double pullbackRangeAtr = (atr>0.0 ? (g_setup.pullback_high-g_setup.pullback_low)/atr : 0.0);
   double triggerClearanceAtr = 0.0;
   if(atr>0.0)
     {
      if(dealType==DEAL_TYPE_BUY)
         triggerClearanceAtr=(c-g_setup.pullback_high)/atr;
      else if(dealType==DEAL_TYPE_SELL)
         triggerClearanceAtr=(g_setup.pullback_low-c)/atr;
     }

   FileWrite(handle,
             TimeToString(dealTime,TIME_DATE|TIME_SECONDS),
             (string)deal,
             (string)positionId,
             EnumToString((ENUM_DEAL_ENTRY)entryType),
             EnumToString((ENUM_DEAL_TYPE)dealType),
             EnumToString((ENUM_DEAL_REASON)dealReason),
             DoubleToString(HistoryDealGetDouble(deal,DEAL_PRICE),5),
             DoubleToString(HistoryDealGetDouble(deal,DEAL_VOLUME),2),
             DoubleToString(HistoryDealGetDouble(deal,DEAL_PROFIT),2),
             DoubleToString(HistoryDealGetDouble(deal,DEAL_COMMISSION),2),
             DoubleToString(HistoryDealGetDouble(deal,DEAL_SWAP),2),
             DoubleToString(HistoryDealGetDouble(deal,DEAL_FEE),2),
             EnumToString(g_setup.state),
             TimeToString(g_setup.pullback_time,TIME_DATE|TIME_SECONDS),
             DoubleToString(g_setup.pullback_high,5),
             DoubleToString(g_setup.pullback_low,5),
             IntegerToString(g_setup.bar_index),
             DoubleToString(emaFast,5),DoubleToString(emaSlow,5),DoubleToString(emaTrend,5),DoubleToString(atr,5),
             DoubleToString(o,5),DoubleToString(h,5),DoubleToString(l,5),DoubleToString(c,5),
             DoubleToString(fastSlowAtr,5),DoubleToString(slowTrendAtr,5),
             DoubleToString(pullbackRangeAtr,5),DoubleToString(triggerClearanceAtr,5));
   FileClose(handle);
  }

'''


def build(source: str) -> str:
    if source.count(TELEMETRY_INPUT) != 1:
        raise ValueError("authoritative EXP2 telemetry input marker missing or ambiguous")
    if TRADE_INPUT in source:
        raise ValueError("trade telemetry input already present")
    out = source.replace(TELEMETRY_INPUT, TELEMETRY_INPUT + "\n" + TRADE_INPUT, 1)
    if out.count(ON_TRADE_MARKER) != 1:
        raise ValueError("OnTradeTransaction marker missing or ambiguous")
    out = out.replace(ON_TRADE_MARKER, LOGGER + ON_TRADE_MARKER, 1)
    if out.count(CALL_MARKER) != 1:
        raise ValueError("deal-entry marker missing or ambiguous")
    out = out.replace(CALL_MARKER, "   LogTradeDeal(trans.deal);\n\n" + CALL_MARKER, 1)
    # Trading logic invariants: logging build must retain the exact EXP2 hypothesis.
    required = (
        "26073025",
        "c > g_setup.pullback_high + (0.20*atr)",
        "c < g_setup.pullback_low - (0.20*atr)",
        "RiskPercent                  = 0.25",
        "RewardRisk                   = 1.5",
    )
    for marker in required:
        if marker not in out:
            raise ValueError(f"trading invariant missing after telemetry injection: {marker}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inject logging-only telemetry into authoritative EXP2")
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    try:
        source_path = Path(args.source)
        output_path = Path(args.output)
        text = source_path.read_text(encoding="utf-8-sig")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(build(text), encoding="utf-8", newline="\n")
        print(f"EXP2 diagnostic telemetry source written: {output_path}")
        return 0
    except Exception as exc:
        print(f"EXP2_TELEMETRY_BUILDER_ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
