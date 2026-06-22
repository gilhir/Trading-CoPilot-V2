"""
agents/short_term_drill_down.py — כללי Drill-Down לסוכן קצר הטווח.
אחריות: הגדרת מתי ואיזה גרף משלים לבקש. אין API, אין DB.
"""
from __future__ import annotations

# ─── בלוק פרומפט — מיובא ל-short_term_prompt.py ─────────────────

DRILL_DOWN_RULES = """## חוקי תחקור לעומק (Drill-Down) — מתי לבקש גרף משלים:

טריגר אוטומטי — הפעל Drill-Down בכל אחד מהתנאים הבאים:

1. גרף 65 דקות (REQUEST_65M):
   - נר יומי אחרון הוא Doji או Pinbar על רמת תמיכה/התנגדות קריטית
     ויש ספק: איסוף (Accumulation) או פיזור (Distribution)?
   - תזת המשתמש מתבססת על פריצה תוך-יומית שלא נראית ביומי.
   - ציון 6/6 אבל חוק 3 או 4 מוגדר ⚠️ ניטרלי — לא ניתן לאשר בביטחון.

2. ווליום מעוגן — Anchored VWAP (REQUEST_AVWAP):
   - קיים Gap פתוח מלפני פחות מ-20 יום + מחיר מדשדש ליד הפער.
   - מהלך מומנטום חריג + המחיר נעצר בלי תמיכה ברורה בגרף.

3. עוצמה יחסית — RS/SPY Overlay (REQUEST_RS_CONTEXT):
   - תבנית המניה נראית ניטרלית אך המשתמש טוען למומנטום חזק.
   - ציון 4/6 ומטה + תזת המשתמש חיובית — נדרש הוכחת עוצמה יחסית.

כאשר מופעל Drill-Down:
- הצג את הניתוח החלקי עם הציון הקיים.
- הסבר בדיוק מה חסר ולמה הנתון הספציפי נדרש.
- session נשאר פתוח — ממתין לגרף המשלים.
- לאחר קבלת הגרף המשלים: עדכן ניתוח + תזה סופית."""

# ─── פורמט JSON המורחב (כולל DRILL_DOWN) ────────────────────────

DRILL_DOWN_JSON = """{
  "status": "CONFIRMED" | "CLOSE" | "DRILL_DOWN_REQUIRED",
  "requested_action": "NONE" | "REQUEST_65M" | "REQUEST_AVWAP" | "REQUEST_RS_CONTEXT",
  "drill_down_rationale": "הסבר למשתמש למה הגרף הנוסף נדרש",
  "symbol": "TICKER",
  "trigger_price_zone": 0.0,
  "stop_loss": 0.0,
  "thesis_summary": "תזה סופית / חלקית",
  "required_setup_conditions": "חוקים שהתקיימו: ...",
  "trade_type": "SHORT_TERM",
  "narrative": "ציון X/6 — תיקוף: ...",
  "high_risk": false
}"""

# ─── פרסור תוצאת Drill-Down ──────────────────────────────────────

_ACTION_LABELS = {
    "REQUEST_65M":        "גרף 65 דקות",
    "REQUEST_AVWAP":      "Anchored VWAP / Volume Profile",
    "REQUEST_RS_CONTEXT": "עוצמה יחסית ביחס ל-SPY",
    "NONE":               None,
}


def parse_drill_down(result: dict) -> dict:
    """
    מחלץ מידע Drill-Down מתוצאת ניתוח.
    מחזיר dict עם: required (bool), action, label, rationale, response_text.
    """
    if result.get("status") != "DRILL_DOWN_REQUIRED":
        return {"required": False}

    action    = result.get("requested_action", "NONE")
    rationale = result.get("drill_down_rationale", "נדרש מידע נוסף")
    label     = _ACTION_LABELS.get(action, action)

    lines = [
        f"⏳ **נדרש תחקור לעומק לפני אישור**",
        f"",
        f"📊 **בקשה:** {label}" if label else "",
        f"💡 **סיבה:** {rationale}",
        f"",
        f"אנא שלח את הגרף המבוקש — התחקיר ממשיך לאחר קבלתו.",
    ]

    return {
        "required":      True,
        "action":        action,
        "label":         label,
        "rationale":     rationale,
        "response_text": "\n".join(l for l in lines if l is not None),
    }


def format_drill_down_response(result: dict) -> str:
    """בונה תשובת טקסט מלאה לבקשת Drill-Down."""
    dd = parse_drill_down(result)
    if not dd["required"]:
        return ""

    symbol    = result.get("symbol", "?")
    narrative = result.get("narrative", "")

    header = f"**{symbol}** — ניתוח חלקי\n\n{narrative}\n\n" if narrative else ""
    return header + dd["response_text"]
