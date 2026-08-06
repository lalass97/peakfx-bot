from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

THRESHOLD = "0.50"


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    sample = raw[:4096]
    if sample and sample[1::2].count(0) / max(1, len(sample)//2) > 0.2:
        return raw.decode("utf-16-le")
    return raw.decode("utf-8")


def replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}, found {len(matches)}")
    return re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE)


def build(source: str) -> str:
    candidate = source

    # Metadata-only changes.
    candidate = re.sub(r'(?m)^(\s*#property\s+version\s+)"[^"]+"', r'\1"1.50"', candidate, count=1)
    candidate = candidate.replace("PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5", "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP8_PULLBACK_DEPTH.mq5")
    candidate = candidate.replace("peakfx_confirmed_breakout_exp2_events.csv", "peakfx_exp8_pullback_depth_events.csv")
    candidate = candidate.replace("26073025", "26073031", 1)

    # Single isolated hypothesis: redefine a valid pullback candle by requiring
    # wick intrusion of at least 0.50 ATR beyond EMA12. Because the same pullback
    # functions are reused for initial and replacement pullbacks, this criterion
    # intentionally governs both call sites.
    long_pat = r'(?m)^(\s*return\s+[^;]*c\s*<=\s*ema12[^;]*;\s*)$'
    short_pat = r'(?m)^(\s*return\s+[^;]*c\s*>=\s*ema12[^;]*;\s*)$'

    long_matches = list(re.finditer(long_pat, candidate))
    short_matches = list(re.finditer(short_pat, candidate))
    if len(long_matches) != 1 or len(short_matches) != 1:
        raise ValueError(f"pullback return markers not unique: long={len(long_matches)} short={len(short_matches)}")

    long_line = long_matches[0].group(1)
    short_line = short_matches[0].group(1)
    long_expr = long_line.rstrip().rstrip(';') + f" && ((ema12-l)/atr >= {THRESHOLD});"
    short_expr = short_line.rstrip().rstrip(';') + f" && ((h-ema12)/atr >= {THRESHOLD});"
    candidate = candidate.replace(long_line, long_expr, 1)
    candidate = candidate.replace(short_line, short_expr, 1)

    required = [
        f"((ema12-l)/atr >= {THRESHOLD})",
        f"((h-ema12)/atr >= {THRESHOLD})",
        "peakfx_exp8_pullback_depth_events.csv",
        "26073031",
    ]
    for marker in required:
        if candidate.count(marker) != 1:
            raise ValueError(f"candidate validation failed for {marker}")
    return candidate


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("output")
    args = p.parse_args()
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
