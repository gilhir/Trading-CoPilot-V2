"""
agents/chart_analyst.py — ניתוח גרפי TradingView (vision).
אחריות: קבלת תמונת גרף → ניתוח → הצעת watchlist_setup.
אין DB ישיר — מחזיר dict שה-caller שומר אם המשתמש אישר.

חוקי guardrail:
    1. התראת מחיר בלבד — לא Buy Stop
    2. סטופ = 1.5 × ATR מתחת לנקודת כשל
    3. מתחת MA_150 = HIGH RISK (מסמן, לא חוסם)
    4. גרף גרוע → עוצר, מחזיר NEED_BETTER_CHART
    5. 4 שדות חובה לפני שמירה: symbol, trigger_price_zone,
       stop_loss, thesis_summary
"""

from __future__ import annotations
from agents.client import generate

# ─── Prompt מערכת ────────────────────────────────────────────────
_SYSTEM = """אתה אנליסט טכני בכיר המנתח גרפי מניות.
עבוד תמיד בעברית מקצועית. אל תנחש — אם הגרף לא מספיק ברור, בקש גרף חדש.

חוקי ברזל:
1. המלץ על התראת מחיר בלבד (Price Alert) — לעולם לא Buy Stop Order.
2. חשב סטופ = 1.5 × ATR מתחת לנקודת הכשל (Failure Point).
   אם ATR לא נראה בגרף — ציין "ATR לא גלוי, הערכה ויזואלית" וספק הערכה.
3. אם המחיר מתחת ל-MA_150 — סמן HIGH RISK בתשובה. אל תפסול את העסקה,
   אך הדגש את הסיכון בבירור.
4. אם הגרף טשטושי, חתוך, או חסרים נתונים קריטיים (מחיר, ציר זמן, MA) —
   ענה בדיוק: NEED_BETTER_CHART ואל תוסיף ניתוח.
5. לפני שאתה מציע כניסה ל-watchlist, ודא שיש לך 4 שדות:
   symbol, trigger_price_zone, stop_loss, thesis_summary.
   אם חסר אחד — שאל את המשתמש.

פורמט תשובה (JSON בלבד, ללא markdown code block):
{
  "status": "OK" | "NEED_BETTER_CHART" | "MISSING_FIELDS",
  "missing_fields": [],
  "high_risk": true | false,
  "symbol": "TICKER",
  "asset_name": "שם החברה",
  "trigger_price_zone": 0.0,
  "stop_loss": 0.0,
  "atr_note": "הסבר ATR",
  "thesis_summary": "תיאור קצר",
  "required_setup_conditions": "תנאים לכניסה",
  "trade_type": "SHORT_TERM" | "LONG_TERM",
  "narrative": "ניתוח חופשי — מה רואים בגרף"
}"""

# ─── פונקציה ציבורית ─────────────────────────────────────────────

def analyze_chart(
    image_bytes: bytes,
    trade_type: str = "SHORT_TERM",
    extra_context: str = "",
) -> dict:
    """
    מנתח גרף TradingView ומחזיר dict עם תוצאת הניתוח.

    image_bytes: תוכן הקובץ (PNG/JPEG) כ-bytes
    trade_type:  "SHORT_TERM" | "LONG_TERM"
    extra_context: הערות נוספות מהמשתמש (אופציונלי)

    מחזיר dict עם status + שדות הניתוח.
    status = "OK"               → ניתוח תקין, 4 שדות קיימים
    status = "NEED_BETTER_CHART" → גרף לא ברור, בקש שוב
    status = "MISSING_FIELDS"   → חסר מידע, missing_fields מציין מה
    status = "ERROR"            → שגיאה טכנית, "error" מכיל פרטים
    """
    import json

    user_prompt = (
        f"סוג עסקה: {trade_type}\n"
        + (f"הערות: {extra_context}\n" if extra_context else "")
        + "נתח את הגרף הזה והחזר JSON בלבד לפי הפורמט שניתן."
    )

    try:
        raw = generate(
            model_key="smart",
            system_prompt=_SYSTEM,
            user_prompt=user_prompt,
            images=[image_bytes],
        )
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

    # ניקוי אפשרי של markdown wrappers
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # הסר שורה ראשונה (```json) ואחרונה (```)
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        # המודל לא החזיר JSON תקין — נחזיר error עם הטקסט הגולמי
        return {"status": "ERROR", "error": "JSON parse failed", "raw": raw}

    if "status" not in result:
        result["status"] = "ERROR"
        result["error"] = "חסר שדה status בתשובת המודל"
    _log_result(result)
    return result


def validate_for_save(result: dict) -> tuple[bool, list[str]]:
    """
    בדיקה שכל 4 השדות החובה קיימים לפני שמירה ל-watchlist.
    מחזיר (True, []) אם תקין, (False, [שדות חסרים]) אם לא.
    """
    required = ["symbol", "trigger_price_zone", "stop_loss", "thesis_summary"]
    missing = [
        f for f in required
        if not result.get(f) or result.get(f) in (0.0, "", None)
    ]
    return (len(missing) == 0, missing)


def to_watchlist_payload(result: dict) -> dict:
    """
    ממיר תוצאת analyze_chart לפורמט המתאים ל-database.py / watchlist_setups.
    קוראים ל-validate_for_save לפני שמירה.
    """
    return {
        "symbol":                   result.get("symbol", "").upper(),
        "required_setup_conditions": result.get("required_setup_conditions", ""),
        "trigger_price_zone":       result.get("trigger_price_zone", 0.0),
        "current_status":           "Pending Alert",
        "stop_loss":                result.get("stop_loss", 0.0),
        "thesis_summary":           result.get("thesis_summary", ""),
        "activation_trigger_price": 0.0,
        "activation_trigger_time":  "",
        "dismissal_notes":          "",
        "trade_type":               result.get("trade_type", "SHORT_TERM"),
    }


# ─── עזר פנימי ───────────────────────────────────────────────────

def _log_result(result: dict) -> None:
    status = result.get("status", "?")
    symbol = result.get("symbol", "לא זוהה")
    risk   = " ⚠️ HIGH RISK" if result.get("high_risk") else ""
    print(f"[chart_analyst] status={status} | symbol={symbol}{risk}")
    if result.get("missing_fields"):
        print(f"[chart_analyst] חסרים: {result['missing_fields']}")
