#property strict
#property version   "1.00"
#property description "PeakFX Architecture F frozen London opening-range breakout"

#include <Trade/Trade.mqh>

input string InpSymbol="EURUSD";
input double InpRiskPercent=0.25;
input double InpDailyLossLimitPercent=1.0;
input double InpWeeklyLossLimitPercent=2.0;
input double InpBreakoutBufferAtr=0.00;
input double InpTargetR=1.00;
input double InpMaxSpreadPips=2.0;
input int InpDeviationPoints=10;
input ulong InpMagic=26080706;

CTrade trade;
int hAtr=INVALID_HANDLE;
datetime lastM15Bar=0;
int consumedDayKey=0;
int equityDayKey=0,equityWeekKey=0;
double dayStartEquity=0.0,weekStartEquity=0.0;

int DateKey(datetime t){MqlDateTime d;TimeToStruct(t,d);return d.year*10000+d.mon*100+d.day;}
int WeekKey(datetime t){MqlDateTime d;TimeToStruct(t,d);datetime monday=t-(d.day_of_week==0?6:d.day_of_week-1)*86400;return DateKey(monday);}
datetime ToUtc(datetime serverTime){long offset=(long)(TimeTradeServer()-TimeGMT());return (datetime)((long)serverTime-offset);}
double PipSize(){int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);return (digits==3||digits==5)?10.0*p:p;}
bool HasOurPosition(){if(!PositionSelect(InpSymbol))return false;return (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;}
bool SpreadAllowed(){MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return false;return (t.ask-t.bid)<=InpMaxSpreadPips*PipSize();}

void RefreshLossAnchors(datetime utc){int d=DateKey(utc),w=WeekKey(utc);double e=AccountInfoDouble(ACCOUNT_EQUITY);if(d!=equityDayKey||dayStartEquity<=0){equityDayKey=d;dayStartEquity=e;}if(w!=equityWeekKey||weekStartEquity<=0){equityWeekKey=w;weekStartEquity=e;}}
bool LossLimitsAllow(datetime utc){RefreshLossAnchors(utc);double e=AccountInfoDouble(ACCOUNT_EQUITY);if(dayStartEquity>0&&e<=dayStartEquity*(1.0-InpDailyLossLimitPercent/100.0))return false;if(weekStartEquity>0&&e<=weekStartEquity*(1.0-InpWeeklyLossLimitPercent/100.0))return false;return true;}

bool OpeningRangeForDay(int dayKey,double &hi,double &lo,double &atrRef)
{
   hi=-DBL_MAX;lo=DBL_MAX;atrRef=0.0;
   bool seen[8];for(int i=0;i<8;i++)seen[i]=false;int count=0,refShift=-1;
   int bars=Bars(InpSymbol,PERIOD_M15);int maxShift=MathMin(bars-1,400);
   for(int sh=1;sh<=maxShift;sh++)
   {
      datetime bt=iTime(InpSymbol,PERIOD_M15,sh);if(bt<=0)continue;datetime utc=ToUtc(bt);int key=DateKey(utc);
      if(key>dayKey)continue;if(key<dayKey&&count>0)break;if(key!=dayKey)continue;
      MqlDateTime d;TimeToStruct(utc,d);int slot=-1;
      if(d.hour==6)slot=d.min/15;else if(d.hour==7)slot=4+d.min/15;else continue;
      if(slot<0||slot>7||seen[slot])continue;
      double h=iHigh(InpSymbol,PERIOD_M15,sh),l=iLow(InpSymbol,PERIOD_M15,sh);if(h<=0||l<=0||h<=l)return false;
      seen[slot]=true;count++;hi=MathMax(hi,h);lo=MathMin(lo,l);if(slot==7)refShift=sh;
   }
   if(count!=8||hi<=lo||refShift<1)return false;
   double b[1];if(CopyBuffer(hAtr,0,refShift,1,b)!=1||b[0]<=0)return false;atrRef=b[0];return true;
}

bool SignalWindow(datetime utc){MqlDateTime d;TimeToStruct(utc,d);if(d.day_of_week==0||d.day_of_week==6)return false;int mins=d.hour*60+d.min;return mins>=480&&mins<=825;}

void ForceFlat(datetime utc){if(!HasOurPosition())return;MqlDateTime d;TimeToStruct(utc,d);if(d.hour>=20||d.day_of_week==0||d.day_of_week==6)trade.PositionClose(InpSymbol,InpDeviationPoints);}

double NormalizeVolume(double v){double minV=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN),maxV=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX),step=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);if(step<=0||v<minV)return 0;v=MathFloor(v/step)*step;if(v<minV||v>maxV)return 0;return NormalizeDouble(v,2);}
double VolumeForRisk(ENUM_ORDER_TYPE type,double entry,double stop){double money=AccountInfoDouble(ACCOUNT_EQUITY)*(InpRiskPercent/100.0),loss=0;if(!OrderCalcProfit(type,InpSymbol,1.0,entry,stop,loss))return 0;loss=MathAbs(loss);if(loss<=0)return 0;return NormalizeVolume(money/loss);}
bool StopsValid(double entry,double sl,double tp){double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);double minD=(double)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL)*p;if(MathAbs(entry-sl)<minD||MathAbs(tp-entry)<minD)return false;return true;}

