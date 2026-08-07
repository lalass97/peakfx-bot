#property strict
#property version   "1.00"
#property description "PeakFX Architecture C frozen session exhaustion mean reversion"

#include <Trade/Trade.mqh>

input string InpSymbol = "EURUSD";
input double InpRiskPercent = 0.25;
input double InpDailyLossLimitPercent = 1.0;
input double InpWeeklyLossLimitPercent = 2.0;
input double InpExcursionMultiple = 0.50;
input bool InpMidpointTarget = true;
input double InpStopBufferMultiple = 0.25;
input double InpFixedTargetR = 1.50;
input double InpMaxSpreadPips = 2.0;
input int InpDeviationPoints = 10;
input ulong InpMagic = 26080703;

CTrade trade;
datetime lastH1Bar = 0;
int consumedDayKey = 0;
int equityDayKey = 0;
int equityWeekKey = 0;
double dayStartEquity = 0.0;
double weekStartEquity = 0.0;

int UtcDateKey(datetime t)
{
   MqlDateTime d;
   TimeToStruct(t,d);
   return d.year*10000+d.mon*100+d.day;
}

int UtcWeekKey(datetime t)
{
   MqlDateTime d;
   TimeToStruct(t,d);
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
   MqlDateTime d;
   TimeToStruct(utc,d);
   d.hour=0;d.min=0;d.sec=0;
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

bool AsianRangeForDay(int dayKey,double &high,double &low)
{
   high=-DBL_MAX;
   low=DBL_MAX;
   bool seen[7];
   for(int i=0;i<7;i++) seen[i]=false;
   int count=0;

   const int bars=Bars(InpSymbol,PERIOD_H1);
   const int maxShift=MathMin(bars-1,1200);
   for(int sh=1;sh<=maxShift;sh++)
   {
      const datetime bt=iTime(InpSymbol,PERIOD_H1,sh);
      if(bt<=0) continue;
      const datetime utc=ToUtc(bt);
      const int key=UtcDateKey(utc);
      if(key>dayKey) continue;
      if(key<dayKey && count>0) break;
      if(key!=dayKey) continue;
      MqlDateTime d;
      TimeToStruct(utc,d);
      if(d.hour<0 || d.hour>6) continue;
      if(seen[d.hour]) continue;
      const double h=iHigh(InpSymbol,PERIOD_H1,sh);
      const double l=iLow(InpSymbol,PERIOD_H1,sh);
      if(h<=0.0 || l<=0.0 || h<=l) return false;
      seen[d.hour]=true;
      count++;
      high=MathMax(high,h);
      low=MathMin(low,l);
   }
   return count==7 && high>low;
}

double Median(double &values[],int n)
{
   if(n<=0) return 0.0;
   double copy[];
   ArrayResize(copy,n);
   for(int i=0;i<n;i++) copy[i]=values[i];
   ArraySort(copy);
   if((n%2)==1) return copy[n/2];
   return 0.5*(copy[n/2-1]+copy[n/2]);
}

bool MedianPriorAsianRange(datetime currentUtc,double &medianRange)
{
   double ranges[20];
   int found=0;
   datetime cursor=UtcDayStart(currentUtc)-86400;
   for(int attempts=0;attempts<45 && found<20;attempts++,cursor-=86400)
   {
      MqlDateTime d;
      TimeToStruct(cursor,d);
      if(d.day_of_week==0 || d.day_of_week==6) continue;
      double h=0.0,l=0.0;
      if(!AsianRangeForDay(UtcDateKey(cursor),h,l)) continue;
      ranges[found++]=h-l;
   }
   if(found<20) return false;
   medianRange=Median(ranges,20);
   return medianRange>0.0;
}

bool SignalWindow(datetime signalUtc)
{
   MqlDateTime d;
   TimeToStruct(signalUtc,d);
   if(d.day_of_week==0 || d.day_of_week==6) return false;
   return d.hour>=7 && d.hour<=14;
}

void ForceFlat(datetime utcNow)
{
   if(!HasOurPosition()) return;
   MqlDateTime d;
   TimeToStruct(utcNow,d);
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
   if(tp>0.0 && MathAbs(tp-entry)<minDist) return false;
   return true;
}

void EvaluateEntry(datetime utcNow)
{
   if(HasOurPosition() || !LossLimitsAllowEntry(utcNow)) return;

   const datetime signalServer=iTime(InpSymbol,PERIOD_H1,1);
   if(signalServer<=0) return;
   const datetime signalUtc=ToUtc(signalServer);
   if(!SignalWindow(signalUtc)) return;
   const int dayKey=UtcDateKey(signalUtc);
   if(consumedDayKey==dayKey) return;

   double asianHigh=0.0,asianLow=0.0;
   if(!AsianRangeForDay(dayKey,asianHigh,asianLow)) return;
   double medianRange=0.0;
   if(!MedianPriorAsianRange(signalUtc,medianRange)) return;

   const double boundaryUp=asianHigh+InpExcursionMultiple*medianRange;
   const double boundaryDown=asianLow-InpExcursionMultiple*medianRange;
   const double o=iOpen(InpSymbol,PERIOD_H1,1);
   const double h=iHigh(InpSymbol,PERIOD_H1,1);
   const double l=iLow(InpSymbol,PERIOD_H1,1);
   const double c=iClose(InpSymbol,PERIOD_H1,1);
   if(o<=0.0 || h<=l || c<=0.0) return;

   int direction=0;
   if(h>boundaryUp && c<asianHigh && c<o) direction=-1;
   else if(l<boundaryDown && c>asianLow && c>o) direction=1;
   if(direction==0) return;

   // The first valid reversal signal consumes the day even if execution is skipped.
   consumedDayKey=dayKey;
   if(!SpreadAllowed()) return;

   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol,tick)) return;
   const int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);
   const double midpoint=0.5*(asianHigh+asianLow);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);

   if(direction<0)
   {
      const double entry=tick.bid;
      const double sl=NormalizeDouble(h+InpStopBufferMultiple*medianRange,digits);
      if(sl<=entry) return;
      const double risk=sl-entry;
      const double tp=InpMidpointTarget ? NormalizeDouble(midpoint,digits) : NormalizeDouble(entry-InpFixedTargetR*risk,digits);
      if(tp>=entry) return;
      const double volume=VolumeForRisk(ORDER_TYPE_SELL,entry,sl);
      if(volume>0.0 && StopsValid(entry,sl,tp)) trade.Sell(volume,InpSymbol,0.0,sl,tp,"ARCH_C");
   }
   else
   {
      const double entry=tick.ask;
      const double sl=NormalizeDouble(l-InpStopBufferMultiple*medianRange,digits);
      if(sl>=entry) return;
      const double risk=entry-sl;
      const double tp=InpMidpointTarget ? NormalizeDouble(midpoint,digits) : NormalizeDouble(entry+InpFixedTargetR*risk,digits);
      if(tp<=entry) return;
      const double volume=VolumeForRisk(ORDER_TYPE_BUY,entry,sl);
      if(volume>0.0 && StopsValid(entry,sl,tp)) trade.Buy(volume,InpSymbol,0.0,sl,tp,"ARCH_C");
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

   const datetime currentH1=iTime(InpSymbol,PERIOD_H1,0);
   if(currentH1<=0 || currentH1==lastH1Bar) return;
   lastH1Bar=currentH1;
   EvaluateEntry(utcNow);
}
