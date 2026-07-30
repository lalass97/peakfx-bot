#property strict
#property version   "1.20"
#property description "PeakFX EURUSD H1 trend-following EA - demo first"

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
input double MaxWeeklyLossPercent = 3.0;
input double MaxHighWaterDrawdownPercent = 5.0;
input int MaxTradesPerDay = 2;
input int MaxSpreadPoints = 25;
input int MaxDeviationPoints = 10;
input int StartHour = 7;
input int EndHour = 20;
input int FridayCutoffHour = 16;
input int CooldownBars = 2;
input bool DemoOnly = true;
input long MagicNumber = 26073001;
input bool EnableTelemetry = true;
input string TelemetryFolder = "PeakFX";
input string TelemetryFile = "peakfx_events.csv";
input int HeartbeatSeconds = 300;

int fastHandle = INVALID_HANDLE;
int slowHandle = INVALID_HANDLE;
int trendHandle = INVALID_HANDLE;
int atrHandle = INVALID_HANDLE;
datetime lastBarTime = 0;
datetime lastTradeBar = 0;
datetime dayAnchor = 0;
datetime weekAnchor = 0;
double dayStartEquity = 0.0;
double weekStartEquity = 0.0;
double equityHighWater = 0.0;
int tradesToday = 0;

string TelemetryPath()
{
   return TelemetryFolder + "\\" + TelemetryFile;
}

string UtcTimestamp()
{
   MqlDateTime value;
   TimeToStruct(TimeGMT(), value);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",
                       value.year, value.mon, value.day,
                       value.hour, value.min, value.sec);
}

string CleanTelemetryMessage(string message)
{
   StringReplace(message, "\r", " ");
   StringReplace(message, "\n", " ");
   return message;
}

void LogEvent(const string eventName, const ulong ticket = 0, const string message = "")
{
   if(!EnableTelemetry) return;

   FolderCreate(TelemetryFolder, FILE_COMMON);
   int handle = FileOpen(TelemetryPath(),
                         FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ,
                         ',');
   if(handle == INVALID_HANDLE)
   {
      Print("Telemetry open failed. Error=", GetLastError());
      ResetLastError();
      return;
   }

   if(FileSize(handle) == 0)
      FileWrite(handle, "time", "event", "symbol", "magic", "ticket", "message");

   FileSeek(handle, 0, SEEK_END);
   FileWrite(handle,
             UtcTimestamp(),
             eventName,
             InpSymbol,
             (string)MagicNumber,
             (string)ticket,
             CleanTelemetryMessage(message));
   FileFlush(handle);
   FileClose(handle);
}

string StateKey(const string suffix)
{
   return StringFormat("PeakFX.%I64d.%I64d.%s", AccountInfoInteger(ACCOUNT_LOGIN), MagicNumber, suffix);
}

void SaveState()
{
   GlobalVariableSet(StateKey("day_anchor"), (double)dayAnchor);
   GlobalVariableSet(StateKey("week_anchor"), (double)weekAnchor);
   GlobalVariableSet(StateKey("day_equity"), dayStartEquity);
   GlobalVariableSet(StateKey("week_equity"), weekStartEquity);
   GlobalVariableSet(StateKey("high_water"), equityHighWater);
   GlobalVariableSet(StateKey("last_trade_bar"), (double)lastTradeBar);
}

datetime StartOfDay(const datetime value)
{
   MqlDateTime t;
   TimeToStruct(value, t);
   return StringToTime(StringFormat("%04d.%02d.%02d 00:00", t.year, t.mon, t.day));
}

datetime StartOfWeek(const datetime value)
{
   datetime day = StartOfDay(value);
   MqlDateTime t;
   TimeToStruct(day, t);
   int daysFromMonday = (t.day_of_week == 0 ? 6 : t.day_of_week - 1);
   return day - daysFromMonday * 86400;
}

int CountTodayTrades()
{
   datetime from = StartOfDay(TimeCurrent());
   if(!HistorySelect(from, TimeCurrent())) return 0;
   int count = 0;
   for(int i = 0; i < HistoryDealsTotal(); i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != InpSymbol) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != MagicNumber) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_IN) count++;
   }
   return count;
}

