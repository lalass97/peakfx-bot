from pathlib import Path


SOURCE = Path("mt5/PeakFX_QualificationTelemetry.mqh")


def _text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_exact_qualification_headers_are_present():
    text = _text()
    assert '"closed_at","net_pnl","r_multiple","side"' in text
    assert (
        '"timestamp","balance","equity","margin_used",\n'
        '                   "gross_exposure","open_positions"'
    ) in text


def test_module_is_append_only_and_contains_no_trade_submission_api():
    text = _text()
    forbidden = (
        "CTrade",
        ".Buy(",
        ".Sell(",
        "OrderSend(",
        "OrderDelete(",
        "PositionClose(",
        "PositionModify(",
        "trade.Buy",
        "trade.Sell",
    )
    assert all(token not in text for token in forbidden)


def test_evidence_is_flushed_after_each_append():
    text = _text()
    assert text.count("FileFlush(m_trade_handle)") >= 2
    assert text.count("FileFlush(m_snapshot_handle)") >= 2


def test_invalid_or_unsafe_values_fail_closed():
    text = _text()
    assert "MathIsValidNumber(net_pnl)" in text
    assert "MathIsValidNumber(r_multiple)" in text
    assert "balance<=0.0" in text
    assert "equity<0.0" in text
    assert "margin_used<0.0" in text
    assert "gross_exposure<0.0" in text
    assert "open_positions<0" in text


def test_side_is_restricted_to_long_or_short():
    text = _text()
    assert 'normalized!="long" && normalized!="short"' in text


def test_integration_document_explicitly_blocks_behavior_changes():
    doc = Path("docs/MT5_QUALIFICATION_TELEMETRY.md").read_text(encoding="utf-8")
    assert "does not calculate signals" in doc
    assert "not yet inserted into the recovered v1.42 EA" in doc
    assert "No manual editing, sorting, deduplication" in doc
