#property strict
#property version   "1.00"
#property description "PeakFX Architecture H H1 statistical deviation reversion"
#include <Trade/Trade.mqh>

input string InpSymbol="EURUSD";
input double InpRiskPercent=0.25;
input double InpDailyLossLimitPercent=1.0;
input double InpWeeklyLossLimitPercent=2.0;
input double InpExtensionAtr=1.25;
input bool InpEmaTarget=true;
input double InpStopAtrBuffer=0.75;
input double InpFixedTargetR=1.0;
input double InpMaxSpreadPips=2.0;
input int InpDeviationPoints=10;
input ulong InpMagic=26080708;

CTrade trade;
int hEma=INVALID_HANDLE,hAtr=INVALID_HANDLE,hRsi=INVALID_HANDLE;
datetime lastH1Bar=0;
int consumedDayKey=0,equityDayKey=0,equityWeekKey=0;
double dayStartEquity=0,weekStartEquity=0;

int DateKey(datetime t){MqlDateTime d;TimeToStruct(t,d);return d.year*10000+d.mon*100+d.day;}
int WeekKey(datetime t){MqlDateTime d;TimeToStruct(t,d);datetime m=t-(d.day_of_week==0?6:d.day_of_week-1)*86400;return DateKey(m);}
datetime ToUtc(datetime serverTime){long off=(long)(TimeTradeServer()-TimeGMT());return (datetime)((long)serverTime-off);}
double PipSize(){int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);double pt=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);return (digits==3||digits==5)?10.0*pt:pt;}
bool HasOurPosition(){if(!PositionSelect(InpSymbol))return false;return (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;}
bool SpreadAllowed(){MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return false;return (t.ask-t.bid)<=InpMaxSpreadPips*PipSize();}
void RefreshLossAnchors(datetime u){int d=DateKey(u),w=WeekKey(u);double eq=AccountInfoDouble(ACCOUNT_EQUITY);if(d!=equityDayKey||dayStartEquity<=0){equityDayKey=d;dayStartEquity=eq;}if(w!=equityWeekKey||weekStartEquity<=0){equityWeekKey=w;weekStartEquity=eq;}}
bool LossLimitsAllowEntry(datetime u){RefreshLossAnchors(u);double eq=AccountInfoDouble(ACCOUNT_EQUITY);if(dayStartEquity>0&&eq<=dayStartEquity*(1.0-InpDailyLossLimitPercent/100.0))return false;if(weekStartEquity>0&&eq<=weekStartEquity*(1.0-InpWeeklyLossLimitPercent/100.0))return false;return true;}
bool Buf(int h,int sh,double &v){double b[1];if(CopyBuffer(h,0,sh,1,b)!=1)return false;v=b[0];return MathIsValidNumber(v);}
bool SignalWindow(datetime u){MqlDateTime d;TimeToStruct(u,d);if(d.day_of_week==0||d.day_of_week==6)return false;return d.hour>=7&&d.hour<=17;}
void ForceFlat(datetime u){if(!HasOurPosition())return;MqlDateTime d;TimeToStruct(u,d);if(d.hour>=20||d.day_of_week==0||d.day_of_week==6)trade.PositionClose(InpSymbol,InpDeviationPoints);}
double NormalizeVolume(double v){double mn=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN),mx=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX),st=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);if(st<=0||v<mn)return 0;v=MathFloor(v/st)*st;if(v<mn||v>mx)return 0;return NormalizeDouble(v,2);}
double VolumeForRisk(ENUM_ORDER_TYPE type,double entry,double stop){double risk=AccountInfoDouble(ACCOUNT_EQUITY)*(InpRiskPercent/100.0),one=0;if(!OrderCalcProfit(type,InpSymbol,1.0,entry,stop,one))return 0;one=MathAbs(one);if(one<=0)return 0;return NormalizeVolume(risk/one);}
bool StopsValid(double entry,double sl,double tp){double pt=SymbolInfoDouble(InpSymbol,SYMBOL_POINT),md=(double)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL)*pt;if(MathAbs(entry-sl)<md)return false;if(tp>0&&MathAbs(tp-entry)<md)return false;return true;}

