#property strict
#property version   "1.40"
#property description "PeakFX EURUSD H1 with ADX and EMA separation filters - demo only"

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
input int ADXPeriod = 14;
input double MinADX = 22.0;
input double MinEMASeparationATR = 0.05;
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
input long MagicNumber = 26073003;
input bool EnableTelemetry = true;
input string TelemetryFolder = "PeakFX";
input string TelemetryFile = "peakfx_adx_emasep_events.csv";
input int HeartbeatSeconds = 300;

int fastHandle=INVALID_HANDLE, slowHandle=INVALID_HANDLE, trendHandle=INVALID_HANDLE;
int atrHandle=INVALID_HANDLE, adxHandle=INVALID_HANDLE;
datetime lastBarTime=0, lastTradeBar=0, dayAnchor=0, weekAnchor=0;
double dayStartEquity=0.0, weekStartEquity=0.0, equityHighWater=0.0;
int tradesToday=0;

string TelemetryPath(){ return TelemetryFolder+"\\"+TelemetryFile; }
string UtcTimestamp(){ MqlDateTime v; TimeToStruct(TimeGMT(),v); return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",v.year,v.mon,v.day,v.hour,v.min,v.sec); }
string CleanTelemetryMessage(string m){ StringReplace(m,"\r"," "); StringReplace(m,"\n"," "); return m; }
void LogEvent(const string e,const ulong ticket=0,const string m=""){
   if(!EnableTelemetry) return;
   FolderCreate(TelemetryFolder,FILE_COMMON);
   int h=FileOpen(TelemetryPath(),FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
   if(h==INVALID_HANDLE){ Print("Telemetry open failed. Error=",GetLastError()); ResetLastError(); return; }
   if(FileSize(h)==0) FileWrite(h,"time","event","symbol","magic","ticket","message");
   FileSeek(h,0,SEEK_END); FileWrite(h,UtcTimestamp(),e,InpSymbol,(string)MagicNumber,(string)ticket,CleanTelemetryMessage(m)); FileFlush(h); FileClose(h);
}
string StateKey(const string s){ return StringFormat("PeakFX.%I64d.%I64d.%s",AccountInfoInteger(ACCOUNT_LOGIN),MagicNumber,s); }
void SaveState(){
   GlobalVariableSet(StateKey("day_anchor"),(double)dayAnchor); GlobalVariableSet(StateKey("week_anchor"),(double)weekAnchor);
   GlobalVariableSet(StateKey("day_equity"),dayStartEquity); GlobalVariableSet(StateKey("week_equity"),weekStartEquity);
   GlobalVariableSet(StateKey("high_water"),equityHighWater); GlobalVariableSet(StateKey("last_trade_bar"),(double)lastTradeBar);
}
datetime StartOfDay(const datetime x){ MqlDateTime t; TimeToStruct(x,t); return StringToTime(StringFormat("%04d.%02d.%02d 00:00",t.year,t.mon,t.day)); }
datetime StartOfWeek(const datetime x){ datetime d=StartOfDay(x); MqlDateTime t; TimeToStruct(d,t); int n=(t.day_of_week==0?6:t.day_of_week-1); return d-n*86400; }
int CountTodayTrades(){
   datetime from=StartOfDay(TimeCurrent()); if(!HistorySelect(from,TimeCurrent())) return 0; int count=0;
   for(int i=0;i<HistoryDealsTotal();i++){ ulong ticket=HistoryDealGetTicket(i); if(ticket==0) continue;
      if(HistoryDealGetString(ticket,DEAL_SYMBOL)!=InpSymbol) continue;
      if((long)HistoryDealGetInteger(ticket,DEAL_MAGIC)!=MagicNumber) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket,DEAL_ENTRY)==DEAL_ENTRY_IN) count++; }
   return count;
}
void RestoreState(){
   datetime now=TimeCurrent(), today=StartOfDay(now), monday=StartOfWeek(now); double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   dayAnchor=GlobalVariableCheck(StateKey("day_anchor"))?(datetime)GlobalVariableGet(StateKey("day_anchor")):today;
   weekAnchor=GlobalVariableCheck(StateKey("week_anchor"))?(datetime)GlobalVariableGet(StateKey("week_anchor")):monday;
   dayStartEquity=GlobalVariableCheck(StateKey("day_equity"))?GlobalVariableGet(StateKey("day_equity")):eq;
   weekStartEquity=GlobalVariableCheck(StateKey("week_equity"))?GlobalVariableGet(StateKey("week_equity")):eq;
   equityHighWater=GlobalVariableCheck(StateKey("high_water"))?GlobalVariableGet(StateKey("high_water")):eq;
   lastTradeBar=GlobalVariableCheck(StateKey("last_trade_bar"))?(datetime)GlobalVariableGet(StateKey("last_trade_bar")):0;
   if(dayAnchor!=today){ dayAnchor=today; dayStartEquity=eq; } if(weekAnchor!=monday){ weekAnchor=monday; weekStartEquity=eq; }
   equityHighWater=MathMax(equityHighWater,eq); tradesToday=CountTodayTrades(); SaveState();
}
void RefreshRiskState(){
   datetime now=TimeCurrent(), today=StartOfDay(now), monday=StartOfWeek(now); double eq=AccountInfoDouble(ACCOUNT_EQUITY); bool changed=false;
   if(today!=dayAnchor){ dayAnchor=today; dayStartEquity=eq; tradesToday=CountTodayTrades(); changed=true; }
   if(monday!=weekAnchor){ weekAnchor=monday; weekStartEquity=eq; changed=true; }
   if(eq>equityHighWater){ equityHighWater=eq; changed=true; } if(changed) SaveState();
}
bool IsNewBar(){ datetime x=iTime(InpSymbol,InpTimeframe,0); if(x==0||x==lastBarTime) return false; lastBarTime=x; return true; }
bool IsDemoAccount(){ return (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO; }
bool TradingWindowOpen(){ MqlDateTime n; TimeToStruct(TimeCurrent(),n); if(n.day_of_week==0||n.day_of_week==6) return false; if(n.day_of_week==5&&n.hour>=FridayCutoffHour) return false; return n.hour>=StartHour&&n.hour<EndHour; }
double LossPercent(const double a){ if(a<=0.0) return 100.0; return 100.0*(a-AccountInfoDouble(ACCOUNT_EQUITY))/a; }
bool PortfolioRiskAllowsTrading(){
   double d=LossPercent(dayStartEquity); if(d>=MaxDailyLossPercent){ LogEvent("daily_lock",0,StringFormat("daily_loss_pct=%.3f",d)); return false; }
   double w=LossPercent(weekStartEquity); if(w>=MaxWeeklyLossPercent){ LogEvent("weekly_lock",0,StringFormat("weekly_loss_pct=%.3f",w)); return false; }
   double h=LossPercent(equityHighWater); if(h>=MaxHighWaterDrawdownPercent){ LogEvent("drawdown_lock",0,StringFormat("drawdown_pct=%.3f",h)); return false; } return true;
}
bool HasOpenPosition(){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong t=PositionGetTicket(i); if(t==0||!PositionSelectByTicket(t)) continue; if(PositionGetString(POSITION_SYMBOL)==InpSymbol&&(long)PositionGetInteger(POSITION_MAGIC)==MagicNumber) return true; } return false; }
double CurrentSpreadPoints(){ MqlTick t; if(!SymbolInfoTick(InpSymbol,t)) return -1.0; double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT); return p>0.0?(t.ask-t.bid)/p:-1.0; }
bool CooldownComplete(){ if(lastTradeBar==0) return true; return iBarShift(InpSymbol,InpTimeframe,lastTradeBar,false)>=CooldownBars; }
bool ReadIndicators(double &f1,double &f2,double &s1,double &s2,double &tr1,double &tr6,double &a1,double &x1,double &c1){
   double f[],s[],tr[],a[],x[],c[]; ArrayResize(f,3); ArrayResize(s,3); ArrayResize(tr,7); ArrayResize(a,3); ArrayResize(x,3); ArrayResize(c,3);
   ArraySetAsSeries(f,true); ArraySetAsSeries(s,true); ArraySetAsSeries(tr,true); ArraySetAsSeries(a,true); ArraySetAsSeries(x,true); ArraySetAsSeries(c,true);
   if(CopyBuffer(fastHandle,0,0,3,f)<3||CopyBuffer(slowHandle,0,0,3,s)<3||CopyBuffer(trendHandle,0,0,7,tr)<7||CopyBuffer(atrHandle,0,0,3,a)<3||CopyBuffer(adxHandle,0,0,3,x)<3||CopyClose(InpSymbol,InpTimeframe,0,3,c)<3) return false;
   f1=f[1]; f2=f[2]; s1=s[1]; s2=s[2]; tr1=tr[1]; tr6=tr[6]; a1=a[1]; x1=x[1]; c1=c[1]; return a1>0.0&&x1>=0.0;
}
double NormalizeVolume(double v){ double mn=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN),mx=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX),st=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP); if(st<=0.0||v<mn) return 0.0; v=MathMin(mx,MathFloor(v/st)*st); int d=(int)MathMax(0,MathRound(-MathLog10(st))); return NormalizeDouble(v,d); }
double CalculateVolume(double dist){ if(dist<=0.0) return 0.0; double money=AccountInfoDouble(ACCOUNT_EQUITY)*(RiskPercent/100.0),ts=SymbolInfoDouble(InpSymbol,SYMBOL_TRADE_TICK_SIZE),tv=SymbolInfoDouble(InpSymbol,SYMBOL_TRADE_TICK_VALUE_LOSS); if(tv<=0.0) tv=SymbolInfoDouble(InpSymbol,SYMBOL_TRADE_TICK_VALUE); if(ts<=0.0||tv<=0.0) return 0.0; return NormalizeVolume(money/((dist/ts)*tv)); }
bool StopsValid(double e,double sl,double tp){ double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT),m=(double)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL)*p; return MathAbs(e-sl)>=m&&MathAbs(tp-e)>=m; }
bool MarginAvailable(const ENUM_ORDER_TYPE type,const double v,const double p){ double m=0.0; return OrderCalcMargin(type,InpSymbol,v,p,m)&&m<=AccountInfoDouble(ACCOUNT_MARGIN_FREE); }

