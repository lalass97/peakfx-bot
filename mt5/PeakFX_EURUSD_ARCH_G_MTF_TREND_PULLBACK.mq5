#property strict
#property version "1.00"
#include <Trade/Trade.mqh>

input string InpSymbol="EURUSD";
input double InpRiskPercent=0.25;
input double InpDailyLossLimitPercent=1.0;
input double InpWeeklyLossLimitPercent=2.0;
input double InpH4SeparationAtr=0.10;
input double InpTargetR=1.25;
input double InpStopAtrBuffer=0.25;
input double InpMaxSpreadPips=2.0;
input int InpDeviationPoints=10;
input ulong InpMagic=26080707;

CTrade trade;
int hH4Fast=INVALID_HANDLE,hH4Slow=INVALID_HANDLE,hH4Atr=INVALID_HANDLE,hH1Ema=INVALID_HANDLE,hH1Atr=INVALID_HANDLE;
datetime lastH1=0; int consumedDay=0,dayKeyAnchor=0,weekKeyAnchor=0; double dayEq=0,weekEq=0;

int DateKey(datetime t){MqlDateTime d;TimeToStruct(t,d);return d.year*10000+d.mon*100+d.day;}
int WeekKey(datetime t){MqlDateTime d;TimeToStruct(t,d);datetime m=t-(d.day_of_week==0?6:d.day_of_week-1)*86400;return DateKey(m);}
datetime ToUtc(datetime t){long o=(long)(TimeTradeServer()-TimeGMT());return (datetime)((long)t-o);}
double Pip(){int d=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);return (d==3||d==5)?10*p:p;}
bool SpreadOK(){MqlTick x;if(!SymbolInfoTick(InpSymbol,x))return false;return x.ask-x.bid<=InpMaxSpreadPips*Pip();}
bool OurPos(){return PositionSelect(InpSymbol)&&(ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;}
bool Buf(int h,int sh,double &v){double a[1];if(CopyBuffer(h,0,sh,1,a)!=1)return false;v=a[0];return MathIsValidNumber(v)&&v>0;}
void Anchors(datetime u){int d=DateKey(u),w=WeekKey(u);double e=AccountInfoDouble(ACCOUNT_EQUITY);if(d!=dayKeyAnchor||dayEq<=0){dayKeyAnchor=d;dayEq=e;}if(w!=weekKeyAnchor||weekEq<=0){weekKeyAnchor=w;weekEq=e;}}
bool Limits(datetime u){Anchors(u);double e=AccountInfoDouble(ACCOUNT_EQUITY);return !(e<=dayEq*(1-InpDailyLossLimitPercent/100.0)||e<=weekEq*(1-InpWeeklyLossLimitPercent/100.0));}
double Vol(double v){double mn=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN),mx=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX),st=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);if(st<=0||v<mn)return 0;v=MathFloor(v/st)*st;if(v<mn||v>mx)return 0;return NormalizeDouble(v,2);}
double RiskVol(ENUM_ORDER_TYPE type,double e,double s){double money=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPercent/100.0,loss=0;if(!OrderCalcProfit(type,InpSymbol,1.0,e,s,loss))return 0;loss=MathAbs(loss);return loss>0?Vol(money/loss):0;}
bool Stops(double e,double s,double t){double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT),m=(double)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL)*p;return MathAbs(e-s)>=m&&MathAbs(t-e)>=m;}

