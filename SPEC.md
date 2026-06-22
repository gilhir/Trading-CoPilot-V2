# Trading Co-pilot v2 — מסמך מפרט ראשי

## עקרונות הפרויקט

- **קובץ = אחריות אחת.** אם צריך לחפש איפה נמצאת פונקציה — הקובץ שגוי.
- **מקסימום 150 שורות לקובץ.** חריגה → פיצול לקבצים.
- **תכונה נעולה = לא נוגעים בה.** סיימנו ובדקנו → status: LOCKED.
- **בדיקה לפני מעבר.** כל שלב מסתיים בבדיקה ידנית לפני המשך.
- **ללא framework כבד.** Python backend + HTML/JS סטטי. אין React build step.

---

## סטאק טכנולוגי

| שכבה | טכנולוגיה | הסיבה |
|---|---|---|
| Backend | FastAPI + Uvicorn | async, SSE, קל, מוכר |
| Frontend | HTML + Vanilla JS | local only, אין צורך ב-build |
| DB | SQLite (קיים) | עובד, לא משנים |
| AI models | google-genai (Gemini) | מפתח קיים |
| Market data | yfinance | עובד |
| Alerts | FastAPI webhook (קיים) | לא משנים |

---

## מבנה תיקיות

```
copilot_v2/
├── SPEC.md
├── main.py                          # FastAPI app + router imports
├── database.py                      # כל גישה ל-SQLite
│
├── agents/
│   ├── __init__.py
│   ├── client.py                    # generate() + re-export generate_with_history
│   ├── client_history.py            # generate_with_history (max_output_tokens=8192)
│   ├── registry.py                  # רשימת סוכנים — short_term supports_image=True
│   ├── router.py                    # Supervisor: intent detection + confidence
│   ├── chart_analyst.py             # ניתוח גרף ראשוני (vision)
│   ├── chart_analyst_session.py     # המשך תחקיר chart_analyst
│   ├── chart_analyst_contents.py    # build_session_contents (implicit caching)
│   ├── short_term.py                # analyze_short_term + analyze_st_followup + לוגים
│   ├── short_term_prompt.py         # 6 חוקים + thesis + stop + drill_down rules
│   ├── short_term_parser.py         # parsing, validate, to_watchlist_payload
│   ├── short_term_contents.py       # build_st_contents
│   ├── short_term_drill_down.py     # DRILL_DOWN_RULES + parse_drill_down
│   ├── long_term.py                 # ⬜ TODO
│   └── portfolio.py                 # ⬜ TODO
│
├── routes/
│   ├── __init__.py
│   ├── chat.py                      # POST /api/chat
│   ├── image_session.py             # POST /api/chat/image — לוגים מפורטים
│   ├── session.py                   # POST /api/chat/session — DRILL_DOWN תמיכה
│   └── watchlist_add.py             # POST /api/watchlist/add ← חדש
│
├── services/
│   ├── market_data.py               # ⬜ TODO
│   ├── excel_parser.py              # ⬜ TODO
│   └── webhook.py                   # ⬜ TODO
│
├── static/
│   ├── index.html                   # chat-chips-container (דינמי)
│   ├── app.js                       # _updateChips + addToWatchlist + session chips
│   └── style.css                    # + chip-accent / chip-danger variants
│
└── tests/
    ├── test_database.py
    ├── test_router.py
    └── test_market_data.py
```

---

## סכמת DB (קיימת, לא משנים)

### open_positions
| עמודה | טיפוס | הערות |
|---|---|---|
| symbol | TEXT PK | טיקר |
| quantity | REAL | כמות מניות |
| avg_cost_price | REAL | שער כניסה ממוצע |
| current_price | REAL | מחיר נוכחי |
| direction | TEXT | LONG / SHORT |
| entry_thesis | TEXT | תזת כניסה |
| initial_stop_loss | REAL | סטופ ראשוני |
| dynamic_stop_loss | REAL | סטופ נגרר |
| asset_name | TEXT | שם החברה |
| trade_type | TEXT | LONG_TERM / SHORT_TERM |

### watchlist_setups
| עמודה | טיפוס | הערות |
|---|---|---|
| symbol | TEXT PK | |
| required_setup_conditions | TEXT | תנאים לכניסה |
| trigger_price_zone | REAL | מחיר טריגר |
| current_status | TEXT | Pending Alert / Triggered - Awaiting Confirmation |
| stop_loss | REAL | סטופ מוצע |
| thesis_summary | TEXT | תזה |
| activation_trigger_price | REAL | |
| activation_trigger_time | TEXT | |
| dismissal_notes | TEXT | |
| trade_type | TEXT | LONG_TERM / SHORT_TERM |

---

## מודלים לפי סוכן

| סוכן | model_key | מודל | max_tokens |
|---|---|---|---|
| router.py | lite | gemini-3.1-flash-lite | 8192 |
| chart_analyst.py | smart | gemini-3.5-flash | 8192 |
| short_term.py | mid | gemini-2.5-flash | 8192 |
| long_term.py | smart | gemini-3.5-flash | 8192 |
| portfolio.py | mid | gemini-2.5-flash | 8192 |