void EvaluateEntry(datetime utcNow)
{
   if(HasOurPosition()||!LossLimitsAllow(utcNow))return;
   datetime sigServer=iTime(InpSymbol,PERIOD_M15,1);if(sigServer<=0)return;datetime sigUtc=ToUtc(sigServer);if(!SignalWindow(sigUtc))return;
   int dayKey=DateKey(sigUtc);if(consumedDayKey==dayKey)return;
   double orH=0,orL=0,atr=0;if(!OpeningRangeForDay(dayKey,orH,orL,atr))return;
   double o=iOpen(InpSymbol,PERIOD_M15,1),c=iClose(InpSymbol,PERIOD_M15,1);if(o<=0||c<=0)return;
   double buf=InpBreakoutBufferAtr*atr;int dir=0;if(c>orH+buf&&c>o)dir=1;else if(c<orL-buf&&c<o)dir=-1;if(dir==0)return;
   consumedDayKey=dayKey;if(!SpreadAllowed())return;
   MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return;int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);trade.SetExpertMagicNumber(InpMagic);trade.SetDeviationInPoints(InpDeviationPoints);
   if(dir>0){double entry=t.ask,sl=NormalizeDouble(orL,digits);if(sl>=entry)return;double risk=entry-sl,tp=NormalizeDouble(entry+InpTargetR*risk,digits);double v=VolumeForRisk(ORDER_TYPE_BUY,entry,sl);if(v>0&&StopsValid(entry,sl,tp))trade.Buy(v,InpSymbol,0,sl,tp,"ARCH_F");}
   else{double entry=t.bid,sl=NormalizeDouble(orH,digits);if(sl<=entry)return;double risk=sl-entry,tp=NormalizeDouble(entry-InpTargetR*risk,digits);double v=VolumeForRisk(ORDER_TYPE_SELL,entry,sl);if(v>0&&StopsValid(entry,sl,tp))trade.Sell(v,InpSymbol,0,sl,tp,"ARCH_F");}
}

int OnInit(){if(!SymbolSelect(InpSymbol,true))return INIT_FAILED;hAtr=iATR(InpSymbol,PERIOD_M15,14);if(hAtr==INVALID_HANDLE)return INIT_FAILED;trade.SetExpertMagicNumber(InpMagic);RefreshLossAnchors(ToUtc(TimeTradeServer()));return INIT_SUCCEEDED;}
void OnDeinit(const int reason){if(hAtr!=INVALID_HANDLE)IndicatorRelease(hAtr);}
void OnTick(){datetime utc=ToUtc(TimeTradeServer());RefreshLossAnchors(utc);ForceFlat(utc);datetime cur=iTime(InpSymbol,PERIOD_M15,0);if(cur<=0||cur==lastM15Bar)return;lastM15Bar=cur;EvaluateEntry(utc);}