void RestoreState()
{
   datetime now = TimeCurrent();
   datetime today = StartOfDay(now);
   datetime monday = StartOfWeek(now);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   dayAnchor = GlobalVariableCheck(StateKey("day_anchor")) ? (datetime)GlobalVariableGet(StateKey("day_anchor")) : today;
   weekAnchor = GlobalVariableCheck(StateKey("week_anchor")) ? (datetime)GlobalVariableGet(StateKey("week_anchor")) : monday;
   dayStartEquity = GlobalVariableCheck(StateKey("day_equity")) ? GlobalVariableGet(StateKey("day_equity")) : equity;
   weekStartEquity = GlobalVariableCheck(StateKey("week_equity")) ? GlobalVariableGet(StateKey("week_equity")) : equity;
   equityHighWater = GlobalVariableCheck(StateKey("high_water")) ? GlobalVariableGet(StateKey("high_water")) : equity;
   lastTradeBar = GlobalVariableCheck(StateKey("last_trade_bar")) ? (datetime)GlobalVariableGet(StateKey("last_trade_bar")) : 0;

   if(dayAnchor != today) { dayAnchor = today; dayStartEquity = equity; }
   if(weekAnchor != monday) { weekAnchor = monday; weekStartEquity = equity; }
   equityHighWater = MathMax(equityHighWater, equity);
   tradesToday = CountTodayTrades();
   SaveState();
}

void RefreshRiskState()
{
   datetime now = TimeCurrent();
   datetime today = StartOfDay(now);
   datetime monday = StartOfWeek(now);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   bool changed = false;

   if(today != dayAnchor)
   {
      dayAnchor = today;
      dayStartEquity = equity;
      tradesToday = CountTodayTrades();
      changed = true;
   }
   if(monday != weekAnchor)
   {
      weekAnchor = monday;
      weekStartEquity = equity;
      changed = true;
   }
   if(equity > equityHighWater)
   {
      equityHighWater = equity;
      changed = true;
   }
   if(changed) SaveState();
}

bool IsNewBar()
{
   datetime current = iTime(InpSymbol, InpTimeframe, 0);
   if(current == 0 || current == lastBarTime) return false;
   lastBarTime = current;
   return true;
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
   if(now.day_of_week == 5 && now.hour >= FridayCutoffHour) return false;
   return now.hour >= StartHour && now.hour < EndHour;
}

double LossPercent(const double anchor)
{
   if(anchor <= 0.0) return 100.0;
   return 100.0 * (anchor - AccountInfoDouble(ACCOUNT_EQUITY)) / anchor;
}

bool PortfolioRiskAllowsTrading()
{
   double dailyLoss = LossPercent(dayStartEquity);
   if(dailyLoss >= MaxDailyLossPercent)
   {
      LogEvent("daily_lock", 0, StringFormat("daily_loss_pct=%.3f", dailyLoss));
      Print("Blocked: daily loss limit reached.");
      return false;
   }

   double weeklyLoss = LossPercent(weekStartEquity);
   if(weeklyLoss >= MaxWeeklyLossPercent)
   {
      LogEvent("weekly_lock", 0, StringFormat("weekly_loss_pct=%.3f", weeklyLoss));
      Print("Blocked: weekly loss limit reached.");
      return false;
   }

   double highWaterLoss = LossPercent(equityHighWater);
   if(highWaterLoss >= MaxHighWaterDrawdownPercent)
   {
      LogEvent("drawdown_lock", 0, StringFormat("drawdown_pct=%.3f", highWaterLoss));
      Print("Blocked: equity drawdown circuit breaker reached.");
      return false;
   }
   return true;
}

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) == InpSymbol && (long)PositionGetInteger(POSITION_MAGIC) == MagicNumber) return true;
   }
   return false;
}

double CurrentSpreadPoints()
{
   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol, tick)) return -1.0;
   double point = SymbolInfoDouble(InpSymbol, SYMBOL_POINT);
   if(point <= 0.0) return -1.0;
   return (tick.ask - tick.bid) / point;
}

bool CooldownComplete()
{
   if(lastTradeBar == 0) return true;
   int shift = iBarShift(InpSymbol, InpTimeframe, lastTradeBar, false);
   return shift >= CooldownBars;
}

bool ReadIndicators(double &fast1, double &fast2, double &slow1, double &slow2,
                    double &trend1, double &trend6, double &atr1, double &close1)
{
   double fast[3], slow[3], trend[7], atr[3], closeBuf[3];
   ArraySetAsSeries(fast, true); ArraySetAsSeries(slow, true); ArraySetAsSeries(trend, true);
   ArraySetAsSeries(atr, true); ArraySetAsSeries(closeBuf, true);
   if(CopyBuffer(fastHandle, 0, 0, 3, fast) < 3) return false;
   if(CopyBuffer(slowHandle, 0, 0, 3, slow) < 3) return false;
   if(CopyBuffer(trendHandle, 0, 0, 7, trend) < 7) return false;
   if(CopyBuffer(atrHandle, 0, 0, 3, atr) < 3) return false;
   if(CopyClose(InpSymbol, InpTimeframe, 0, 3, closeBuf) < 3) return false;
   fast1 = fast[1]; fast2 = fast[2]; slow1 = slow[1]; slow2 = slow[2];
   trend1 = trend[1]; trend6 = trend[6]; atr1 = atr[1]; close1 = closeBuf[1];
   return atr1 > 0.0;
}