void EvaluateSignal(){
   RefreshRiskState();
   if(DemoOnly&&!IsDemoAccount()){ LogEvent("risk_block",0,"DemoOnly enabled on non-demo account"); return; }
   if(!TradingWindowOpen()){ LogEvent("session_block",0,"outside configured trading window"); return; }
   if(!PortfolioRiskAllowsTrading()||tradesToday>=MaxTradesPerDay||HasOpenPosition()) return;
   double spread=CurrentSpreadPoints(); if(spread<0.0||spread>MaxSpreadPoints){ LogEvent("spread_block",0,StringFormat("spread_points=%.1f",spread)); return; }
   if(!CooldownComplete()){ LogEvent("cooldown_block",0,"cooldown bars not complete"); return; }
   double f1,f2,s1,s2,tr1,tr6,atr1,adx1,c1;
   if(!ReadIndicators(f1,f2,s1,s2,tr1,tr6,atr1,adx1,c1)){ LogEvent("risk_block",0,"indicator data unavailable"); return; }
   if(adx1<MinADX){ LogEvent("adx_block",0,StringFormat("adx=%.2f minimum=%.2f",adx1,MinADX)); return; }
   bool longSignal=f2<=s2&&f1>s1&&c1>tr1&&tr1>tr6;
   bool shortSignal=f2>=s2&&f1<s1&&c1<tr1&&tr1<tr6;
   if(!longSignal&&!shortSignal){ LogEvent("no_signal",0,StringFormat("adx=%.2f no qualifying crossover",adx1)); return; }
   double separation=MathAbs(f1-s1), required=atr1*MinEMASeparationATR;
   if(separation<required){ LogEvent("ema_separation_block",0,StringFormat("separation=%.5f required=%.5f atr_fraction=%.3f",separation,required,MinEMASeparationATR)); return; }
   MqlTick tick; if(!SymbolInfoTick(InpSymbol,tick)){ LogEvent("order_rejected",0,"symbol tick unavailable"); return; }
   double stopDistance=atr1*ATRStopMultiplier, volume=CalculateVolume(stopDistance); if(volume<=0.0){ LogEvent("volume_block",0,"calculated volume invalid"); return; }
   trade.SetExpertMagicNumber(MagicNumber); trade.SetDeviationInPoints(MaxDeviationPoints); trade.SetTypeFillingBySymbol(InpSymbol);
   int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS); bool placed=false; double sl=0.0,tp=0.0;
   ENUM_ORDER_TYPE type=longSignal?ORDER_TYPE_BUY:ORDER_TYPE_SELL; double entry=longSignal?tick.ask:tick.bid;
   if(longSignal){ sl=NormalizeDouble(tick.ask-stopDistance,digits); tp=NormalizeDouble(tick.ask+stopDistance*RewardRisk,digits); }
   else{ sl=NormalizeDouble(tick.bid+stopDistance,digits); tp=NormalizeDouble(tick.bid-stopDistance*RewardRisk,digits); }
   if(!StopsValid(entry,sl,tp)||!MarginAvailable(type,volume,entry)){ LogEvent("order_rejected",0,"stops or margin validation failed"); return; }
   LogEvent(longSignal?"signal_long":"signal_short",0,StringFormat("adx=%.2f ema_sep=%.5f atr=%.5f spread_points=%.1f",adx1,separation,atr1,spread));
   if(longSignal) placed=trade.Buy(volume,InpSymbol,0.0,sl,tp,"PeakFX EURUSD H1 ADX EMASEP long");
   else placed=trade.Sell(volume,InpSymbol,0.0,sl,tp,"PeakFX EURUSD H1 ADX EMASEP short");
   if(placed){ tradesToday=CountTodayTrades(); lastTradeBar=iTime(InpSymbol,InpTimeframe,0); SaveState(); LogEvent("order_filled",trade.ResultDeal(),StringFormat("order=%I64u volume=%.2f result=%s",trade.ResultOrder(),volume,trade.ResultRetcodeDescription())); }
   else LogEvent("order_rejected",trade.ResultOrder(),StringFormat("retcode=%u description=%s",trade.ResultRetcode(),trade.ResultRetcodeDescription()));
}

