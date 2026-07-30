from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def export_bars(symbol: str, start: datetime, end: datetime, output: Path) -> int:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit(
            "MetaTrader5 is not installed. On Windows run: pip install -r requirements-mt5.txt"
        ) from exc

    if not mt5.initialize():
        code, message = mt5.last_error()
        raise RuntimeError(f"MT5 initialize failed: {code} {message}")

    try:
        if not mt5.symbol_select(symbol, True):
            code, message = mt5.last_error()
            raise RuntimeError(f"Could not select {symbol}: {code} {message}")

        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start, end)
        if rates is None or len(rates) == 0:
            code, message = mt5.last_error()
            raise RuntimeError(f"No H1 rates returned for {symbol}: {code} {message}")

        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        columns = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
        frame = frame[columns].sort_values("time").drop_duplicates("time")
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)
        return len(frame)
    finally:
        mt5.shutdown()


def utc_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export broker EURUSD H1 bars from MetaTrader 5")
    parser.add_argument("--symbol", default="EURUSD", help="Broker symbol, for example EURUSD or EURUSD.a")
    parser.add_argument("--start", required=True, type=utc_date, help="ISO date/time interpreted as UTC")
    parser.add_argument("--end", required=True, type=utc_date, help="ISO date/time interpreted as UTC")
    parser.add_argument("--output", type=Path, default=Path("data/private/EURUSD_H1.csv"))
    args = parser.parse_args()
    if args.end <= args.start:
        parser.error("--end must be after --start")
    count = export_bars(args.symbol, args.start, args.end, args.output)
    print(f"Exported {count:,} {args.symbol} H1 bars to {args.output}")


if __name__ == "__main__":
    main()
