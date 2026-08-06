from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

THRESHOLD = "0.50"


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    sample = raw[:4096]
    if sample and sample[1::2].count(0) / max(1, len(sample) // 2) > 0.2:
        return raw.decode("utf-16-le")
    return raw.decode("utf-8")


def replace_function_body(source: str, name: str, old_body: str, new_body: str) -> str:
    pattern = re.compile(
        rf"bool\s+{re.escape(name)}\s*\(int\s+shift\)\s*\{{(?P<body>.*?)\n\s*\}}",
        flags=re.DOTALL,
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name} function, found {len(matches)}")
    body = matches[0].group("body")
    if body.strip() != old_body.strip():
        raise ValueError(f"unexpected {name} body; refusing non-isolated edit")
    replacement = f"bool {name}(int shift)\n  {{\n{new_body}\n  }}"
    return source[: matches[0].start()] + replacement + source[matches[0].end() :]


def build(source: str) -> str:
    candidate = source

    candidate = re.sub(
        r'(?m)^(\s*#property\s+version\s+)"[^"]+"',
        r'\1"1.50"',
        candidate,
        count=1,
    )
    candidate = candidate.replace(
        "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5",
        "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP8_PULLBACK_DEPTH.mq5",
    )
    candidate = candidate.replace(
        "peakfx_confirmed_breakout_exp2_events.csv",
        "peakfx_exp8_pullback_depth_events.csv",
    )
    candidate = candidate.replace("26073025", "26073031", 1)

    old_long = """   if(!UptrendCondition(shift))
      return(false);
   double f = GetIndicatorValue(hEmaFast,shift);
   double s = GetIndicatorValue(hEmaSlow,shift);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   return(c <= f && c >= s);"""
    new_long = f"""   if(!UptrendCondition(shift))
      return(false);
   double f = GetIndicatorValue(hEmaFast,shift);
   double s = GetIndicatorValue(hEmaSlow,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double l = iLow(InpSymbol,InpTimeframe,shift);
   if(!IsValidValue(atr) || atr <= 0.0)
      return(false);
   return(c <= f && c >= s && ((f-l)/atr >= {THRESHOLD}));"""

    old_short = """   if(!DowntrendCondition(shift))
      return(false);
   double f = GetIndicatorValue(hEmaFast,shift);
   double s = GetIndicatorValue(hEmaSlow,shift);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   return(c >= f && c <= s);"""
    new_short = f"""   if(!DowntrendCondition(shift))
      return(false);
   double f = GetIndicatorValue(hEmaFast,shift);
   double s = GetIndicatorValue(hEmaSlow,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double h = iHigh(InpSymbol,InpTimeframe,shift);
   if(!IsValidValue(atr) || atr <= 0.0)
      return(false);
   return(c >= f && c <= s && ((h-f)/atr >= {THRESHOLD}));"""

    candidate = replace_function_body(
        candidate, "LongPullbackCondition", old_long, new_long
    )
    candidate = replace_function_body(
        candidate, "ShortPullbackCondition", old_short, new_short
    )

    required = [
        f"((f-l)/atr >= {THRESHOLD})",
        f"((h-f)/atr >= {THRESHOLD})",
        "peakfx_exp8_pullback_depth_events.csv",
        "26073031",
    ]
    for marker in required:
        if candidate.count(marker) != 1:
            raise ValueError(f"candidate validation failed for {marker}")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        src_path = Path(args.source)
        out_path = Path(args.output)
        raw = src_path.read_bytes()
        print(f"EXP8 source sha256={hashlib.sha256(raw).hexdigest()}")
        candidate = build(read_text(src_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(candidate, encoding="utf-8", newline="\n")
        print(f"EXP8 output sha256={hashlib.sha256(out_path.read_bytes()).hexdigest()}")
        print(f"EXP8 candidate written: {out_path}")
        return 0
    except Exception as exc:
        print(f"EXP8_BUILDER_ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
