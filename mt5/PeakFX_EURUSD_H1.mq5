#property strict
#property version   "1.00"
#property description "PeakFX EURUSD H1 trend-following EA - paper/demo first"

#include <Trade/Trade.mqh>
CTrade trade;

input string InpSymbol = "EURUSD";
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_H1;
input int FastEMA = 12;
input int SlowEMA = 50;
input int TrendEMA = 200;
input int ATRPeriod = 14;
input double ATRStopMultiplier = 1.5;
input double RewardRisk = 1.5;
input double RiskPercent = 0.25;
input double MaxDailyLossPercent = 1.5;
input int MaxTradesPerDay = 2;
input int MaxSpreadPoints = 25;
input int StartHour = 7;
input int EndHour = 20;
input int CooldownBars = 2;
input bool DemoOnly = true;
input long MagicNumber = 26073001;

int fastHandle = INVALID_HANDLE;
int slowHandle = INVALID_HANDLE;
int trendHandle = INVALID_HANDLE;
int atrHandle = INVALID_HANDLE;
datetime lastBarTime = 0;
datetime lastTradeBar = 0;
datetime dayAnchor = 0;
double dayStartEquity = 0.0;
int tradesToday = 0;

bool IsNewBar()
{
   datetime current = iTime(InpSymbol, InpTimeframe, 0);
   if(current == 0 || current == lastBarTime) return false;
   lastBarTime = current;
   return true;
}

void ResetDailyState()
{
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d 00:00", now.year, now.mon, now.day));
   if(today != dayAnchor)
   {
      dayAnchor = today;
      dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      tradesToday = 0;
   }
}

bool IsDemoAccount()
{
   return (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO;
}

bool TradingWindowOpen()
{
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   if(now.day_of_week == 0 || now.day_of_week == 6) return false;
   if(now.day_of_week == 5 && now.hour >= 16) return false;
   return now.hour >= StartHour && now.hour < EndHour;
}

bool DailyRiskAllowsTrading()
{
   if(dayStartEquity <= 0.0) return false;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double lossPct = 100.0 * (dayStartEquity - equity) / dayStartEquity;
   return lossPct < MaxDailyLossPercent;
}

bool HasOpenPosition()
{
   if(!PositionSelect(InpSymbol)) return false;
   return (long)PositionGetInteger(POSITION_MAGIC) == MagicNumber;
}

bool SpreadAcceptable()
{
   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol, tick)) return false;
   double points = (tick.ask - tick.bid) / SymbolInfoDouble(InpSymbol, SYMBOL_POINT);
   return points <= MaxSpreadPoints;
}

bool CooldownComplete()
{
   if(lastTradeBar == 0) return true;
   int shift = iBarShift(InpSymbol, InpTimeframe, lastTradeBar, true);
   return shift >= CooldownBars;
}

bool ReadIndicators(double &fast1, double &fast2, double &slow1, double &slow2,
                    double &trend1, double &trend6, double &atr1, double &close1)
{
   double fast[3], slow[3], trend[7], atr[3], closeBuf[3];
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);
   ArraySetAsSeries(trend, true);
   ArraySetAsSeries(atr, true);
   ArraySetAsSeries(closeBuf, true);

   if(CopyBuffer(fastHandle, 0, 0, 3, fast) < 3) return false;
   if(CopyBuffer(slowHandle, 0, 0, 3, slow) < 3) return false;
   if(CopyBuffer(trendHandle, 0, 0, 7, trend) < 7) return false;
   if(CopyBuffer(atrHandle, 0, 0, 3, atr) < 3) return false;
   if(CopyClose(InpSymbol, InpTimeframe, 0, 3, closeBuf) < 3) return false;

   fast1 = fast[1]; fast2 = fast[2];
   slow1 = slow[1]; slow2 = slow[2];
   trend1 = trend[1]; trend6 = trend[6];
   atr1 = atr[1]; close1 = closeBuf[1];
   return atr1 > 0.0;
}

double NormalizeVolume(double volume)
{
   double minLot = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_STEP);
   volume = MathMax(minLot, MathMin(maxLot, volume));
   volume = MathFloor(volume / step) * step;
   return NormalizeDouble(volume, 2);
}

