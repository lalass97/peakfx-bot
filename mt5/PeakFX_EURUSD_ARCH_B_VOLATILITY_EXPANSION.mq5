#property strict
#property version   "1.00"
#property description "PeakFX Architecture B frozen pre-structure-aligned volatility expansion"

#include <Trade/Trade.mqh>

input string InpSymbol = "EURUSD";
input double InpRiskPercent = 0.25;
input int InpAtrPeriod = 14;
input int InpPercentileLookback = 180;
input double InpCompressionPercentile = 0.25;
input int InpMinCompressionDays = 5;
input int InpMaxCompressionDays = 15;
input double InpExpansionMultiplier = 1.50;
input bool InpFastFailExit = false;
input int InpFastFailBars = 8;
input double InpTargetR = 2.0;
input double InpMaxSpreadPips = 2.0;
input int InpDeviationPoints = 10;
input bool InpRequireTickVolume = false; // false=baseline; true=only predeclared B-R1
input ulong InpMagic = 26080602;

CTrade trade;
int hAtrD1 = INVALID_HANDLE;
int hAtrH1 = INVALID_HANDLE;
datetime lastH1Bar = 0;
datetime entryBarTime = 0;
long activeBoxKey = 0;
long tradedBoxKey = 0;

struct CompressionState
{
   bool valid;
   int direction;
   datetime startTime;
   datetime endTime;
   double boxHigh;
   double boxLow;
   double meanH1Atr;
   long key;
};

int UtcDateKey(datetime t)
{
   MqlDateTime d;
   TimeToStruct(t,d);
   return d.year*10000+d.mon*100+d.day;
}