double NormalizeVolume(double volume)
{
   double minLot = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || volume < minLot) return 0.0;
   volume = MathMin(maxLot, MathFloor(volume / step) * step);
   int digits = (int)MathMax(0, MathRound(-MathLog10(step)));
   return NormalizeDouble(volume, digits);
}

double CalculateVolume(double stopDistance)
{
   if(stopDistance <= 0.0) return 0.0;
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * (RiskPercent / 100.0);
   double tickSize = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0.0) tickValue = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0) return 0.0;
   return NormalizeVolume(riskMoney / ((stopDistance / tickSize) * tickValue));
}

bool StopsValid(double entry, double sl, double tp)
{
   double point = SymbolInfoDouble(InpSymbol, SYMBOL_POINT);
   double minDistance = (double)SymbolInfoInteger(InpSymbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   return MathAbs(entry - sl) >= minDistance && MathAbs(tp - entry) >= minDistance;
}

bool MarginAvailable(const ENUM_ORDER_TYPE type, const double volume, const double price)
{
   double margin = 0.0;
   if(!OrderCalcMargin(type, InpSymbol, volume, price, margin)) return false;
   return margin <= AccountInfoDouble(ACCOUNT_MARGIN_FREE);
}

void EvaluateSignal()
{
   RefreshRiskState();

   if(DemoOnly && !IsDemoAccount())
   {
      LogEvent("risk_block", 0, "DemoOnly enabled on non-demo account");
      Print("Blocked: DemoOnly is enabled.");
      return;
   }

   if(!TradingWindowOpen())
   {
      LogEvent("session_block", 0, "outside configured trading window");
      return;
   }

   if(!PortfolioRiskAllowsTrading()) return;

   if(tradesToday >= MaxTradesPerDay)
   {
      LogEvent("risk_block", 0, "maximum daily trade count reached");
      return;
   }
   if(HasOpenPosition())
   {
      LogEvent("risk_block", 0, "PeakFX position already open");
      return;
   }

   double spreadPoints = CurrentSpreadPoints();
   if(spreadPoints < 0.0 || spreadPoints > MaxSpreadPoints)
   {
      LogEvent("spread_block", 0, StringFormat("spread_points=%.1f", spreadPoints));
      return;
   }

   if(!CooldownComplete())
   {
      LogEvent("cooldown_block", 0, "cooldown bars not complete");
      return;
   }

   double fast1, fast2, slow1, slow2, trend1, trend6, atr1, close1;
   if(!ReadIndicators(fast1, fast2, slow1, slow2, trend1, trend6, atr1, close1))
   {
      LogEvent("risk_block", 0, "indicator data unavailable");
      return;
   }

   bool longSignal = fast2 <= slow2 && fast1 > slow1 && close1 > trend1 && trend1 > trend6;
   bool shortSignal = fast2 >= slow2 && fast1 < slow1 && close1 < trend1 && trend1 < trend6;
   if(!longSignal && !shortSignal)
   {
      LogEvent("no_signal", 0, "closed H1 candle produced no qualifying crossover");
      return;
   }

   LogEvent(longSignal ? "signal_long" : "signal_short", 0,
            StringFormat("atr=%.5f spread_points=%.1f", atr1, spreadPoints));

   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol, tick))
   {
      LogEvent("order_rejected", 0, "symbol tick unavailable");
      return;
   }

   double stopDistance = atr1 * ATRStopMultiplier;
   double volume = CalculateVolume(stopDistance);
   if(volume <= 0.0)
   {
      LogEvent("volume_block", 0, "calculated volume below broker minimum or invalid");
      Print("Blocked: calculated volume is below broker minimum or invalid.");
      return;
   }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(MaxDeviationPoints);
   trade.SetTypeFillingBySymbol(InpSymbol);
   int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
   bool placed = false;
   double sl = 0.0;
   double tp = 0.0;
   ENUM_ORDER_TYPE orderType = longSignal ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double entry = longSignal ? tick.ask : tick.bid;

   if(longSignal)
   {
      sl = NormalizeDouble(tick.ask - stopDistance, digits);
      tp = NormalizeDouble(tick.ask + stopDistance * RewardRisk, digits);
   }
   else
   {
      sl = NormalizeDouble(tick.bid + stopDistance, digits);
      tp = NormalizeDouble(tick.bid - stopDistance * RewardRisk, digits);
   }

   if(!StopsValid(entry, sl, tp))
   {
      LogEvent("order_rejected", 0, "SL or TP violates broker minimum stop distance");
      return;
   }

   if(!MarginAvailable(orderType, volume, entry))
   {
      LogEvent("margin_block", 0, StringFormat("volume=%.2f", volume));
      return;
   }

   LogEvent("order_submitted", 0,
            StringFormat("side=%s volume=%.2f sl=%.5f tp=%.5f",
                         longSignal ? "buy" : "sell", volume, sl, tp));

   if(longSignal)
      placed = trade.Buy(volume, InpSymbol, 0.0, sl, tp, "PeakFX EURUSD H1 long");
   else
      placed = trade.Sell(volume, InpSymbol, 0.0, sl, tp, "PeakFX EURUSD H1 short");

   if(placed)
   {
      tradesToday = CountTodayTrades();
      lastTradeBar = iTime(InpSymbol, InpTimeframe, 0);
      SaveState();
      LogEvent("order_filled", trade.ResultDeal(),
               StringFormat("order=%I64u volume=%.2f result=%s",
                            trade.ResultOrder(), volume, trade.ResultRetcodeDescription()));
      Print("Trade placed. Volume=", volume, " Result=", trade.ResultRetcodeDescription());
   }
   else
   {
      LogEvent("order_rejected", trade.ResultOrder(),
               StringFormat("retcode=%u description=%s",
                            trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      Print("Trade rejected: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   }
}

int OnInit()
{
   if(InpSymbol != "EURUSD" || InpTimeframe != PERIOD_H1)
   {
      Print("This version is locked to EURUSD H1.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(RiskPercent <= 0.0 || RiskPercent > 0.5 || RewardRisk < 1.0) return INIT_PARAMETERS_INCORRECT;
   if(HeartbeatSeconds < 60) return INIT_PARAMETERS_INCORRECT;
   if(!SymbolSelect(InpSymbol, true)) return INIT_FAILED;

   fastHandle = iMA(InpSymbol, InpTimeframe, FastEMA, 0, MODE_EMA, PRICE_CLOSE);
   slowHandle = iMA(InpSymbol, InpTimeframe, SlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   trendHandle = iMA(InpSymbol, InpTimeframe, TrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   atrHandle = iATR(InpSymbol, InpTimeframe, ATRPeriod);
   if(fastHandle == INVALID_HANDLE || slowHandle == INVALID_HANDLE || trendHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
      return INIT_FAILED;

   RestoreState();
   lastBarTime = iTime(InpSymbol, InpTimeframe, 0);
   EventSetTimer(HeartbeatSeconds);
   LogEvent("startup", 0,
            StringFormat("version=1.20 demo_only=%s trades_today=%d equity=%.2f",
                         DemoOnly ? "true" : "false", tradesToday, AccountInfoDouble(ACCOUNT_EQUITY)));
   Print("PeakFX EURUSD H1 initialized. DemoOnly=", DemoOnly, " TradesToday=", tradesToday);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   LogEvent("shutdown", 0, StringFormat("reason=%d", reason));
   EventKillTimer();
   SaveState();
   if(fastHandle != INVALID_HANDLE) IndicatorRelease(fastHandle);
   if(slowHandle != INVALID_HANDLE) IndicatorRelease(slowHandle);
   if(trendHandle != INVALID_HANDLE) IndicatorRelease(trendHandle);
   if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
}

void OnTimer()
{
   RefreshRiskState();
   LogEvent("heartbeat", 0,
            StringFormat("equity=%.2f daily_loss_pct=%.3f weekly_loss_pct=%.3f trades_today=%d open_position=%s",
                         AccountInfoDouble(ACCOUNT_EQUITY),
                         LossPercent(dayStartEquity),
                         LossPercent(weekStartEquity),
                         tradesToday,
                         HasOpenPosition() ? "true" : "false"));
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != InpSymbol) return;
   if((long)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != MagicNumber) return;

   ENUM_DEAL_ENTRY entryType = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double volume = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
                 + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
                 + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);

   if(entryType == DEAL_ENTRY_IN || entryType == DEAL_ENTRY_INOUT)
      LogEvent("position_opened", trans.deal,
               StringFormat("price=%.5f volume=%.2f", price, volume));

   if(entryType == DEAL_ENTRY_OUT || entryType == DEAL_ENTRY_OUT_BY || entryType == DEAL_ENTRY_INOUT)
      LogEvent("position_closed", trans.deal,
               StringFormat("price=%.5f volume=%.2f net_profit=%.2f", price, volume, profit));
}

void OnTick()
{
   if(_Symbol != InpSymbol) return;
   RefreshRiskState();
   if(IsNewBar())
   {
      LogEvent("new_bar", 0, TimeToString(lastBarTime, TIME_DATE | TIME_MINUTES));
      EvaluateSignal();
   }
}
