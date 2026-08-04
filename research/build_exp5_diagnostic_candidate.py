from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


GLOBALS_ANCHOR = re.compile(r"(?m)^PullbackSetup\s+g_setup;\s*$")
LONG_ER_GATE = re.compile(
    r"if\(!EfficiencyGatePasses\(shift\)\)\s*\r?\n\s*return\(false\);",
    re.MULTILINE,
)
SHORT_ER_GATE = LONG_ER_GATE
PROCESS_ANCHOR = re.compile(r"(?m)^void\s+ProcessCompletedBar\(\)\s*\r?\n\s*\{")
NO_SETUP_ANCHOR = re.compile(
    r"(?m)^(\s*if\(g_setup\.state\s*==\s*STATE_NONE\)\s*\r?\n\s*\{)"
)
TRIGGER_FALSE_ANCHOR = re.compile(
    r"(?m)^(\s*bool triggered = isLongSetup \? LongTriggerCondition\(shift\) : ShortTriggerCondition\(shift\);\s*)$"
)
BLOCK_ANCHOR = re.compile(
    r"(?m)^(\s*else\s*\r?\n\s*LogEvent\(\"trigger_fired_no_entry\",blockReason\);)"
)
INVALIDATED_ANCHOR = re.compile(r'(?m)^(\s*LogEvent\("setup_invalidated", isLongSetup\?"long":"short"\);)')
REPLACED_ANCHOR = re.compile(r'(?m)^(\s*LogEvent\("pullback_replaced", isLongSetup\?"long":"short"\);)')
EXPIRED_ANCHOR = re.compile(r'(?m)^(\s*LogEvent\("setup_expired", isLongSetup\?"long":"short"\);)')
ENTRY_LONG_ANCHOR = re.compile(r'(?m)^(\s*LogEvent\(isLong\?"entry_long":"entry_short","retcode="\+IntegerToString\(\(int\)retcode\)\);)')
DEINIT_ANCHOR = re.compile(r"(?m)^(void\s+OnDeinit\(const int reason\)\s*\r?\n\s*\{)")

DIAGNOSTIC_GLOBALS = r'''

// EXP5 diagnostic-only counters. These do not alter any trading decision.
long g_diag_bars_processed = 0;
long g_diag_indicator_invalid = 0;
long g_diag_no_setup_no_trend = 0;
long g_diag_no_setup_uptrend_no_pullback = 0;
long g_diag_no_setup_downtrend_no_pullback = 0;
long g_diag_pullback_new_long = 0;
long g_diag_pullback_new_short = 0;
long g_diag_er_reject_long = 0;
long g_diag_er_reject_short = 0;
long g_diag_trigger_not_reached = 0;
long g_diag_trigger_fired = 0;
long g_diag_block_existing_position = 0;
long g_diag_block_daily_trade_count = 0;
long g_diag_block_cooldown = 0;
long g_diag_block_session_hours = 0;
long g_diag_block_spread = 0;
long g_diag_block_risk_limit = 0;
long g_diag_block_other = 0;
long g_diag_setup_invalidated = 0;
long g_diag_pullback_replaced = 0;
long g_diag_setup_expired = 0;
long g_diag_entries = 0;

void DiagnosticCountBlock(const string reason)
  {
   if(reason=="existing_position") g_diag_block_existing_position++;
   else if(reason=="daily_trade_count") g_diag_block_daily_trade_count++;
   else if(reason=="cooldown") g_diag_block_cooldown++;
   else if(reason=="session_hours") g_diag_block_session_hours++;
   else if(reason=="spread") g_diag_block_spread++;
   else if(reason=="risk_limit") g_diag_block_risk_limit++;
   else g_diag_block_other++;
  }

void WriteDiagnosticSummary()
  {
   string path = "PeakFX\\exp5_diagnostic_summary.csv";
   FolderCreate("PeakFX", FILE_COMMON);
   int handle = FileOpen(path, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
   if(handle==INVALID_HANDLE)
     {
      Print("EXP5 diagnostic summary could not be opened: ",GetLastError());
      return;
     }
   FileWrite(handle,"metric","count");
   FileWrite(handle,"bars_processed",g_diag_bars_processed);
   FileWrite(handle,"indicator_invalid",g_diag_indicator_invalid);
   FileWrite(handle,"no_setup_no_trend",g_diag_no_setup_no_trend);
   FileWrite(handle,"no_setup_uptrend_no_pullback",g_diag_no_setup_uptrend_no_pullback);
   FileWrite(handle,"no_setup_downtrend_no_pullback",g_diag_no_setup_downtrend_no_pullback);
   FileWrite(handle,"pullback_new_long",g_diag_pullback_new_long);
   FileWrite(handle,"pullback_new_short",g_diag_pullback_new_short);
   FileWrite(handle,"er_reject_long",g_diag_er_reject_long);
   FileWrite(handle,"er_reject_short",g_diag_er_reject_short);
   FileWrite(handle,"trigger_not_reached",g_diag_trigger_not_reached);
   FileWrite(handle,"trigger_fired",g_diag_trigger_fired);
   FileWrite(handle,"block_existing_position",g_diag_block_existing_position);
   FileWrite(handle,"block_daily_trade_count",g_diag_block_daily_trade_count);
   FileWrite(handle,"block_cooldown",g_diag_block_cooldown);
   FileWrite(handle,"block_session_hours",g_diag_block_session_hours);
   FileWrite(handle,"block_spread",g_diag_block_spread);
   FileWrite(handle,"block_risk_limit",g_diag_block_risk_limit);
   FileWrite(handle,"block_other",g_diag_block_other);
   FileWrite(handle,"setup_invalidated",g_diag_setup_invalidated);
   FileWrite(handle,"pullback_replaced",g_diag_pullback_replaced);
   FileWrite(handle,"setup_expired",g_diag_setup_expired);
   FileWrite(handle,"entries",g_diag_entries);
   FileClose(handle);
  }
'''


