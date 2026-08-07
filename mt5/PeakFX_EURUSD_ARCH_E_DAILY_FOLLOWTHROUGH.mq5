#property strict
#property version   "1.00"
#property description "PeakFX Architecture E frozen prior-day directional follow-through"

#include <Trade/Trade.mqh>

input string InpSymbol = "EURUSD";
input double InpRiskPercent = 0.25;
input double InpDailyLossLimitPercent = 1.0;
input double InpWeeklyLossLimitPercent = 2.0;
input double InpBodyFraction = 0.55;
input double InpTargetR = 1.00;
input double InpStopBufferFraction = 0.10;
input double InpMaxSpreadPips = 2.0;
input int InpDeviationPoints = 10;
input ulong InpMagic = 26080705;

CTrade trade;
datetime lastM15Bar = 0;
int consumedDayKey = 0;
int equityDayKey = 0;
int equityWeekKey = 0;
double dayStartEquity = 0.0;
double weekStartEquity = 0.0;

int UtcDateKey(datetime t)
{
   MqlDateTime d; TimeToStruct(t,d);
   return d.year*10000+d.mon*100+d.day;
}

int UtcWeekKey(datetime t)
{
   MqlDateTime d; TimeToStruct(t,d);
   const datetime monday=t-(d.day_of_week==0 ? 6 : d.day_of_week-1)*86400;
   return UtcDateKey(monday);
}

datetime ToUtc(datetime serverTime)
{
   const long offset=(long)(TimeTradeServer()-TimeGMT());
   return (datetime)((long)serverTime-offset);
}

datetime UtcDayStart(datetime utc)
{
   MqlDateTime d; TimeToStruct(utc,d);
   d.hour=0; d.min=0; d.sec=0;
   return StructToTime(d);
}

double PipSize()
{
   const int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);
   const double point=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);
   return (digits==3 || digits==5) ? 10.0*point : point;
}

bool SpreadAllowed()
{
   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol,tick)) return false;
   return (tick.ask-tick.bid)<=InpMaxSpreadPips*PipSize();
}

bool HasOurPosition()
{
   if(!PositionSelect(InpSymbol)) return false;
   return (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;
}

void RefreshLossAnchors(datetime utcNow)
{
   const int dayKey=UtcDateKey(utcNow);
   const int weekKey=UtcWeekKey(utcNow);
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(equityDayKey!=dayKey || dayStartEquity<=0.0)
   {
      equityDayKey=dayKey;
      dayStartEquity=equity;
   }
   if(equityWeekKey!=weekKey || weekStartEquity<=0.0)
   {
      equityWeekKey=weekKey;
      weekStartEquity=equity;
   }
}

bool LossLimitsAllowEntry(datetime utcNow)
{
   RefreshLossAnchors(utcNow);
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(dayStartEquity>0.0 && equity<=dayStartEquity*(1.0-InpDailyLossLimitPercent/100.0)) return false;
   if(weekStartEquity>0.0 && equity<=weekStartEquity*(1.0-InpWeeklyLossLimitPercent/100.0)) return false;
   return true;
}

bool UtcDayOhlc(int dayKey,double &o,double &h,double &l,double &c)
{
   bool seen[96];
   for(int i=0;i<96;i++) seen[i]=false;
   int count=0;
   h=-DBL_MAX; l=DBL_MAX; o=0.0; c=0.0;
   const int bars=Bars(InpSymbol,PERIOD_M15);
   const int maxShift=MathMin(bars-1,4000);

   for(int sh=1;sh<=maxShift;sh++)
   {
      const datetime bt=iTime(InpSymbol,PERIOD_M15,sh);
      if(bt<=0) continue;
      const datetime utc=ToUtc(bt);
      const int key=UtcDateKey(utc);
      if(key>dayKey) continue;
      if(key<dayKey && count>0) break;
      if(key!=dayKey) continue;
      MqlDateTime d; TimeToStruct(utc,d);
      if(d.min!=0 && d.min!=15 && d.min!=30 && d.min!=45) continue;
      const int idx=d.hour*4+d.min/15;
      if(idx<0 || idx>=96 || seen[idx]) continue;
      const double bo=iOpen(InpSymbol,PERIOD_M15,sh);
      const double bh=iHigh(InpSymbol,PERIOD_M15,sh);
      const double bl=iLow(InpSymbol,PERIOD_M15,sh);
      const double bc=iClose(InpSymbol,PERIOD_M15,sh);
      if(bo<=0.0 || bc<=0.0 || bh<=bl) return false;
      seen[idx]=true; count++;
      if(idx==0) o=bo;
      if(idx==95) c=bc;
      h=MathMax(h,bh); l=MathMin(l,bl);
   }
   return count==96 && o>0.0 && c>0.0 && h>l;
}

bool PriorValidUtcDay(datetime currentUtc,int &priorKey,double &o,double &h,double &l,double &c)
{
   datetime cursor=UtcDayStart(currentUtc)-86400;
   for(int attempts=0;attempts<7;attempts++,cursor-=86400)
   {
      MqlDateTime d; TimeToStruct(cursor,d);
      if(d.day_of_week==0 || d.day_of_week==6) continue;
      const int key=UtcDateKey(cursor);
      if(UtcDayOhlc(key,o,h,l,c))
      {
         priorKey=key;
         return true;
      }
   }
   return false;
}

bool SignalWindow(datetime signalUtc)
{
   MqlDateTime d; TimeToStruct(signalUtc,d);
   if(d.day_of_week==0 || d.day_of_week==6) return false;
   if(d.hour<7 || d.hour>13) return false;
   return d.min==0 || d.min==15 || d.min==30 || d.min==45;
}

void ForceFlat(datetime utcNow)
{
   if(!HasOurPosition()) return;
   MqlDateTime d; TimeToStruct(utcNow,d);
   if(d.hour>=20 || d.day_of_week==0 || d.day_of_week==6)
      trade.PositionClose(InpSymbol,InpDeviationPoints);
}

double NormalizeVolume(double volume)
{
   const double minVol=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN);
   const double maxVol=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0 || volume<minVol) return 0.0;
   volume=MathFloor(volume/step)*step;
   if(volume<minVol || volume>maxVol) return 0.0;
   return NormalizeDouble(volume,2);
}