double CalculateVolume(double stopDistance)
{
   if(stopDistance <= 0.0) return 0.0;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * (RiskPercent / 100.0);
   double tickSize = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0) return 0.0;
   double lossPerLot = (stopDistance / tickSize) * tickValue;
   if(lossPerLot <= 0.0) return 0.0;
   return NormalizeVolume(riskMoney / lossPerLot);
}

bool StopsValid(double entry, double sl, double tp)
{
   double point = SymbolInfoDouble(InpSymbol, SYMBOL_POINT);
   int stopsLevel = (int)SymbolInfoInteger(InpSymbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDistance = stopsLevel * point;
   return MathAbs(entry - sl) >= minDistance && MathAbs(tp - entry) >= minDistance;
}

void EvaluateSignal()
{
   ResetDailyState();
   if(DemoOnly && !IsDemoAccount()) { Print("Blocked: DemoOnly is enabled."); return; }
   if(!TradingWindowOpen()) return;
   if(!DailyRiskAllowsTrading()) { Print("Blocked: daily loss limit reached."); return; }
   if(tradesToday >= MaxTradesPerDay) return;
   if(HasOpenPosition()) return;
   if(!SpreadAcceptable()) return;
   if(!CooldownComplete()) return;

   double fast1, fast2, slow1, slow2, trend1, trend6, atr1, close1;
   if(!ReadIndicators(fast1, fast2, slow1, slow2, trend1, trend6, atr1, close1)) return;

   bool longSignal = fast2 <= slow2 && fast1 > slow1 && close1 > trend1 && trend1 > trend6;
   bool shortSignal = fast2 >= slow2 && fast1 < slow1 && close1 < trend1 && trend1 < trend6;
   if(!longSignal && !shortSignal) return;

   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol, tick)) return;
   double stopDistance = atr1 * ATRStopMultiplier;
   double volume = CalculateVolume(stopDistance);
   if(volume <= 0.0) return;

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFillingBySymbol(InpSymbol);

   bool placed = false;
   if(longSignal)
   {
      double entry = tick.ask;
      double sl = NormalizeDouble(entry - stopDistance, (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS));
      double tp = NormalizeDouble(entry + stopDistance * RewardRisk, (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS));
      if(StopsValid(entry, sl, tp)) placed = trade.Buy(volume, InpSymbol, 0.0, sl, tp, "PeakFX EURUSD H1 long");
   }
   else if(shortSignal)
   {
      double entry = tick.bid;
      double sl = NormalizeDouble(entry + stopDistance, (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS));
      double tp = NormalizeDouble(entry - stopDistance * RewardRisk, (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS));
      if(StopsValid(entry, sl, tp)) placed = trade.Sell(volume, InpSymbol, 0.0, sl, tp, "PeakFX EURUSD H1 short");
   }

   if(placed)
   {
      tradesToday++;
      lastTradeBar = iTime(InpSymbol, InpTimeframe, 0);
      Print("Trade placed. Volume=", volume, " Result=", trade.ResultRetcodeDescription());
   }
   else
   {
      Print("Trade rejected: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   }
}

int OnInit()
{
   if(!SymbolSelect(InpSymbol, true)) return INIT_FAILED;
   fastHandle = iMA(InpSymbol, InpTimeframe, FastEMA, 0, MODE_EMA, PRICE_CLOSE);
   slowHandle = iMA(InpSymbol, InpTimeframe, SlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   trendHandle = iMA(InpSymbol, InpTimeframe, TrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   atrHandle = iATR(InpSymbol, InpTimeframe, ATRPeriod);
   if(fastHandle == INVALID_HANDLE || slowHandle == INVALID_HANDLE || trendHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
      return INIT_FAILED;
   ResetDailyState();
   Print("PeakFX EURUSD H1 initialized. DemoOnly=", DemoOnly);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(fastHandle != INVALID_HANDLE) IndicatorRelease(fastHandle);
   if(slowHandle != INVALID_HANDLE) IndicatorRelease(slowHandle);
   if(trendHandle != INVALID_HANDLE) IndicatorRelease(trendHandle);
   if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
}

void OnTick()
{
   if(_Symbol != InpSymbol) return;
   if(IsNewBar()) EvaluateSignal();
}
