#property strict
#property version   "1.00"
#property description "PeakFX Architecture A frozen regime-aligned session breakout"

#include <Trade/Trade.mqh>

input string InpSymbol = "EURUSD";
input ENUM_TIMEFRAMES InpExecutionTimeframe = PERIOD_M15;
input double InpRiskPercent = 0.50;
input int InpAtrPeriod = 14;
input int InpFastEmaPeriod = 20;
input int InpSlowEmaPeriod = 50;
input double InpBreakoutBufferAtr = 0.10;
input double InpStopAtrFloor = 1.00;
input double InpTargetR = 1.50;
input double InpMinRangeAtr = 0.40;
input double InpMaxRangeAtr = 1.50;
input double InpMaxSpreadPips = 2.0;
input int InpDeviationPoints = 10;
input ulong InpMagic = 26080601;
input bool InpRequireH4EmaSlope = false; // false=baseline; true=only predeclared A-R1

CTrade trade;
int hAtrH1 = INVALID_HANDLE;
int hFastH4 = INVALID_HANDLE;
int hSlowH4 = INVALID_HANDLE;
datetime lastM15Bar = 0;
int lastTradeUtcDate = 0;
int frozenUtcDate = 0;
double frozenAsianHigh = 0.0;
double frozenAsianLow = 0.0;
double frozenAtr = 0.0;
bool rangeReady = false;

int UtcDateKey(datetime utc)
{
   MqlDateTime d;
   TimeToStruct(utc,d);
   return d.year*10000+d.mon*100+d.day;
}

datetime ToUtc(datetime serverTime)
{
   const long offset=(long)(TimeTradeServer()-TimeGMT());
   return (datetime)((long)serverTime-offset);
}

bool GetBufferValue(int handle,int shift,double &value)
{
   double b[1];
   if(CopyBuffer(handle,0,shift,1,b)!=1) return false;
   value=b[0];
   return MathIsValidNumber(value) && value>0.0;
}

bool HasOurPosition()
{
   if(!PositionSelect(InpSymbol)) return false;
   return (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;
}

void CloseAtSessionEnd(datetime utcNow)
{
   MqlDateTime d;
   TimeToStruct(utcNow,d);
   if(d.hour<20 || !HasOurPosition()) return;
   trade.PositionClose(InpSymbol,InpDeviationPoints);
}

bool FreezeAsianRange(datetime utcNow)
{
   const int dateKey=UtcDateKey(utcNow);
   if(frozenUtcDate==dateKey && rangeReady) return true;

   MqlRates rates[];
   ArraySetAsSeries(rates,true);
   const int copied=CopyRates(InpSymbol,PERIOD_M15,1,120,rates);
   if(copied<24) return false;

   double high=-DBL_MAX;
   double low=DBL_MAX;
   int count=0;
   for(int i=0;i<copied;i++)
   {
      const datetime utc=ToUtc(rates[i].time);
      if(UtcDateKey(utc)!=dateKey) continue;
      MqlDateTime d;
      TimeToStruct(utc,d);
      const int minuteOfDay=d.hour*60+d.min;
      if(minuteOfDay>=0 && minuteOfDay<=405) // 00:00 through 06:45 UTC
      {
         high=MathMax(high,rates[i].high);
         low=MathMin(low,rates[i].low);
         count++;
      }
   }
   if(count<24 || high<=low) return false;

   double atr=0.0;
   if(!GetBufferValue(hAtrH1,1,atr)) return false;
   const double width=high-low;
   if(width<InpMinRangeAtr*atr || width>InpMaxRangeAtr*atr) return false;

   frozenUtcDate=dateKey;
   frozenAsianHigh=high;
   frozenAsianLow=low;
   frozenAtr=atr;
   rangeReady=true;
   return true;
}

int RegimeDirection()
{
   double fast1=0.0,fast2=0.0,slow1=0.0;
   if(!GetBufferValue(hFastH4,1,fast1) || !GetBufferValue(hFastH4,2,fast2) || !GetBufferValue(hSlowH4,1,slow1)) return 0;
   const double close1=iClose(InpSymbol,PERIOD_H4,1);
   if(close1<=0.0) return 0;

   if(fast1>slow1 && close1>fast1)
   {
      if(InpRequireH4EmaSlope && fast1<=fast2) return 0;
      return 1;
   }
   if(fast1<slow1 && close1<fast1)
   {
      if(InpRequireH4EmaSlope && fast1>=fast2) return 0;
      return -1;
   }
   return 0;
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

double NormalizeVolume(double volume)
{
   const double minVol=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN);
   const double maxVol=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0) return 0.0;
   volume=MathFloor(volume/step)*step;
   volume=MathMax(minVol,MathMin(maxVol,volume));
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
   const int stops=(int)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL);
   const double minDist=stops*point;
   return MathAbs(entry-sl)>=minDist && MathAbs(tp-entry)>=minDist;
}

