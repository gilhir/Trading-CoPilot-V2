"""
agents/short_term_parser.py — parsing, ולידציה ו-payload עבור short_term.
אחריות: עיבוד תשובות מהמודל בלבד. אין API calls, אין DB.
"""
from __future__ import annotations
import json as _json


def parse_initial_response(raw: str) -> dict:
    """
    מנסה לפרסר JSON מתשובת המודל.
    אם נכשל — הטקסט הוא תשובה נרטיבית תקינה (פורמט 6 חוקים).
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()

    if "NEED_BETTER_CHART" in cleaned:
        return {"status": "NEED_BETTER_CHART"}

    try:
        result = _json.loads(cleaned)
        if "status" not in result:
            result["status"] = "OK"
        result.setdefault("trade_type", "SHORT_TERM")
        _log_result(result)
        return result
    except _json.JSONDecodeError:
        _log_narrative(cleaned)
        return {
            "status":     "OK",
            "raw_text":   cleaned,
            "trade_type": "SHORT_TERM",
        }


def validate_for_save(result: dict) -> tuple[bool, list[str]]:
    """4 שדות חובה לפני שמירה ל-watchlist."""
    required = ["symbol", "trigger_price_zone", "stop_loss", "thesis_summary"]
    missing = [
        f for f in required
        if not result.get(f) or result.get(f) in (0.0, "", None)
    ]
    return (len(missing) == 0, missing)


def to_watchlist_payload(result: dict) -> dict:
    """ממיר תוצאת ניתוח לפורמט watchlist_setups."""
    score_note = result.get("narrative", "")
    return {
        "symbol":                    result.get("symbol", "").upper(),
        "required_setup_conditions": result.get("required_setup_conditions", score_note),
        "trigger_price_zone":        result.get("trigger_price_zone", 0.0),
        "current_status":            "Pending Alert",
        "stop_loss":                 result.get("stop_loss", 0.0),
        "thesis_summary":            result.get("thesis_summary", ""),
        "activation_trigger_price":  0.0,
        "activation_trigger_time":   "",
        "dismissal_notes":           "",
        "trade_type":                "SHORT_TERM",
    }


# ─── עזר פנימי ───────────────────────────────────────────────────

def _log_result(result: dict) -> None:
    status = result.get("status", "?")
    symbol = result.get("symbol", "לא זוהה")
    risk   = " ⚠️ HIGH RISK" if result.get("high_risk") else ""
    print(f"[short_term] status={status} | symbol={symbol}{risk}")
    if result.get("missing_fields"):
        print(f"[short_term] חסרים: {result['missing_fields']}")


def _log_narrative(text: str) -> None:
    preview = text[:80].replace("\n", " ")
    print(f"[short_term] תשובה נרטיבית | {preview}...")