def replace_once(source: str, pattern: re.Pattern[str], replacement: str, label: str) -> str:
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}, found {len(matches)}")
    return pattern.sub(replacement, source, count=1)


def build(source: str) -> str:
    candidate = replace_once(source, GLOBALS_ANCHOR, "PullbackSetup g_setup;" + DIAGNOSTIC_GLOBALS, "global anchor")

    er_matches = list(LONG_ER_GATE.finditer(candidate))
    if len(er_matches) != 2:
        raise ValueError(f"expected two ER gate calls, found {len(er_matches)}")
    candidate = LONG_ER_GATE.sub(
        lambda m, n=iter(("long", "short")): (
            "if(!EfficiencyGatePasses(shift))\n     {\n"
            f"      g_diag_er_reject_{next(n)}++;\n"
            "      return(false);\n     }"
        ),
        candidate,
        count=2,
    )

    candidate = replace_once(
        candidate,
        PROCESS_ANCHOR,
        "void ProcessCompletedBar()\n  {\n   g_diag_bars_processed++;",
        "ProcessCompletedBar anchor",
    )
    candidate = candidate.replace(
        'LogEvent("indicator_data_invalid","skipped_bar");',
        'g_diag_indicator_invalid++;\n      LogEvent("indicator_data_invalid","skipped_bar");',
        1,
    )

    no_setup_probe = r'''\1
      bool diagUptrend = UptrendCondition(shift);
      bool diagDowntrend = DowntrendCondition(shift);
      bool diagLongPullback = LongPullbackCondition(shift);
      bool diagShortPullback = ShortPullbackCondition(shift);
      if(!diagLongPullback && !diagShortPullback)
        {
         if(diagUptrend) g_diag_no_setup_uptrend_no_pullback++;
         else if(diagDowntrend) g_diag_no_setup_downtrend_no_pullback++;
         else g_diag_no_setup_no_trend++;
        }'''
    candidate = replace_once(candidate, NO_SETUP_ANCHOR, no_setup_probe, "no-setup anchor")
    candidate = candidate.replace("if(LongPullbackCondition(shift))", "if(diagLongPullback)", 1)
    candidate = candidate.replace("else if(ShortPullbackCondition(shift))", "else if(diagShortPullback)", 1)
    candidate = candidate.replace('LogEvent("pullback_new","long");', 'g_diag_pullback_new_long++;\n         LogEvent("pullback_new","long");', 1)
    candidate = candidate.replace('LogEvent("pullback_new","short");', 'g_diag_pullback_new_short++;\n         LogEvent("pullback_new","short");', 1)

    candidate = replace_once(
        candidate,
        TRIGGER_FALSE_ANCHOR,
        r'''\1
   if(triggered) g_diag_trigger_fired++;
   else g_diag_trigger_not_reached++;''',
        "trigger anchor",
    )
    candidate = replace_once(
        candidate,
        BLOCK_ANCHOR,
        r'''else
        {
         DiagnosticCountBlock(blockReason);
         LogEvent("trigger_fired_no_entry",blockReason);
        }''',
        "execution block anchor",
    )
    candidate = replace_once(candidate, INVALIDATED_ANCHOR, r'g_diag_setup_invalidated++;\n\1', "invalidation anchor")
    candidate = replace_once(candidate, REPLACED_ANCHOR, r'g_diag_pullback_replaced++;\n\1', "replacement anchor")
    candidate = replace_once(candidate, EXPIRED_ANCHOR, r'g_diag_setup_expired++;\n\1', "expiry anchor")
    candidate = replace_once(candidate, ENTRY_LONG_ANCHOR, r'g_diag_entries++;\n\1', "entry anchor")
    candidate = replace_once(candidate, DEINIT_ANCHOR, r'\1\n   WriteDiagnosticSummary();', "OnDeinit anchor")

    candidate = candidate.replace('"1.46"', '"1.47"', 1)
    required = (
        "MinimumEfficiencyRatio        = 0.35;",
        "0.20*atr",
        "WriteDiagnosticSummary();",
        "g_diag_er_reject_long",
        "g_diag_block_session_hours",
    )
    for marker in required:
        if marker not in candidate:
            raise ValueError(f"diagnostic candidate missing marker: {marker}")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Add diagnostic-only rejection telemetry to EXP3A")
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        source = Path(args.source).read_text(encoding="utf-8-sig")
        candidate = build(source)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(candidate, encoding="utf-8", newline="\n")
        print(f"EXP5 diagnostic candidate written: {output}")
        return 0
    except Exception as exc:
        print(f"EXP5_DIAGNOSTIC_BUILDER_ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
