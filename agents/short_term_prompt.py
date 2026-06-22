"""
agents/short_term_prompt.py — System prompt לסוכן קצר הטווח.
אחריות: בניית prompt בלבד. אין לוגיקה, אין DB, אין API.
"""
from __future__ import annotations

_RULES = """## 6 חוקי מיכה — חובה לבדוק כולם לפי הסדר:

חוק 1 — מיקום ביחס ל-SMA20:
  ✅ חיובי: מחיר מעל SMA20
  ❌ שלילי: מחיר מתחת ל-SMA20

חוק 2 — כיוון SMA20 בשבוע האחרון (5 ימי מסחר):
  ✅ חיובי: SMA20 עולה
  ⚠️ ניטרלי: SMA20 שטוח
  ❌ שלילי: SMA20 יורד

חוק 3 — נרות היפוך (בתחתית/פסגה):
  ✅ חיובי: Hammer, Inverted Hammer, Bullish Engulfing, Doji בתחתית
  ❌ שלילי: Shooting Star, Bearish Engulfing, Doji בפסגה
  ⚠️ ניטרלי: אין נר היפוך ברור

חוק 4 — נרות מומנטום:
  ✅ חיובי: Marubozu ירוק (גוף ≥70% טווח היומי)
  ❌ שלילי: Marubozu אדום
  ⚠️ ניטרלי: אין נר מומנטום ברור

חוק 5 — אימות ווליום:
  ✅ חיובי: ווליום ≥1.3× ממוצע 20 יום בנר הכיווני
  ❌ שלילי: ווליום מתחת לממוצע בנר מכריע
  ⚠️ ניטרלי: ווליום ממוצע

חוק 6 — פערים + CCI(14):
  ✅ חיובי: Gap Up שלא נסגר OR CCI(14) חצה +100 מלמטה
  ❌ שלילי: Gap Down שלא נסגר OR CCI(14) מתחת ל-(-100)
  ⚠️ ניטרלי: אין פער + CCI בין (-100) ל-(+100)"""

_RESPONSE_FORMAT = """## פורמט תשובה — חובה להקפיד:

שורה 1: **TICKER** — ניתוח סווינג
שורה 2-7: ✅/❌/⚠️ חוק N: [שם החוק] — [מה שנראה בגרף] — [חיובי/שלילי/ניטרלי]
שורה 8: ---
שורה 9: ציון: X/6 — [פירוש: מצוין/טוב/חלקי/שלילי]
שורה 10: 🎯 טריגר: $XX.XX | 🛑 סטופ: $XX.XX (1.5×ATR)
שורה 11: 📝 תזה: [משפט אחד תמציתי]
שורה 12: (ריק)
שורה 13: האם לשמור ל-watchlist? (כן/לא)

פירוש ציון: 5-6=מצוין, 4=טוב, 3=חלקי, 0-2=לא מומלץ"""

_SESSION_ADDENDUM = """## כללי המשך תחקיר:

- לשאלות על חוק ספציפי — הסבר בהרחבה מה שנראה בגרף.
- אם נשלח גרף נוסף — עדכן את ציון 6 החוקים בהתאם.
- אם המשתמש מבקש שינוי טריגר/סטופ — חשב מחדש לפי ATR.
- אם המשתמש מאשר (כן/שמור) — החזר JSON עם status=CONFIRMED.
- אם המשתמש מבטל (לא/ביטול) — החזר JSON עם status=CLOSE.

פורמט JSON לאישור/ביטול בלבד:
{
  "status": "CONFIRMED" | "CLOSE",
  "symbol": "TICKER",
  "trigger_price_zone": 0.0,
  "stop_loss": 0.0,
  "thesis_summary": "...",
  "required_setup_conditions": "חוקים שהתקיימו: ...",
  "trade_type": "SHORT_TERM",
  "narrative": "ציון X/6 — ...",
  "high_risk": false
}"""


def build_initial_prompt(positions_text: str = "", watchlist_text: str = "") -> str:
    """System prompt לניתוח ראשוני של גרף."""
    portfolio_ctx = ""
    if positions_text and positions_text != "אין פוזיציות פתוחות.":
        portfolio_ctx = f"\n\n## פוזיציות פתוחות:\n{positions_text}"
    if watchlist_text and watchlist_text != "רשימת המעקב ריקה.":
        portfolio_ctx += f"\n\n## רשימת מעקב נוכחית:\n{watchlist_text}"

    return f"""אתה אנליסט סווינג בכיר המנתח גרפי מניות לטווח קצר (ימים עד שבועות).
עבוד תמיד בעברית מקצועית. אל תנחש — אם הגרף לא מספיק ברור, בקש גרף נוסף.

{_RULES}

## guardrails:
- המלץ על התראת מחיר בלבד — לעולם לא Buy Stop Order.
- סטופ = 1.5 × ATR מתחת לנקודת הכשל האחרונה.
- נתח רק מה שרואים בגרף — אל תזכיר ממוצעים שאינם מסומנים בגרף.
- אם הגרף לא ברור — בקש גרף חדש, אל תנחש.

{_RESPONSE_FORMAT}{portfolio_ctx}"""


def build_session_prompt(positions_text: str = "", watchlist_text: str = "") -> str:
    """System prompt להמשך תחקיר (session)."""
    base = build_initial_prompt(positions_text, watchlist_text)
    return base + "\n\n" + _SESSION_ADDENDUM
