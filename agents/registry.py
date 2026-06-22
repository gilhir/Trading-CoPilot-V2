"""
agents/registry.py — רשימת סוכנים פעילים.
כל סוכן חדש נרשם כאן בלבד — ה-router מרכיב את ה-prompt אוטומטית.
"""

AGENTS = [
    {
        "name":           "chart_analyst",
        "description":    "ניתוח גרפי TradingView כללי, vision, זיהוי תבניות ויזואליות, ניתוח טווח ארוך עם MA_150",
        "supports_image": True,
        "active":         True,
        "contexts":       ["LONG_TERM"],
        "extra_fields":   ["trade_type"],
    },
    {
        "name":           "short_term",
        "description":    "סווינג, טווח קצר, 6 חוקי מיכה, CCI, SMA20, ניתוח נרות, גרף לטווח קצר",
        "supports_image": True,   # ← תוקן: short_term מקבל גרפים
        "active":         True,
        "contexts":       ["SHORT_TERM"],
        "extra_fields":   [],
    },
    {
        "name":           "long_term",
        "description":    "ניתוח מבני, תמיכות, התנגדויות, מגמה ראשית, טווח ארוך, ללא תמונה",
        "supports_image": False,
        "active":         True,
        "contexts":       ["LONG_TERM"],
        "extra_fields":   [],
    },
    {
        "name":           "portfolio",
        "description":    "ביקורת תיק, עדכון סטופים, EOD, חשיפות, קורלציות, חוק 1%",
        "supports_image": False,
        "active":         True,
        "contexts":       ["EOD_ANALYSIS"],
        "extra_fields":   [],
    },
    {
        "name":           "trade_monitor",
        "description":    'רישום עסקה חדשה, "קניתי/מכרתי", עדכון פוזיציה קיימת',
        "supports_image": False,
        "active":         True,
        "contexts":       ["ACTION_LOADING"],
        "extra_fields":   [],
    },
    {
        "name":           "data_loader",
        "description":    "העלאת אקסל, סנכרון נתונים, קובץ בנק",
        "supports_image": False,
        "active":         False,   # יופעל בשלב 13
        "contexts":       ["DATA_LOADING"],
        "extra_fields":   [],
    },
    {
        "name":           "general",
        "description":    "כל שאלה כללית שלא שייכת לאף סוכן אחר",
        "supports_image": False,
        "active":         True,
        "contexts":       ["MAIN_ROUTER"],
        "extra_fields":   [],
    },
]

# הקשרים תקינים — נגזר אוטומטית מה-registry
VALID_CONTEXTS = {
    ctx
    for agent in AGENTS
    for ctx in agent["contexts"]
}

def get_active_agents() -> list[dict]:
    return [a for a in AGENTS if a["active"]]

def get_valid_names() -> set[str]:
    return {a["name"] for a in get_active_agents()}