double VolumeForRisk(ENUM_ORDER_TYPE type,double entry,double stop)
{
   const double riskMoney=AccountInfoDouble(ACCOUNT_EQUITY)*(InpRiskPercent/100.0);
   double oneLotLoss=0.0;
   if(!OrderCalcProfit(type,InpSymbol,1.0,entry,stop,oneLotLoss)) return 0.0;
   oneLotLoss=MathAbs(oneLotLoss);
   if(oneLotLoss<=0.0) return 0.0;
   return NormalizeVolume(riskMoney/oneLotLoss);
}

bool StopsValid(double entry,double sl,double tp)
{
   const double point=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);
   const double minDist=(double)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
   if(MathAbs(entry-sl)<minDist) return false;
   if(MathAbs(tp-entry)<minDist) return false;
   return true;
}

void EvaluateEntry(datetime utcNow)
{
   if(HasOurPosition() || !LossLimitsAllowEntry(utcNow)) return;

   const datetime signalServer=iTime(InpSymbol,PERIOD_M15,1);
   if(signalServer<=0) return;
   const datetime signalUtc=ToUtc(signalServer);
   if(!SignalWindow(signalUtc)) return;
   const int dayKey=UtcDateKey(signalUtc);
   if(consumedDayKey==dayKey) return;

   int priorKey=0;
   double po=0.0,ph=0.0,pl=0.0,pc=0.0;
   if(!PriorValidUtcDay(signalUtc,priorKey,po,ph,pl,pc)) return;
   const double priorRange=ph-pl;
   if(priorRange<=0.0) return;
   const double body=MathAbs(pc-po);
   const double bodyFraction=body/priorRange;
   if(bodyFraction<InpBodyFraction) return;

   int priorDirection=0;
   if(pc>po) priorDirection=1;
   else if(pc<po) priorDirection=-1;
   if(priorDirection==0) return;

   const double so=iOpen(InpSymbol,PERIOD_M15,1);
   const double sh=iHigh(InpSymbol,PERIOD_M15,1);
   const double slw=iLow(InpSymbol,PERIOD_M15,1);
   const double sc=iClose(InpSymbol,PERIOD_M15,1);
   if(so<=0.0 || sc<=0.0 || sh<=slw) return;

   int direction=0;
   if(priorDirection>0 && sc>ph && sc>so) direction=1;
   else if(priorDirection<0 && sc<pl && sc<so) direction=-1;
   if(direction==0) return;

   consumedDayKey=dayKey;
   if(!SpreadAllowed()) return;

   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol,tick)) return;
   const int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);

   if(direction>0)
   {
      const double entry=tick.ask;
      const double stop=NormalizeDouble(slw-InpStopBufferFraction*priorRange,digits);
      if(stop>=entry) return;
      const double risk=entry-stop;
      const double tp=NormalizeDouble(entry+InpTargetR*risk,digits);
      const double volume=VolumeForRisk(ORDER_TYPE_BUY,entry,stop);
      if(volume>0.0 && StopsValid(entry,stop,tp)) trade.Buy(volume,InpSymbol,0.0,stop,tp,"ARCH_E");
   }
   else
   {
      const double entry=tick.bid;
      const double stop=NormalizeDouble(sh+InpStopBufferFraction*priorRange,digits);
      if(stop<=entry) return;
      const double risk=stop-entry;
      const double tp=NormalizeDouble(entry-InpTargetR*risk,digits);
      const double volume=VolumeForRisk(ORDER_TYPE_SELL,entry,stop);
      if(volume>0.0 && StopsValid(entry,stop,tp)) trade.Sell(volume,InpSymbol,0.0,stop,tp,"ARCH_E");
   }
}

int OnInit()
{
   if(!SymbolSelect(InpSymbol,true)) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   RefreshLossAnchors(ToUtc(TimeTradeServer()));
   return INIT_SUCCEEDED;
}

void OnTick()
{
   const datetime utcNow=ToUtc(TimeTradeServer());
   RefreshLossAnchors(utcNow);
   ForceFlat(utcNow);

   const datetime currentM15=iTime(InpSymbol,PERIOD_M15,0);
   if(currentM15<=0 || currentM15==lastM15Bar) return;
   lastM15Bar=currentM15;
   EvaluateEntry(utcNow);
}
