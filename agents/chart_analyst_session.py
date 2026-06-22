"""
agents/chart_analyst_session.py — המשך תחקיר עם chart_analyst.
אחריות: שמירת הקשר מלא (תמונות + היסטוריה) עם implicit caching.

מבנה כל בקשה (סדר קבוע → Gemini cache אוטומטי):
  [תמונות session]     ← זהות תמיד → cached
  [היסטוריית שיחה]    ← משתנה
  [הודעה נוכחית]      ← משתנה
"""

from __future__ import annotations
from agents.client import get_client, MODELS
from agents.chart_analyst import _log_result
from agents.chart_analyst_contents import build_session_contents
import json as _json

_SESSION_SYSTEM = """אתה אנליסט טכני בכיר הממשיך תחקיר פתוח על גרף מניה.
כל הגרפים שנשלחו בתחקיר מצורפים. נתח אותם בכל שאלה.

כללים:
1. ענה בעברית מקצועית בלבד.
2. לשאלות ניתוחיות (נפח, MA, RSI, מבנה) — הסתכל על הגרפים וענה לפיהם בדיוק.
3. אל תתן תשובות כלליות — ענה על מה שנראה בגרפים האלה ספציפית.
4. אם נשלח גרף נוסף — שלב אותו בניתוח המעודכן.
5. אם המשתמש מאשר כניסה (כן/שמור) — החזר JSON עם status=CONFIRMED.
6. אם המשתמש מבטל (לא/ביטול) — החזר JSON עם status=CLOSE.
7. לשאלות ניתוחיות — ענה בטקסט חופשי מפורט, ללא JSON.

פורמט JSON (רק לעדכון ניתוח או אישור/ביטול):
{
  "status": "OK" | "CONFIRMED" | "CLOSE",
  "symbol": "TICKER",
  "trigger_price_zone": 0.0,
  "stop_loss": 0.0,
  "thesis_summary": "...",
  "narrative": "...",
  "high_risk": false
}"""


def analyze_followup(
    history: list[dict],
    user_message: str,
    session_images: list[bytes] = None,
) -> dict:
    """
    ממשיך תחקיר קיים עם כל הגרפים שנאספו עד כה.

    history:        היסטוריית שיחה [{"role", "text"}]
    user_message:   ההודעה הנוכחית
    session_images: כל גרפי התחקיר (מקורי + נוספים שהצטרפו)
    """
    if _is_close(user_message) and not session_images:
        return {"status": "CLOSE", "text": "התחקיר נסגר."}

    try:
        from google.genai import types
        client     = get_client()
        model_name = MODELS["smart"]

        contents = build_session_contents(
            history=history,
            user_message=user_message,
            session_images=session_images or [],
        )

        config = types.GenerateContentConfig(
            system_instruction=_SESSION_SYSTEM,
            temperature=0.1,
            max_output_tokens=4096,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        raw = response.text or ""

    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

    return _parse_response(raw)


def _parse_response(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1]).strip()
    try:
        result = _json.loads(cleaned)
        if "status" not in result:
            result["status"] = "OK"
        _log_result(result)
        return result
    except _json.JSONDecodeError:
        return {"status": "QUESTION", "text": raw.strip()}


def is_confirmation(message: str) -> bool | None:
    msg = message.strip().lower()
    if any(k in msg for k in ["כן", "שמור", "אישור", "אשר", "yes", "save", "👍"]):
        return True
    if any(k in msg for k in ["לא", "ביטול", "בטל", "no", "cancel", "👎"]):
        return False
    return None


def _is_close(message: str) -> bool:
    kw = ["לא", "ביטול", "בטל", "סגור", "סיום", "תודה", "no", "cancel"]
    return any(k in message.strip().lower() for k in kw) and len(message.strip()) < 15