int OnInit(){
   if(InpSymbol!="EURUSD"||InpTimeframe!=PERIOD_H1) return INIT_PARAMETERS_INCORRECT;
   if(FastEMA<=0||SlowEMA<=FastEMA||TrendEMA<=SlowEMA||ATRPeriod<=0||ADXPeriod<=0||MinADX<0.0||MinEMASeparationATR<0.0) return INIT_PARAMETERS_INCORRECT;
   if(RiskPercent<=0.0||RiskPercent>0.5||RewardRisk<1.0||HeartbeatSeconds<60) return INIT_PARAMETERS_INCORRECT;
   if(!SymbolSelect(InpSymbol,true)) return INIT_FAILED;
   fastHandle=iMA(InpSymbol,InpTimeframe,FastEMA,0,MODE_EMA,PRICE_CLOSE); slowHandle=iMA(InpSymbol,InpTimeframe,SlowEMA,0,MODE_EMA,PRICE_CLOSE);
   trendHandle=iMA(InpSymbol,InpTimeframe,TrendEMA,0,MODE_EMA,PRICE_CLOSE); atrHandle=iATR(InpSymbol,InpTimeframe,ATRPeriod); adxHandle=iADX(InpSymbol,InpTimeframe,ADXPeriod);
   if(fastHandle==INVALID_HANDLE||slowHandle==INVALID_HANDLE||trendHandle==INVALID_HANDLE||atrHandle==INVALID_HANDLE||adxHandle==INVALID_HANDLE) return INIT_FAILED;
   RestoreState(); lastBarTime=iTime(InpSymbol,InpTimeframe,0); EventSetTimer(HeartbeatSeconds);
   LogEvent("startup",0,StringFormat("version=1.40 demo_only=%s min_adx=%.2f min_ema_sep_atr=%.3f trades_today=%d equity=%.2f",DemoOnly?"true":"false",MinADX,MinEMASeparationATR,tradesToday,AccountInfoDouble(ACCOUNT_EQUITY))); return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ LogEvent("shutdown",0,StringFormat("reason=%d",reason)); EventKillTimer(); SaveState(); if(fastHandle!=INVALID_HANDLE) IndicatorRelease(fastHandle); if(slowHandle!=INVALID_HANDLE) IndicatorRelease(slowHandle); if(trendHandle!=INVALID_HANDLE) IndicatorRelease(trendHandle); if(atrHandle!=INVALID_HANDLE) IndicatorRelease(atrHandle); if(adxHandle!=INVALID_HANDLE) IndicatorRelease(adxHandle); }
