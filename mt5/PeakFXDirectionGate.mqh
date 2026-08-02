#ifndef PEAKFX_DIRECTION_GATE_MQH
#define PEAKFX_DIRECTION_GATE_MQH

enum ENUM_PEAKFX_DIRECTION_MODE
{
   PEAKFX_DIRECTION_BOTH = 0,
   PEAKFX_DIRECTION_LONG_ONLY = 1,
   PEAKFX_DIRECTION_SHORT_ONLY = 2
};

bool PeakFXDirectionAllowed(const ENUM_PEAKFX_DIRECTION_MODE mode, const bool is_long)
{
   if(mode == PEAKFX_DIRECTION_BOTH)
      return true;
   if(mode == PEAKFX_DIRECTION_LONG_ONLY)
      return is_long;
   if(mode == PEAKFX_DIRECTION_SHORT_ONLY)
      return !is_long;
   return false;
}

#endif
