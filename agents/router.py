"""
agents/router.py — סוכן הניתוב הדינמי.
אחריות: קבלת הודעה → בניית prompt מה-registry → ניתוב או בקשת הבהרה.
לא מנתח, לא כותב, לא נוגע ב-DB.
מודל: lite — הכי זול, רץ על כל הודעה.
"""
import json
from agents.client import generate
from agents.registry import get_active_agents, get_valid_names, VALID_CONTEXTS

_FALLBACK = {"agent": "general", "context": "MAIN_ROUTER", "confidence": 1.0}
_CONFIDENCE_THRESHOLD = 0.85


def _build_system_prompt(has_image: bool) -> str:
    """בונה prompt דינמי מה-registry — מתעדכן אוטומטית כשמוסיפים סוכן."""
    agents = get_active_agents()

    # בניית רשימת סוכנים
    agent_lines = []
    for a in agents:
        img_tag = " [תומך בתמונות]" if a["supports_image"] else ""
        contexts = ", ".join(a["contexts"])
        agent_lines.append(f'- {a["name"]}{img_tag}\n  תיאור: {a["description"]}\n  הקשרים: {contexts}')
    agents_block = "\n".join(agent_lines)

    image_note = (
        "\nשים לב: המשתמש שלח תמונה (גרף/צילום מסך). "
        "העדף סוכנים התומכים בתמונות אלא אם הטקסט מצביע אחרת.\n"
        if has_image else ""
    )

    extra_fields_note = (
        "\nעבור chart_analyst בלבד — הוסף שדה trade_type: "
        '"SHORT_TERM" | "LONG_TERM" לפי כוונת המשתמש. ברירת מחדל: "SHORT_TERM".\n'
    )

    return f"""אתה סוכן ניתוב של מערכת מסחר.
תפקידך: לקבל הודעה ולהחזיר JSON בלבד — ללא טקסט נוסף.
{image_note}
סוכנים פעילים:
{agents_block}
{extra_fields_note}
החזר תמיד JSON בפורמט הזה:
{{"agent": "...", "context": "...", "confidence": 0.0-1.0}}

אם אינך בטוח מעל {int(_CONFIDENCE_THRESHOLD*100)}% — החזר:
{{"agent": "CLARIFY", "question": "שאלת הבהרה קצרה למשתמש"}}

דוגמאות:
"גרף סווינג של NVDA"          → {{"agent": "chart_analyst", "context": "SHORT_TERM", "trade_type": "SHORT_TERM", "confidence": 0.97}}
"ניתוח גרף טווח ארוך MSFT"    → {{"agent": "chart_analyst", "context": "LONG_TERM",  "trade_type": "LONG_TERM",  "confidence": 0.95}}
"עדכן סטופים"                 → {{"agent": "portfolio",     "context": "EOD_ANALYSIS",   "confidence": 0.91}}
"קניתי 50 AAPL"               → {{"agent": "trade_monitor", "context": "ACTION_LOADING", "confidence": 0.98}}
"ניתוח מבני QQQ"              → {{"agent": "long_term",     "context": "LONG_TERM",      "confidence": 0.93}}
"סווינג TSLA"                 → {{"agent": "short_term",    "context": "SHORT_TERM",     "confidence": 0.94}}
"מה המצב?"                    → {{"agent": "CLARIFY", "question": "על מה תרצה מידע — התיק הכללי, מניה ספציפית, או משהו אחר?"}}"""


def route(user_message: str, has_image: bool = False) -> dict:
    """
    מנתב הודעה לסוכן המתאים.
    מחזיר dict עם agent, context, confidence.
    אם confidence < 0.85 → agent=CLARIFY, question=שאלה.
    לעולם לא זורק exception.
    """
    if not user_message.strip() and not has_image:
        return _FALLBACK.copy()

    # אם יש תמונה ללא טקסט — הוסף הקשר מינימלי
    message = user_message.strip() or "המשתמש שלח תמונה ללא הסבר"

    try:
        raw = generate(
            model_key="lite",
            system_prompt=_build_system_prompt(has_image),
            user_prompt=message,
            max_retries=3,
        )

        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        result = json.loads(clean)
        agent  = result.get("agent", "")

        # CLARIFY — המודל לא בטוח
        if agent == "CLARIFY":
            question = result.get("question", "תוכל להבהיר את כוונתך?")
            print(f"[router] CLARIFY → {question}")
            return {"agent": "CLARIFY", "question": question}

        # ולידציה
        valid_names = get_valid_names()
        if agent not in valid_names:
            print(f"[router] סוכן לא מוכר: {agent!r} → fallback")
            return _FALLBACK.copy()

        context = result.get("context", "MAIN_ROUTER")
        if context not in VALID_CONTEXTS:
            context = "MAIN_ROUTER"

        confidence = float(result.get("confidence", 1.0))

        # confidence נמוך — טפל כ-CLARIFY
        if confidence < _CONFIDENCE_THRESHOLD:
            question = result.get("question", f"האם התכוונת לסוכן {agent}?")
            print(f"[router] confidence={confidence:.2f} < {_CONFIDENCE_THRESHOLD} → CLARIFY")
            return {"agent": "CLARIFY", "question": question}

        routing = {"agent": agent, "context": context, "confidence": confidence}

        # שדות נוספים לפי registry
        agents_map = {a["name"]: a for a in get_active_agents()}
        for field in agents_map.get(agent, {}).get("extra_fields", []):
            if field in result:
                routing[field] = result[field]

        # trade_type ברירת מחדל
        if agent == "chart_analyst" and "trade_type" not in routing:
            routing["trade_type"] = "SHORT_TERM"

        print(f"[router] '{message[:40]}' → {routing}")
        return routing

    except json.JSONDecodeError as e:
        print(f"[router] JSON error: {e} | raw={raw!r}")
        return _FALLBACK.copy()
    except Exception as e:
        print(f"[router] שגיאה: {e}")
        return _FALLBACK.copy()


def route_with_log(user_message: str, has_image: bool = False) -> dict:
    """כמו route() — לבדיקות."""
    return route(user_message, has_image)