void OnTimer(){ RefreshRiskState(); LogEvent("heartbeat",0,StringFormat("equity=%.2f daily_loss_pct=%.3f weekly_loss_pct=%.3f trades_today=%d open_position=%s",AccountInfoDouble(ACCOUNT_EQUITY),LossPercent(dayStartEquity),LossPercent(weekStartEquity),tradesToday,HasOpenPosition()?"true":"false")); }
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result){
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD||trans.deal==0||!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=InpSymbol||(long)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=MagicNumber) return;
   ENUM_DEAL_ENTRY e=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal,DEAL_ENTRY); double p=HistoryDealGetDouble(trans.deal,DEAL_PRICE),v=HistoryDealGetDouble(trans.deal,DEAL_VOLUME);
   double profit=HistoryDealGetDouble(trans.deal,DEAL_PROFIT)+HistoryDealGetDouble(trans.deal,DEAL_SWAP)+HistoryDealGetDouble(trans.deal,DEAL_COMMISSION);
   if(e==DEAL_ENTRY_IN||e==DEAL_ENTRY_INOUT) LogEvent("position_opened",trans.deal,StringFormat("price=%.5f volume=%.2f",p,v));
   if(e==DEAL_ENTRY_OUT||e==DEAL_ENTRY_OUT_BY||e==DEAL_ENTRY_INOUT) LogEvent("position_closed",trans.deal,StringFormat("price=%.5f volume=%.2f net_profit=%.2f",p,v,profit));
}
void OnTick(){ if(_Symbol!=InpSymbol) return; RefreshRiskState(); if(IsNewBar()){ LogEvent("new_bar",0,TimeToString(lastBarTime,TIME_DATE|TIME_MINUTES)); EvaluateSignal(); } }