datetime ToUtc(datetime serverTime)
{
   const long offset=(long)(TimeTradeServer()-TimeGMT());
   return (datetime)((long)serverTime-offset);
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

bool GetAtr(int handle,int shift,double &value)
{
   double b[1];
   if(CopyBuffer(handle,0,shift,1,b)!=1) return false;
   value=b[0];
   return MathIsValidNumber(value) && value>0.0;
}

double Percentile(double &values[],int n,double p)
{
   if(n<=0) return 0.0;
   double copy[];
   ArrayResize(copy,n);
   for(int i=0;i<n;i++) copy[i]=values[i];
   ArraySort(copy);
   const double idx=(n-1)*p;
   const int lo=(int)MathFloor(idx);
   const int hi=(int)MathCeil(idx);
   if(lo==hi) return copy[lo];
   return copy[lo]+(copy[hi]-copy[lo])*(idx-lo);
}

bool DailyCompressed(int shift)
{
   double current=0.0;
   if(!GetAtr(hAtrD1,shift,current)) return false;
   double hist[];
   ArrayResize(hist,InpPercentileLookback);
   for(int i=0;i<InpPercentileLookback;i++)
   {
      if(!GetAtr(hAtrD1,shift+1+i,hist[i])) return false;
   }
   return current<=Percentile(hist,InpPercentileLookback,InpCompressionPercentile);
}

bool IsSwingHigh(int shift)
{
   const double h=iHigh(InpSymbol,PERIOD_D1,shift);
   if(h<=0.0) return false;
   return h>iHigh(InpSymbol,PERIOD_D1,shift+1) && h>iHigh(InpSymbol,PERIOD_D1,shift+2)
       && h>iHigh(InpSymbol,PERIOD_D1,shift-1) && h>iHigh(InpSymbol,PERIOD_D1,shift-2);
}

bool IsSwingLow(int shift)
{
   const double l=iLow(InpSymbol,PERIOD_D1,shift);
   if(l<=0.0) return false;
   return l<iLow(InpSymbol,PERIOD_D1,shift+1) && l<iLow(InpSymbol,PERIOD_D1,shift+2)
       && l<iLow(InpSymbol,PERIOD_D1,shift-1) && l<iLow(InpSymbol,PERIOD_D1,shift-2);
}

int PreCompressionDirection(int compressionStartShift)
{
   double highs[2],lows[2];
   int hc=0,lc=0;
   for(int s=compressionStartShift+2;s<compressionStartShift+400 && (hc<2 || lc<2);s++)
   {
      if(hc<2 && IsSwingHigh(s)) highs[hc++]=iHigh(InpSymbol,PERIOD_D1,s);
      if(lc<2 && IsSwingLow(s)) lows[lc++]=iLow(InpSymbol,PERIOD_D1,s);
   }
   if(hc<2 || lc<2) return 0;
   // arrays are newest eligible first, then older
   if(highs[0]>highs[1] && lows[0]>lows[1]) return 1;
   if(highs[0]<highs[1] && lows[0]<lows[1]) return -1;
   return 0;
}

bool MeanCompressionH1Atr(datetime startTime,datetime endTime,double &meanAtr)
{
   MqlRates h1[];
   ArraySetAsSeries(h1,true);
   const int copied=CopyRates(InpSymbol,PERIOD_H1,startTime,endTime+86399,h1);
   if(copied<72) return false;
   double total=0.0;
   int count=0;
   for(int i=0;i<copied;i++)
   {
      if(h1[i].time<startTime || h1[i].time>endTime+86399) continue;
      const int shift=iBarShift(InpSymbol,PERIOD_H1,h1[i].time,true);
      if(shift<1) continue;
      double atr=0.0;
      if(GetAtr(hAtrH1,shift,atr)) { total+=atr; count++; }
   }
   if(count<72) return false;
   meanAtr=total/count;
   return meanAtr>0.0;
}

bool BuildCompressionState(CompressionState &s)
{
   s.valid=false;
   int endShift=1;
   int count=0;
   while(endShift+count<InpMaxCompressionDays+2 && DailyCompressed(endShift+count)) count++;
   if(count<InpMinCompressionDays) return false;

   // More than max consecutive compressed days invalidates the phase.
   if(count>=InpMaxCompressionDays && DailyCompressed(endShift+count)) return false;

   const int startShift=endShift+count-1;
   const int direction=PreCompressionDirection(startShift);
   if(direction==0) return false;

   double high=-DBL_MAX,low=DBL_MAX;
   for(int sh=endShift;sh<=startShift;sh++)
   {
      high=MathMax(high,iHigh(InpSymbol,PERIOD_D1,sh));
      low=MathMin(low,iLow(InpSymbol,PERIOD_D1,sh));
   }
   if(high<=low) return false;

   const datetime start=iTime(InpSymbol,PERIOD_D1,startShift);
   const datetime end=iTime(InpSymbol,PERIOD_D1,endShift);
   double meanAtr=0.0;
   if(!MeanCompressionH1Atr(start,end,meanAtr)) return false;

   s.valid=true;
   s.direction=direction;
   s.startTime=start;
   s.endTime=end;
   s.boxHigh=high;
   s.boxLow=low;
   s.meanH1Atr=meanAtr;
   s.key=(long)UtcDateKey(ToUtc(start))*100000L+(long)UtcDateKey(ToUtc(end));
   return true;
}

bool TickVolumeConfirmed()
{
   if(!InpRequireTickVolume) return true;
   const long signalVolume=(long)iVolume(InpSymbol,PERIOD_H1,1);
   if(signalVolume<=0) return false;
   double total=0.0;
   for(int i=2;i<22;i++) total+=(double)iVolume(InpSymbol,PERIOD_H1,i);
   return signalVolume>(total/20.0);
}

bool WeeklyEntryAllowed(datetime utc)
{
   MqlDateTime d;
   TimeToStruct(utc,d);
   if(d.day_of_week==0) return false;
   if(d.day_of_week==1 && d.hour<2) return false;
   if(d.day_of_week==5 && d.hour>=20) return false;
   if(d.day_of_week==6) return false;
   return true;
}

void ForceFlatBeforeWeeklyClose(datetime utc)
{
   if(!HasOurPosition()) return;
   MqlDateTime d;
   TimeToStruct(utc,d);
   if(d.day_of_week==5 && d.hour>=20)
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

bool StopValid(double entry,double sl)
{
   const double point=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);
   const double minDist=(double)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
   return MathAbs(entry-sl)>=minDist;
}

void ManageFastFail()
{
   if(!InpFastFailExit || !HasOurPosition() || entryBarTime<=0) return;
   const int bars=iBarShift(InpSymbol,PERIOD_H1,entryBarTime,false);
   if(bars>=InpFastFailBars)
      trade.PositionClose(InpSymbol,InpDeviationPoints);
}

void EvaluateEntry(datetime utcNow)
{
   if(HasOurPosition() || !WeeklyEntryAllowed(utcNow) || !SpreadAllowed()) return;

   CompressionState s;
   if(!BuildCompressionState(s)) return;
   activeBoxKey=s.key;
   if(tradedBoxKey==s.key) return;

   const double signalClose=iClose(InpSymbol,PERIOD_H1,1);
   const double signalHigh=iHigh(InpSymbol,PERIOD_H1,1);
   const double signalLow=iLow(InpSymbol,PERIOD_H1,1);
   const double prevClose=iClose(InpSymbol,PERIOD_H1,2);
   if(signalClose<=0.0 || signalHigh<=signalLow || prevClose<=0.0) return;
   const double trueRange=MathMax(signalHigh-signalLow,MathMax(MathAbs(signalHigh-prevClose),MathAbs(signalLow-prevClose)));
   if(trueRange<InpExpansionMultiplier*s.meanH1Atr || !TickVolumeConfirmed()) return;

   MqlTick tick;
   if(!SymbolInfoTick(InpSymbol,tick)) return;
   const int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);

   if(s.direction>0 && signalClose>s.boxHigh)
   {
      const double entry=tick.ask;
      const double sl=NormalizeDouble(entry-s.meanH1Atr,digits);
      const double tp=InpFastFailExit ? 0.0 : NormalizeDouble(entry+InpTargetR*s.meanH1Atr,digits);
      const double volume=VolumeForRisk(ORDER_TYPE_BUY,entry,sl);
      if(volume>0.0 && StopValid(entry,sl) && trade.Buy(volume,InpSymbol,0.0,sl,tp,"ARCH_B"))
      {
         tradedBoxKey=s.key;
         entryBarTime=iTime(InpSymbol,PERIOD_H1,0);
      }
   }
   else if(s.direction<0 && signalClose<s.boxLow)
   {
      const double entry=tick.bid;
      const double sl=NormalizeDouble(entry+s.meanH1Atr,digits);
      const double tp=InpFastFailExit ? 0.0 : NormalizeDouble(entry-InpTargetR*s.meanH1Atr,digits);
      const double volume=VolumeForRisk(ORDER_TYPE_SELL,entry,sl);
      if(volume>0.0 && StopValid(entry,sl) && trade.Sell(volume,InpSymbol,0.0,sl,tp,"ARCH_B"))
      {
         tradedBoxKey=s.key;
         entryBarTime=iTime(InpSymbol,PERIOD_H1,0);
      }
   }
}

int OnInit()
{
   if(!SymbolSelect(InpSymbol,true)) return INIT_FAILED;
   hAtrD1=iATR(InpSymbol,PERIOD_D1,InpAtrPeriod);
   hAtrH1=iATR(InpSymbol,PERIOD_H1,InpAtrPeriod);
   if(hAtrD1==INVALID_HANDLE || hAtrH1==INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hAtrD1!=INVALID_HANDLE) IndicatorRelease(hAtrD1);
   if(hAtrH1!=INVALID_HANDLE) IndicatorRelease(hAtrH1);
}

void OnTick()
{
   const datetime utcNow=ToUtc(TimeTradeServer());
   ForceFlatBeforeWeeklyClose(utcNow);

   const datetime currentBar=iTime(InpSymbol,PERIOD_H1,0);
   if(currentBar<=0 || currentBar==lastH1Bar) return;
   lastH1Bar=currentBar;

   ManageFastFail();
   EvaluateEntry(utcNow);
}