---

## API Endpoints

| Method | Path | תפקיד | סטטוס |
|---|---|---|---|
| GET | /api/positions | פוזיציות + P&L | ✅ |
| GET | /api/watchlist | רשימת מעקב | ✅ |
| GET | /api/summary | 4 KPIs | ✅ |
| GET | /api/advice | המלצה אחרונה | ✅ |
| POST | /api/sync | רענון yfinance | stub |
| POST | /api/chat | צ'אט → SSE | ✅ |
| POST | /api/chat/image | גרף → short_term / chart_analyst | ✅ |
| POST | /api/chat/session | המשך תחקיר | ✅ |
| POST | /api/watchlist/add | שמירת ניתוח ל-watchlist | ✅ |
| POST | /api/watchlist/{symbol}/dismiss | ביטול התראה | ✅ |
| POST | /api/excel | העלאת קובץ בנק | ⬜ |
| POST | /webhook | TradingView alerts | ⬜ |

---

## ארכיטקטורת Session

```
גרף + תזה → /api/chat/image
    ↓ router → short_term
    ↓ analyze_short_term() — 6 חוקים + תיקוף תזה + סטופ טכני
    ↓ pending_watchlist
    ↓ app.js: _openSession() + _updateChips()
        ── צ'יפים: [💾 הוסף ל-Watchlist 🔒]  [✕ סיום תחקיר]
    ↓ ניתוח מלא מגיע → _updateChips() מפעיל "הוסף"
        ── צ'יפים: [💾 הוסף ל-Watchlist ✅]  [✕ סיום תחקיר]
    ↓ לחיצה → addToWatchlist() → POST /api/watchlist/add → DB
    ↓ loadAll() + _closeSession()
        ── צ'יפים: [עדכן סטופים]  [מצב התיק]  [הצג פוזיציות]
```

### Drill-Down
```
ציון לא מספיק → DRILL_DOWN_REQUIRED
    ↓ session_active=True — ממתין לגרף נוסף
    ↓ גרף נוסף → analyze_st_followup() עם session_images מעודכן
    ↓ ניתוח מלא → pending_watchlist → כפתור "הוסף" מופעל
```

---

## חוקי short_term (guardrails)

### 6 חוקי מיכה:
1. מיקום ביחס ל-SMA20
2. כיוון SMA20 בשבוע האחרון
3. נרות היפוך (Hammer, Doji, Engulfing)
4. נרות מומנטום (Marubozu)
5. אימות ווליום מול ממוצע 20 יום
6. פערים (Gaps) + CCI(14)

### תיקוף תזה:
- ציטוט מדויק של תזת המשתמש
- ✅ מאשש / ⚠️ חלקי / ❌ סותר + ראיות מהגרף
- טריגר מתזת המשתמש — אסור לשנות בשקט

### סטופ טכני:
- שלב 1: שפל נר הפריצה / תמיכה קרובה
- שלב 2: צמוד מדי (< 0.5×ATR) → כרית 0.5–1×ATR
- שלב 3: ציין מקור בתשובה

### Drill-Down triggers:
- REQUEST_65M: Doji/Pinbar על התנגדות, ציון 6/6 עם חוק ⚠️
- REQUEST_AVWAP: Gap פתוח + דשדוש
- REQUEST_RS_CONTEXT: תבנית ניטרלית + תזה חיובית

---

## סדר בנייה ומצב שלבים

| שלב | קבצים | מצב |
|---|---|---|
| 1 | database.py | 🔒 LOCKED |
| 2 | main.py + GET endpoints | 🔒 LOCKED |
| 3 | static/index.html + style.css | 🔒 LOCKED |
| 4 | static/app.js (tables + KPIs) | 🔒 LOCKED |
| 5 | agents/client.py + client_history.py | 🔒 LOCKED |
| 6 | agents/registry.py + agents/router.py | 🔒 LOCKED |
| 7 | POST /api/chat + SSE (routes/chat.py) | 🔒 LOCKED |
| 8 | chart_analyst + session + contents + routes | 🔒 LOCKED |
| 9 | short_term + prompt + parser + contents + drill_down | 🔒 LOCKED |
| 9b | watchlist chips UI + /api/watchlist/add | 🔒 LOCKED |
| 10 | agents/long_term.py + long_term_prompt.py | ⬜ TODO |
| 11 | agents/portfolio.py + portfolio_prompt.py | ⬜ TODO |
| 12 | services/market_data.py + POST /api/sync | ⬜ TODO |
| 13 | services/excel_parser.py + POST /api/excel | ⬜ TODO |
| 14 | services/webhook.py + POST /webhook | ⬜ TODO |

מצבים: ⬜ TODO → 🔨 IN PROGRESS → ✅ DONE → 🔒 LOCKED