int Trend(){double f,s,a,c=iClose(InpSymbol,PERIOD_H4,1);if(!Buf(hH4Fast,1,f)||!Buf(hH4Slow,1,s)||!Buf(hH4Atr,1,a)||c<=0)return 0;if(f>s&&c>f&&(f-s)>=InpH4SeparationAtr*a)return 1;if(f<s&&c<f&&(s-f)>=InpH4SeparationAtr*a)return -1;return 0;}
void ForceFlat(datetime u){if(!OurPos())return;MqlDateTime d;TimeToStruct(u,d);if((d.day_of_week==5&&d.hour>=20)||d.day_of_week==0||d.day_of_week==6)trade.PositionClose(InpSymbol,InpDeviationPoints);}
void Eval(datetime u){if(OurPos()||!Limits(u))return;MqlDateTime d;TimeToStruct(u,d);if(d.day_of_week==0||d.day_of_week==6||(d.day_of_week==5&&d.hour>=15))return;datetime sig=iTime(InpSymbol,PERIOD_H1,1);if(sig<=0)return;int dk=DateKey(ToUtc(sig));if(consumedDay==dk)return;int tr=Trend();if(tr==0)return;double ema,atr;if(!Buf(hH1Ema,1,ema)||!Buf(hH1Atr,1,atr))return;double o=iOpen(InpSymbol,PERIOD_H1,1),h=iHigh(InpSymbol,PERIOD_H1,1),l=iLow(InpSymbol,PERIOD_H1,1),c=iClose(InpSymbol,PERIOD_H1,1),pc=iClose(InpSymbol,PERIOD_H1,2);bool ok=(tr>0)?(l<=ema&&c>ema&&c>o&&c>pc):(h>=ema&&c<ema&&c<o&&c<pc);if(!ok)return;consumedDay=dk;if(!SpreadOK())return;MqlTick x;if(!SymbolInfoTick(InpSymbol,x))return;int dg=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);trade.SetExpertMagicNumber(InpMagic);trade.SetDeviationInPoints(InpDeviationPoints);if(tr>0){double e=x.ask,s=NormalizeDouble(l-InpStopAtrBuffer*atr,dg);if(s>=e)return;double r=e-s,t=NormalizeDouble(e+InpTargetR*r,dg),v=RiskVol(ORDER_TYPE_BUY,e,s);if(v>0&&Stops(e,s,t))trade.Buy(v,InpSymbol,0,s,t,"ARCH_G");}else{double e=x.bid,s=NormalizeDouble(h+InpStopAtrBuffer*atr,dg);if(s<=e)return;double r=s-e,t=NormalizeDouble(e-InpTargetR*r,dg),v=RiskVol(ORDER_TYPE_SELL,e,s);if(v>0&&Stops(e,s,t))trade.Sell(v,InpSymbol,0,s,t,"ARCH_G");}}

int OnInit(){if(!SymbolSelect(InpSymbol,true))return INIT_FAILED;hH4Fast=iMA(InpSymbol,PERIOD_H4,50,0,MODE_EMA,PRICE_CLOSE);hH4Slow=iMA(InpSymbol,PERIOD_H4,200,0,MODE_EMA,PRICE_CLOSE);hH4Atr=iATR(InpSymbol,PERIOD_H4,14);hH1Ema=iMA(InpSymbol,PERIOD_H1,20,0,MODE_EMA,PRICE_CLOSE);hH1Atr=iATR(InpSymbol,PERIOD_H1,14);if(hH4Fast==INVALID_HANDLE||hH4Slow==INVALID_HANDLE||hH4Atr==INVALID_HANDLE||hH1Ema==INVALID_HANDLE||hH1Atr==INVALID_HANDLE)return INIT_FAILED;trade.SetExpertMagicNumber(InpMagic);Anchors(ToUtc(TimeTradeServer()));return INIT_SUCCEEDED;}
void OnDeinit(const int r){if(hH4Fast!=INVALID_HANDLE)IndicatorRelease(hH4Fast);if(hH4Slow!=INVALID_HANDLE)IndicatorRelease(hH4Slow);if(hH4Atr!=INVALID_HANDLE)IndicatorRelease(hH4Atr);if(hH1Ema!=INVALID_HANDLE)IndicatorRelease(hH1Ema);if(hH1Atr!=INVALID_HANDLE)IndicatorRelease(hH1Atr);}
void OnTick(){datetime u=ToUtc(TimeTradeServer());Anchors(u);ForceFlat(u);datetime b=iTime(InpSymbol,PERIOD_H1,0);if(b<=0||b==lastH1)return;lastH1=b;Eval(u);}
