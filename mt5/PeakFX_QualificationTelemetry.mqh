#ifndef PEAKFX_QUALIFICATION_TELEMETRY_MQH
#define PEAKFX_QUALIFICATION_TELEMETRY_MQH

// Append-only research telemetry. This module never submits, modifies, or closes orders.
class CPeakFXQualificationTelemetry
  {
private:
   int               m_trade_handle;
   int               m_snapshot_handle;
   int               m_utc_offset_minutes;
   bool              m_ready;

   string FormatIso8601(const datetime value) const
     {
      MqlDateTime parts;
      TimeToStruct(value,parts);
      const int absolute_offset=MathAbs(m_utc_offset_minutes);
      const int offset_hours=absolute_offset/60;
      const int offset_minutes=absolute_offset%60;
      const string sign=(m_utc_offset_minutes>=0 ? "+" : "-");
      return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d%s%02d:%02d",
                          parts.year,parts.mon,parts.day,parts.hour,parts.min,parts.sec,
                          sign,offset_hours,offset_minutes);
     }

   bool WriteHeaders()
     {
      if(FileSize(m_trade_handle)==0)
         FileWrite(m_trade_handle,"closed_at","net_pnl","r_multiple","side");
      if(FileSize(m_snapshot_handle)==0)
         FileWrite(m_snapshot_handle,"timestamp","balance","equity","margin_used",
                   "gross_exposure","open_positions");
      FileFlush(m_trade_handle);
      FileFlush(m_snapshot_handle);
      return true;
     }

public:
                     CPeakFXQualificationTelemetry(void)
     {
      m_trade_handle=INVALID_HANDLE;
      m_snapshot_handle=INVALID_HANDLE;
      m_utc_offset_minutes=0;
      m_ready=false;
     }

                    ~CPeakFXQualificationTelemetry(void)
     {
      Close();
     }

   bool Open(const string run_id,const int utc_offset_minutes)
     {
      Close();
      if(StringLen(run_id)==0 || utc_offset_minutes < -14*60 || utc_offset_minutes > 14*60)
         return false;

      m_utc_offset_minutes=utc_offset_minutes;
      const string prefix="PeakFX_"+run_id+"_";
      m_trade_handle=FileOpen(prefix+"completed_trades.csv",
                              FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
      if(m_trade_handle==INVALID_HANDLE)
         return false;

      m_snapshot_handle=FileOpen(prefix+"open_equity_snapshots.csv",
                                 FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
      if(m_snapshot_handle==INVALID_HANDLE)
        {
         FileClose(m_trade_handle);
         m_trade_handle=INVALID_HANDLE;
         return false;
        }

      FileSeek(m_trade_handle,0,SEEK_END);
      FileSeek(m_snapshot_handle,0,SEEK_END);
      m_ready=WriteHeaders();
      return m_ready;
     }

   void Close(void)
     {
      if(m_trade_handle!=INVALID_HANDLE)
         FileClose(m_trade_handle);
      if(m_snapshot_handle!=INVALID_HANDLE)
         FileClose(m_snapshot_handle);
      m_trade_handle=INVALID_HANDLE;
      m_snapshot_handle=INVALID_HANDLE;
      m_ready=false;
     }

   bool IsReady(void) const
     {
      return m_ready;
     }

   bool AppendCompletedTrade(const datetime closed_at,
                             const double net_pnl,
                             const double r_multiple,
                             const string side)
     {
      if(!m_ready || !MathIsValidNumber(net_pnl) || !MathIsValidNumber(r_multiple))
         return false;
      string normalized=StringToLower(side);
      if(normalized!="long" && normalized!="short")
         return false;

      const uint written=FileWrite(m_trade_handle,FormatIso8601(closed_at),
                                   DoubleToString(net_pnl,8),
                                   DoubleToString(r_multiple,8),normalized);
      FileFlush(m_trade_handle);
      return written>0;
     }

   bool AppendSnapshot(const datetime timestamp,
                       const double balance,
                       const double equity,
                       const double margin_used,
                       const double gross_exposure,
                       const int open_positions)
     {
      if(!m_ready || !MathIsValidNumber(balance) || !MathIsValidNumber(equity) ||
         !MathIsValidNumber(margin_used) || !MathIsValidNumber(gross_exposure))
         return false;
      if(balance<=0.0 || equity<0.0 || margin_used<0.0 || gross_exposure<0.0 ||
         open_positions<0)
         return false;

      const uint written=FileWrite(m_snapshot_handle,FormatIso8601(timestamp),
                                   DoubleToString(balance,8),DoubleToString(equity,8),
                                   DoubleToString(margin_used,8),
                                   DoubleToString(gross_exposure,8),open_positions);
      FileFlush(m_snapshot_handle);
      return written>0;
     }
  };

#endif