void EvaluateEntry(datetime utcNow)
{
   MqlDateTime d;
   TimeToStruct(utcNow,d);
   const int minuteOfDay=d.hour*60+d.min;
   if(minuteOfDay<420 || minuteOfDay>659) return; // 07:00 through 10:59 UTC

   const int dateKey=UtcDateKey(utcNow);
   if(lastTradeUtcDate==dateKey || HasOurPosition()) return;
   if(!SpreadAllowed() || !FreezeAsianRange(utcNow)) return;

   const int regime=RegimeDirection();
   if(regime==0) return;

   const double close1=iClose(InpSymbol,PERIOD_M15,1);
   const double close2=iClose(InpSymbol,PERIOD_M15,2);
   if(close1<=0.0 || close2<=0.0) return;

   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol,tick)) return;
   const double buffer=InpBreakoutBufferAtr*frozenAtr;
   const int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);

   if(regime>0 && close2<=frozenAsianHigh && close1>frozenAsianHigh+buffer)
   {
      const double entry=tick.ask;
      const double structural=entry-(frozenAsianLow-0.10*frozenAtr);
      const double stopDistance=MathMax(InpStopAtrFloor*frozenAtr,structural);
      const double sl=NormalizeDouble(entry-stopDistance,digits);
      const double tp=NormalizeDouble(entry+InpTargetR*stopDistance,digits);
      const double volume=VolumeForRisk(ORDER_TYPE_BUY,entry,sl);
      if(volume>0.0 && StopsValid(entry,sl,tp) && trade.Buy(volume,InpSymbol,0.0,sl,tp,"ARCH_A_BASELINE"))
         lastTradeUtcDate=dateKey;
   }
   else if(regime<0 && close2>=frozenAsianLow && close1<frozenAsianLow-buffer)
   {
      const double entry=tick.bid;
      const double structural=(frozenAsianHigh+0.10*frozenAtr)-entry;
      const double stopDistance=MathMax(InpStopAtrFloor*frozenAtr,structural);
      const double sl=NormalizeDouble(entry+stopDistance,digits);
      const double tp=NormalizeDouble(entry-InpTargetR*stopDistance,digits);
      const double volume=VolumeForRisk(ORDER_TYPE_SELL,entry,sl);
      if(volume>0.0 && StopsValid(entry,sl,tp) && trade.Sell(volume,InpSymbol,0.0,sl,tp,"ARCH_A_BASELINE"))
         lastTradeUtcDate=dateKey;
   }
}

int OnInit()
{
   if(!SymbolSelect(InpSymbol,true)) return INIT_FAILED;
   hAtrH1=iATR(InpSymbol,PERIOD_H1,InpAtrPeriod);
   hFastH4=iMA(InpSymbol,PERIOD_H4,InpFastEmaPeriod,0,MODE_EMA,PRICE_CLOSE);
   hSlowH4=iMA(InpSymbol,PERIOD_H4,InpSlowEmaPeriod,0,MODE_EMA,PRICE_CLOSE);
   if(hAtrH1==INVALID_HANDLE || hFastH4==INVALID_HANDLE || hSlowH4==INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hAtrH1!=INVALID_HANDLE) IndicatorRelease(hAtrH1);
   if(hFastH4!=INVALID_HANDLE) IndicatorRelease(hFastH4);
   if(hSlowH4!=INVALID_HANDLE) IndicatorRelease(hSlowH4);
}

void OnTick()
{
   const datetime utcNow=ToUtc(TimeTradeServer());
   CloseAtSessionEnd(utcNow);

   const datetime currentBar=iTime(InpSymbol,PERIOD_M15,0);
   if(currentBar<=0 || currentBar==lastM15Bar) return;
   lastM15Bar=currentBar;

   const int currentDate=UtcDateKey(utcNow);
   if(frozenUtcDate!=currentDate)
   {
      rangeReady=false;
      frozenAsianHigh=0.0;
      frozenAsianLow=0.0;
      frozenAtr=0.0;
   }
   EvaluateEntry(utcNow);
}
