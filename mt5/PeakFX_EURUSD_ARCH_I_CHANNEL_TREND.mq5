#property strict
#property version "1.01"
#include <Trade/Trade.mqh>
input string InpSymbol="EURUSD";
input int InpEntryChannel=20;
input bool InpFixed2R=true;
input double InpRiskPercent=0.25;
input double InpDailyLossLimitPercent=1.0;
input double InpWeeklyLossLimitPercent=2.0;
input double InpAtrStopMultiple=1.50;
input double InpMaxSpreadPips=2.0;
input int InpDeviationPoints=10;
input ulong InpMagic=26080709;
CTrade trade;
int h4ema=INVALID_HANDLE,h1atr=INVALID_HANDLE; datetime lastH1=0; int dayKey=0,weekKey=0; double dayEq=0,weekEq=0;
int DateKey(datetime t){MqlDateTime d;TimeToStruct(t,d);return d.year*10000+d.mon*100+d.day;}
int WeekKey(datetime t){MqlDateTime d;TimeToStruct(t,d);datetime mon=t-(d.day_of_week==0?6:d.day_of_week-1)*86400;return DateKey(mon);}
void RefreshAnchors(){datetime t=TimeGMT();int dk=DateKey(t),wk=WeekKey(t);double e=AccountInfoDouble(ACCOUNT_EQUITY);if(dk!=dayKey||dayEq<=0){dayKey=dk;dayEq=e;}if(wk!=weekKey||weekEq<=0){weekKey=wk;weekEq=e;}}
bool LossLimitsOK(){RefreshAnchors();double e=AccountInfoDouble(ACCOUNT_EQUITY);return !(e<=dayEq*(1.0-InpDailyLossLimitPercent/100.0)||e<=weekEq*(1.0-InpWeeklyLossLimitPercent/100.0));}
double Pip(){int d=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);return (d==3||d==5)?10*p:p;}
bool SpreadOK(){MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return false;return (t.ask-t.bid)<=InpMaxSpreadPips*Pip();}
bool StopsOK(double e,double sl,double tp){double point=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);double minD=(double)SymbolInfoInteger(InpSymbol,SYMBOL_TRADE_STOPS_LEVEL)*point;if(MathAbs(e-sl)<minD)return false;if(tp>0&&MathAbs(tp-e)<minD)return false;return true;}
bool OurPos(){return PositionSelect(InpSymbol)&&(ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;}
bool CopyOne(int h,int shift,double &v){double b[];ArraySetAsSeries(b,true);if(CopyBuffer(h,0,shift,1,b)!=1)return false;v=b[0];return MathIsValidNumber(v);}
bool H4Trend(int &dir){dir=0;double ema;if(!CopyOne(h4ema,1,ema))return false;double c=iClose(InpSymbol,PERIOD_H4,1);if(c>ema)dir=1;else if(c<ema)dir=-1;return dir!=0;}
bool Channel(int len,int start,double &hi,double &lo){hi=-DBL_MAX;lo=DBL_MAX;for(int s=start;s<start+len;s++){double h=iHigh(InpSymbol,PERIOD_H1,s),l=iLow(InpSymbol,PERIOD_H1,s);if(h<=0||l<=0||h<=l)return false;hi=MathMax(hi,h);lo=MathMin(lo,l);}return hi>lo;}
double NormVol(double v){double minv=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN),maxv=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX),st=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);if(st<=0)return 0;v=MathFloor(v/st)*st;if(v<minv||v>maxv)return 0;return NormalizeDouble(v,2);}
double VolForRisk(ENUM_ORDER_TYPE typ,double entry,double sl){double money=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPercent/100.0,loss=0;if(!OrderCalcProfit(typ,InpSymbol,1.0,entry,sl,loss))return 0;loss=MathAbs(loss);if(loss<=0)return 0;return NormVol(money/loss);}
void ManageChannelExit(){if(!OurPos()||InpFixed2R)return;long type=PositionGetInteger(POSITION_TYPE);double hi,lo;if(!Channel(10,2,hi,lo))return;double c=iClose(InpSymbol,PERIOD_H1,1);if(type==POSITION_TYPE_BUY&&c<lo)trade.PositionClose(InpSymbol,InpDeviationPoints);else if(type==POSITION_TYPE_SELL&&c>hi)trade.PositionClose(InpSymbol,InpDeviationPoints);}
void ForceFriday(){if(!OurPos())return;MqlDateTime d;TimeToStruct(TimeGMT(),d);if(d.day_of_week==5&&d.hour>=20)trade.PositionClose(InpSymbol,InpDeviationPoints);}
void Evaluate(){if(OurPos()||!SpreadOK()||!LossLimitsOK())return;MqlDateTime d;TimeToStruct(TimeGMT(),d);if(d.day_of_week==0||d.day_of_week==6||(d.day_of_week==5&&d.hour>=18))return;int tr;if(!H4Trend(tr))return;double hi,lo;if(!Channel(InpEntryChannel,2,hi,lo))return;double o=iOpen(InpSymbol,PERIOD_H1,1),c=iClose(InpSymbol,PERIOD_H1,1);int dir=0;if(tr>0&&c>hi&&c>o)dir=1;else if(tr<0&&c<lo&&c<o)dir=-1;if(dir==0)return;double atr;if(!CopyOne(h1atr,1,atr)||atr<=0)return;MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return;int digits=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);trade.SetExpertMagicNumber(InpMagic);trade.SetDeviationInPoints(InpDeviationPoints);if(dir>0){double e=t.ask,sl=NormalizeDouble(e-InpAtrStopMultiple*atr,digits),risk=e-sl,tp=InpFixed2R?NormalizeDouble(e+2.0*risk,digits):0;double v=VolForRisk(ORDER_TYPE_BUY,e,sl);if(v>0&&StopsOK(e,sl,tp))trade.Buy(v,InpSymbol,0,sl,tp,"ARCH_I");}else{double e=t.bid,sl=NormalizeDouble(e+InpAtrStopMultiple*atr,digits),risk=sl-e,tp=InpFixed2R?NormalizeDouble(e-2.0*risk,digits):0;double v=VolForRisk(ORDER_TYPE_SELL,e,sl);if(v>0&&StopsOK(e,sl,tp))trade.Sell(v,InpSymbol,0,sl,tp,"ARCH_I");}}
int OnInit(){if(!SymbolSelect(InpSymbol,true))return INIT_FAILED;h4ema=iMA(InpSymbol,PERIOD_H4,200,0,MODE_EMA,PRICE_CLOSE);h1atr=iATR(InpSymbol,PERIOD_H1,14);if(h4ema==INVALID_HANDLE||h1atr==INVALID_HANDLE)return INIT_FAILED;trade.SetExpertMagicNumber(InpMagic);RefreshAnchors();return INIT_SUCCEEDED;}
void OnDeinit(const int reason){if(h4ema!=INVALID_HANDLE)IndicatorRelease(h4ema);if(h1atr!=INVALID_HANDLE)IndicatorRelease(h1atr);}
void OnTick(){RefreshAnchors();ForceFriday();datetime b=iTime(InpSymbol,PERIOD_H1,0);if(b<=0||b==lastH1)return;lastH1=b;ManageChannelExit();Evaluate();}
