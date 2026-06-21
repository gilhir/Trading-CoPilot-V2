"""
agents/router.py — סוכן הניתוב.
אחריות אחת: קבלת הודעה → החזרת JSON עם שם הסוכן והקשר.
לא מנתח, לא כותב, לא נוגע ב-DB.
מודל: lite (gemini-3.1-flash-lite) — הכי זול, רץ על כל הודעה.
"""
import json
from agents.client import generate

# ─── prompt מערכת ────────────────────────────────────────────────
SYSTEM_PROMPT = """אתה סוכן ניתוב של מערכת מסחר.
תפקידך: לקבל הודעה ולהחזיר JSON בלבד — ללא טקסט נוסף.

סוכנים זמינים:
- chart_analyst   → ניתוח גרף, תמונה ממסך TradingView, ניתוח ויזואלי
- short_term      → סווינג, טווח קצר, 6 חוקי מיכה, CCI, SMA20
- long_term       → ניתוח מבני, תמיכות, התנגדויות, מגמה ראשית, טווח ארוך
- portfolio       → ביקורת תיק, עדכון סטופים כללי, EOD, חשיפות, קורלציות
- trade_monitor   → רישום עסקה חדשה, "קניתי/מכרתי", עדכון פוזיציה קיימת
- data_loader     → העלאת אקסל, סנכרון נתונים, קובץ בנק
- general         → כל שאלה כללית שלא שייכת לאף סוכן

הקשרים אפשריים:
- SHORT_TERM      → עסקת סווינג / טווח קצר
- LONG_TERM       → פוזיציה ארוכת טווח
- EOD_ANALYSIS    → ניתוח סוף יום / ביקורת תיק
- ACTION_LOADING  → הזנת עסקה או עדכון
- DATA_LOADING    → טעינת נתונים
- MAIN_ROUTER     → ברירת מחדל / כללי

כלל: החזר JSON בלבד בפורמט הזה:
{"agent": "...", "context": "..."}

דוגמאות:
"העלה גרף של NVDA"           → {"agent": "chart_analyst", "context": "SHORT_TERM"}
"עדכן סטופים כללי"           → {"agent": "portfolio", "context": "EOD_ANALYSIS"}
"קניתי 50 מניות של AAPL"     → {"agent": "trade_monitor", "context": "ACTION_LOADING"}
"מה המצב של התיק שלי"        → {"agent": "portfolio", "context": "EOD_ANALYSIS"}
"ניתוח מבני של QQQ"          → {"agent": "long_term", "context": "LONG_TERM"}
"סווינג על TSLA לפי SMA20"   → {"agent": "short_term", "context": "SHORT_TERM"}
"העלה אקסל"                  → {"agent": "data_loader", "context": "DATA_LOADING"}
"מכרתי AMZN ב-230"           → {"agent": "trade_monitor", "context": "ACTION_LOADING"}
"""

# סוכנים וקשרים תקינים — לוולידציה
VALID_AGENTS   = {"chart_analyst", "short_term", "long_term",
                  "portfolio", "trade_monitor", "data_loader", "general"}
VALID_CONTEXTS = {"SHORT_TERM", "LONG_TERM", "EOD_ANALYSIS",
                  "ACTION_LOADING", "DATA_LOADING", "MAIN_ROUTER"}

_FALLBACK = {"agent": "general", "context": "MAIN_ROUTER"}


def route(user_message: str) -> dict:
    """
    מנתח הודעת משתמש ומחזיר dict עם agent ו-context.
    לעולם לא זורק exception — מחזיר fallback במקרה של שגיאה.
    """
    if not user_message or not user_message.strip():
        return _FALLBACK.copy()

    try:
        raw = generate(
            model_key="lite",
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_message.strip(),
            max_retries=3,
        )

        # ניקוי תשובה — לפעמים המודל עוטף ב-```json
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        result = json.loads(clean)

        # וולידציה
        agent   = result.get("agent", "")
        context = result.get("context", "")

        if agent not in VALID_AGENTS:
            print(f"[router] סוכן לא מוכר: {agent!r} → fallback")
            return _FALLBACK.copy()

        if context not in VALID_CONTEXTS:
            # context לא תקין — מחזירים עם MAIN_ROUTER
            result["context"] = "MAIN_ROUTER"

        return {"agent": agent, "context": result["context"]}

    except json.JSONDecodeError as e:
        print(f"[router] JSON parse error: {e} | raw={raw!r}")
        return _FALLBACK.copy()
    except Exception as e:
        print(f"[router] שגיאה: {e}")
        return _FALLBACK.copy()


def route_with_log(user_message: str) -> dict:
    """כמו route() אבל מדפיס לוג — שימושי לבדיקות."""
    result = route(user_message)
    print(f"[router] '{user_message[:50]}' → {result}")
    return result