void EvaluateEntry(datetime utcNow)
{
 if(HasOurPosition()||!LossLimitsAllowEntry(utcNow))return;
 datetime sigServer=iTime(InpSymbol,PERIOD_H1,1);if(sigServer<=0)return;datetime sigUtc=ToUtc(sigServer);if(!SignalWindow(sigUtc))return;
 int dk=DateKey(sigUtc);if(consumedDayKey==dk)return;
 double ema=0,atr=0,rsi=0;if(!Buf(hEma,1,ema)||!Buf(hAtr,1,atr)||!Buf(hRsi,1,rsi)||atr<=0)return;
 double o=iOpen(InpSymbol,PERIOD_H1,1),h=iHigh(InpSymbol,PERIOD_H1,1),l=iLow(InpSymbol,PERIOD_H1,1),c=iClose(InpSymbol,PERIOD_H1,1);if(o<=0||h<=l||c<=0)return;
 int dir=0;if(c>=ema+InpExtensionAtr*atr&&rsi>=70.0&&c<o)dir=-1;else if(c<=ema-InpExtensionAtr*atr&&rsi<=30.0&&c>o)dir=1;if(dir==0)return;
 consumedDayKey=dk;if(!SpreadAllowed())return;
 MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return;int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);trade.SetExpertMagicNumber(InpMagic);trade.SetDeviationInPoints(InpDeviationPoints);
 if(dir<0){double entry=t.bid,sl=NormalizeDouble(h+InpStopAtrBuffer*atr,digits);if(sl<=entry)return;double risk=sl-entry;double tp=InpEmaTarget?NormalizeDouble(ema,digits):NormalizeDouble(entry-InpFixedTargetR*risk,digits);if(tp>=entry)return;double vol=VolumeForRisk(ORDER_TYPE_SELL,entry,sl);if(vol>0&&StopsValid(entry,sl,tp))trade.Sell(vol,InpSymbol,0,sl,tp,"ARCH_H");}
 else {double entry=t.ask,sl=NormalizeDouble(l-InpStopAtrBuffer*atr,digits);if(sl>=entry)return;double risk=entry-sl;double tp=InpEmaTarget?NormalizeDouble(ema,digits):NormalizeDouble(entry+InpFixedTargetR*risk,digits);if(tp<=entry)return;double vol=VolumeForRisk(ORDER_TYPE_BUY,entry,sl);if(vol>0&&StopsValid(entry,sl,tp))trade.Buy(vol,InpSymbol,0,sl,tp,"ARCH_H");}
}

int OnInit(){if(!SymbolSelect(InpSymbol,true))return INIT_FAILED;hEma=iMA(InpSymbol,PERIOD_H1,20,0,MODE_EMA,PRICE_CLOSE);hAtr=iATR(InpSymbol,PERIOD_H1,14);hRsi=iRSI(InpSymbol,PERIOD_H1,14,PRICE_CLOSE);if(hEma==INVALID_HANDLE||hAtr==INVALID_HANDLE||hRsi==INVALID_HANDLE)return INIT_FAILED;trade.SetExpertMagicNumber(InpMagic);RefreshLossAnchors(ToUtc(TimeTradeServer()));return INIT_SUCCEEDED;}
void OnDeinit(const int reason){if(hEma!=INVALID_HANDLE)IndicatorRelease(hEma);if(hAtr!=INVALID_HANDLE)IndicatorRelease(hAtr);if(hRsi!=INVALID_HANDLE)IndicatorRelease(hRsi);}
void OnTick(){datetime u=ToUtc(TimeTradeServer());RefreshLossAnchors(u);ForceFlat(u);datetime cur=iTime(InpSymbol,PERIOD_H1,0);if(cur<=0||cur==lastH1Bar)return;lastH1Bar=cur;EvaluateEntry(u);}
