import json

from research.run_qualification import (
    EXIT_GREEN,
    EXIT_INVALID_INPUT,
    EXIT_RED,
    main,
)


def _trade_csv(*, losing: bool = False) -> str:
    rows = ["closed_at,net_pnl,r_multiple,side"]
    for index in range(100):
        day = index % 28 + 1
        year = 2024 if index < 50 else 2025
        side = "long" if index % 2 == 0 else "short"
        if losing:
            pnl, r_value = (-20.0, -0.2) if index % 2 else (10.0, 0.1)
        else:
            pnl, r_value = (20.0, 0.2) if index % 4 else (-10.0, -0.1)
        rows.append(
            f"{year}-{(index % 12) + 1:02d}-{day:02d}T10:00:00+00:00,"
            f"{pnl},{r_value},{side}"
        )
    rows[1:] = sorted(rows[1:])
    return "\n".join(rows) + "\n"


def _snapshot_csv(*, unsafe: bool = False) -> str:
    rows = ["timestamp,balance,equity,margin_used,gross_exposure,open_positions"]
    for index in range(100):
        day = index % 28 + 1
        month = index % 12 + 1
        equity = 8000 if unsafe and index == 50 else 9950
        positions = 3 if unsafe and index == 50 else 1
        rows.append(
            f"2025-{month:02d}-{day:02d}T{index % 24:02d}:00:00+00:00,"
            f"10000,{equity},1000,5000,{positions}"
        )
    rows[1:] = sorted(rows[1:])
    return "\n".join(rows) + "\n"


def test_cli_writes_deterministic_green_report(tmp_path, capsys):
    trades = tmp_path / "trades.csv"
    snapshots = tmp_path / "snapshots.csv"
    output = tmp_path / "report.json"
    trades.write_text(_trade_csv(), encoding="utf-8")
    snapshots.write_text(_snapshot_csv(), encoding="utf-8")

    exit_code = main(
        ["--trades", str(trades), "--snapshots", str(snapshots), "--output", str(output)]
    )

    assert exit_code == EXIT_GREEN
    stdout = capsys.readouterr().out
    assert stdout == output.read_text(encoding="utf-8")
    payload = json.loads(stdout)
    assert payload["decision"] == "green"
    assert payload["failed_sections"] == []


def test_cli_returns_red_for_unsafe_open_equity(tmp_path, capsys):
    trades = tmp_path / "trades.csv"
    snapshots = tmp_path / "snapshots.csv"
    trades.write_text(_trade_csv(), encoding="utf-8")
    snapshots.write_text(_snapshot_csv(unsafe=True), encoding="utf-8")

    exit_code = main(["--trades", str(trades), "--snapshots", str(snapshots)])

    assert exit_code == EXIT_RED
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "red"
    assert payload["failed_sections"] == ["open_risk"]


def test_cli_rejects_malformed_input_without_report(tmp_path, capsys):
    trades = tmp_path / "trades.csv"
    snapshots = tmp_path / "snapshots.csv"
    trades.write_text("not,a,valid,export\n", encoding="utf-8")
    snapshots.write_text(_snapshot_csv(), encoding="utf-8")

    exit_code = main(["--trades", str(trades), "--snapshots", str(snapshots)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_INVALID_INPUT
    assert captured.out == ""
    assert "qualification input error" in captured.err


def test_cli_returns_red_for_unprofitable_completed_trades(tmp_path, capsys):
    trades = tmp_path / "trades.csv"
    snapshots = tmp_path / "snapshots.csv"
    trades.write_text(_trade_csv(losing=True), encoding="utf-8")
    snapshots.write_text(_snapshot_csv(), encoding="utf-8")

    exit_code = main(["--trades", str(trades), "--snapshots", str(snapshots)])

    assert exit_code == EXIT_RED
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "red"
    assert payload["failed_sections"] == ["profitability"]
