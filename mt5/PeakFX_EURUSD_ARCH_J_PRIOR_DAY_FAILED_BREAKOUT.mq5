#property strict
#property version "1.00"
#include <Trade/Trade.mqh>
input string InpSymbol="EURUSD";
input double InpExcursionFraction=0.05;
input bool InpMidpointTarget=true;
input double InpFixedTargetR=1.25;
input double InpStopBufferFraction=0.10;
input double InpRiskPercent=0.25;
input double InpMaxSpreadPips=2.0;
input int InpDeviationPoints=10;
input ulong InpMagic=26080710;
CTrade trade; datetime lastM15=0; int consumedDay=0;
int Key(datetime t){MqlDateTime d;TimeToStruct(t,d);return d.year*10000+d.mon*100+d.day;}
datetime ToUtc(datetime s){long off=(long)(TimeTradeServer()-TimeGMT());return (datetime)((long)s-off);}
double Pip(){int d=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);double p=SymbolInfoDouble(InpSymbol,SYMBOL_POINT);return (d==3||d==5)?10*p:p;}
bool SpreadOK(){MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return false;return (t.ask-t.bid)<=InpMaxSpreadPips*Pip();}
bool OurPos(){return PositionSelect(InpSymbol)&&(ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;}
bool PriorDay(datetime cur,double &o,double &h,double &l,double &c){datetime day=cur-(cur%86400)-86400;for(int a=0;a<7;a++,day-=86400){MqlDateTime dd;TimeToStruct(day,dd);if(dd.day_of_week==0||dd.day_of_week==6)continue;bool seen[96];for(int i=0;i<96;i++)seen[i]=false;int count=0;o=0;c=0;h=-DBL_MAX;l=DBL_MAX;for(int s=1;s<=2000;s++){datetime bt=iTime(InpSymbol,PERIOD_M15,s);if(bt<=0)continue;datetime u=ToUtc(bt);int k=Key(u);if(k<Key(day)&&count>0)break;if(k!=Key(day))continue;MqlDateTime x;TimeToStruct(u,x);int idx=x.hour*4+x.min/15;if(idx<0||idx>=96||seen[idx])continue;seen[idx]=true;count++;double bh=iHigh(InpSymbol,PERIOD_M15,s),bl=iLow(InpSymbol,PERIOD_M15,s);if(bh<=bl)return false;h=MathMax(h,bh);l=MathMin(l,bl);if(idx==0)o=iOpen(InpSymbol,PERIOD_M15,s);if(idx==95)c=iClose(InpSymbol,PERIOD_M15,s);}if(count==96&&o>0&&c>0&&h>l)return true;}return false;}
double NormVol(double v){double mn=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MIN),mx=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_MAX),st=SymbolInfoDouble(InpSymbol,SYMBOL_VOLUME_STEP);if(st<=0)return 0;v=MathFloor(v/st)*st;if(v<mn||v>mx)return 0;return NormalizeDouble(v,2);}
double Vol(ENUM_ORDER_TYPE typ,double e,double sl){double money=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPercent/100.0,loss=0;if(!OrderCalcProfit(typ,InpSymbol,1,e,sl,loss))return 0;loss=MathAbs(loss);return loss>0?NormVol(money/loss):0;}
void ForceFlat(datetime u){if(!OurPos())return;MqlDateTime d;TimeToStruct(u,d);if(d.hour>=20||d.day_of_week==0||d.day_of_week==6)trade.PositionClose(InpSymbol,InpDeviationPoints);}
void Eval(datetime u){if(OurPos())return;datetime ss=iTime(InpSymbol,PERIOD_M15,1);if(ss<=0)return;datetime su=ToUtc(ss);MqlDateTime d;TimeToStruct(su,d);if(d.day_of_week==0||d.day_of_week==6||d.hour<7||d.hour>15)return;int key=Key(su);if(consumedDay==key)return;double po,ph,pl,pc;if(!PriorDay(su,po,ph,pl,pc))return;double r=ph-pl,o=iOpen(InpSymbol,PERIOD_M15,1),h=iHigh(InpSymbol,PERIOD_M15,1),l=iLow(InpSymbol,PERIOD_M15,1),c=iClose(InpSymbol,PERIOD_M15,1);int dir=0;if(h>ph+InpExcursionFraction*r&&c<ph&&c<o)dir=-1;else if(l<pl-InpExcursionFraction*r&&c>pl&&c>o)dir=1;if(dir==0)return;consumedDay=key;if(!SpreadOK())return;MqlTick t;if(!SymbolInfoTick(InpSymbol,t))return;int dg=(int)SymbolInfoInteger(InpSymbol,SYMBOL_DIGITS);double mid=(ph+pl)/2.0;trade.SetExpertMagicNumber(InpMagic);trade.SetDeviationInPoints(InpDeviationPoints);if(dir<0){double e=t.bid,sl=NormalizeDouble(h+InpStopBufferFraction*r,dg);if(sl<=e)return;double rr=sl-e,tp=InpMidpointTarget?NormalizeDouble(mid,dg):NormalizeDouble(e-InpFixedTargetR*rr,dg);if(tp>=e)return;double v=Vol(ORDER_TYPE_SELL,e,sl);if(v>0)trade.Sell(v,InpSymbol,0,sl,tp,"ARCH_J");}else{double e=t.ask,sl=NormalizeDouble(l-InpStopBufferFraction*r,dg);if(sl>=e)return;double rr=e-sl,tp=InpMidpointTarget?NormalizeDouble(mid,dg):NormalizeDouble(e+InpFixedTargetR*rr,dg);if(tp<=e)return;double v=Vol(ORDER_TYPE_BUY,e,sl);if(v>0)trade.Buy(v,InpSymbol,0,sl,tp,"ARCH_J");}}
int OnInit(){if(!SymbolSelect(InpSymbol,true))return INIT_FAILED;trade.SetExpertMagicNumber(InpMagic);return INIT_SUCCEEDED;}
void OnTick(){datetime u=ToUtc(TimeTradeServer());ForceFlat(u);datetime b=iTime(InpSymbol,PERIOD_M15,0);if(b<=0||b==lastM15)return;lastM15=b;Eval(u);}
