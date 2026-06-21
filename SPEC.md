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
├── SPEC.md                  # ← המסמך הזה
├── main.py                  # FastAPI app, routes בלבד (אין לוגיקה)
├── database.py              # כל גישה ל-SQLite (מועתק + מנוקה)
│
├── agents/
│   ├── __init__.py
│   ├── client.py            # אתחול Gemini client + retry logic
│   ├── router.py            # Supervisor: intent detection בלבד
│   ├── chart_analyst.py     # ניתוח גרפים (vision)
│   ├── short_term.py        # 6 חוקי מיכה
│   ├── long_term.py         # ניתוח מבני, חוק 1%
│   └── portfolio.py         # EOD audit, stop review
│
├── services/
│   ├── market_data.py       # yfinance wrapper
│   ├── excel_parser.py      # המרת אקסל בנק → DB
│   └── webhook.py           # TradingView handler
│
├── static/
│   ├── index.html           # Dashboard ראשי
│   ├── app.js               # fetch + SSE + UI logic
│   └── style.css            # עיצוב מה-handoff
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
| current_price | REAL | מחיר נוכחי (מעודכן מ-yfinance) |
| direction | TEXT | LONG / SHORT |
| entry_thesis | TEXT | תזת כניסה |
| initial_stop_loss | REAL | סטופ ראשוני (לא זזים ידנית) |
| dynamic_stop_loss | REAL | סטופ נגרר (0.0 = לא הוגדר) |
| asset_name | TEXT | שם החברה |
| trade_type | TEXT | LONG_TERM / SHORT_TERM |

### watchlist_setups
| עמודה | טיפוס | הערות |
|---|---|---|
| symbol | TEXT PK | |
| required_setup_conditions | TEXT | תנאים לכניסה |
| trigger_price_zone | REAL | מחיר טריגר |
| current_status | TEXT | Pending Alert / Triggered - Awaiting Confirmation / TRIGGERED |
| stop_loss | REAL | סטופ מוצע |
| thesis_summary | TEXT | תזה |
| activation_trigger_price | REAL | מחיר בעת הפעלה |
| activation_trigger_time | TEXT | זמן הפעלה |
| dismissal_notes | TEXT | סיבת ביטול |
| trade_type | TEXT | LONG_TERM / SHORT_TERM |

### trade_history_ledger
| עמודה | טיפוס | הערות |
|---|---|---|
| order_id | INTEGER PK | |
| symbol | TEXT | |
| action | TEXT | BUY / SELL |
| execution_price | REAL | |
| executed_quantity | REAL | |
| exit_reason | TEXT | |
| post_mortem_notes | TEXT | |

### portfolio_advice
| עמודה | טיפוס | הערות |
|---|---|---|
| id | INTEGER PK | |
| timestamp | TEXT | |
| advice_text | TEXT | מרקדאון |

---

## מודלים לפי סוכן

| סוכן | מודל | הסיבה |
|---|---|---|
| router.py | gemini-2.5-flash | ניתוב בלבד, זול, מהיר |
| chart_analyst.py | gemini-2.5-pro | vision + ניתוח עמוק |
| short_term.py | gemini-2.5-flash | 6 חוקים קבועים, פחות צריך pro |
| long_term.py | gemini-2.5-pro | ניתוח מבני, שווה להשקיע |
| portfolio.py | gemini-2.5-flash | חישובים, לא vision בד"כ |

---

## API Endpoints

| Method | Path | תפקיד |
|---|---|---|
| GET | /api/positions | פוזיציות פתוחות + P&L מחושב |
| GET | /api/watchlist | רשימת מעקב |
| GET | /api/summary | 4 KPIs: book value, P&L, count, cash |
| GET | /api/advice | המלצה אחרונה מ-portfolio_advice |
| POST | /api/sync | רענון yfinance + audit |
| POST | /api/chat | הודעת צ'אט → SSE stream |
| POST | /api/chat/image | העלאת גרף TradingView |
| POST | /api/watchlist/{symbol}/dismiss | ביטול התראה |
| POST | /api/watchlist/{symbol}/investigate | פתיחת תחקור |
| POST | /api/excel | העלאת קובץ בנק |
| POST | /webhook | TradingView alerts |

---

## חוקי סוכנים (guardrails) — לא משנים אותם

### כלל על לכל הסוכנים:
1. תמיד עברית מקצועית
2. כל פעולת DB מודפסת עם ה-SQL
3. לא מנחשים — עוצרים ושואלים

### router בלבד:
- מקבל הודעה → מחזיר JSON: `{"agent": "chart_analyst", "context": "SHORT_TERM"}`
- לא מנתח, לא כותב, לא מחשב

### chart_analyst:
- חוק 1: התראת מחיר בלבד, לא Buy Stop
- חוק 2: סטופ = 1.5 × ATR מתחת לנקודת כשל
- חוק 3: מתחת MA_150 = HIGH RISK
- חוק 4: גרף גרוע → עוצר ומבקש גרף חדש
- חוק 5: 4 שדות חובה לפני שמירה ל-watchlist

### short_term (6 חוקי מיכה):
1. מיקום ביחס ל-SMA20
2. כיוון SMA20 בשבוע האחרון
3. נרות היפוך (Hammer, Doji)
4. נרות מומנטום (Marubozu)
5. אימות ווליום מול ממוצע 20 יום
6. פערים + CCI(14)

### long_term:
- מבנה שוק, תמיכות, התנגדויות
- חוק 1%: סיכון > 1% מהון → פוסל עסקה

### portfolio:
- Ratchet Guardrail: סטופ רק לכיוון שמקטין סיכון
- לא מעדכן DB אוטומטית — ממליץ בלבד
- חוק 1% visual: שינוי > 1% → דורש גרף

---

## סדר בנייה ומצב שלבים

| שלב | קבצים | מצב |
|---|---|---|
| 1 | database.py | ⬜ TODO |
| 2 | main.py + GET endpoints | ⬜ TODO |
| 3 | static/index.html + style.css | ⬜ TODO |
| 4 | static/app.js (tables + KPIs) | ⬜ TODO |
| 5 | agents/client.py | ⬜ TODO |
| 6 | agents/router.py | ⬜ TODO |
| 7 | POST /api/chat + SSE | ⬜ TODO |
| 8 | agents/chart_analyst.py | ⬜ TODO |
| 9 | agents/short_term.py | ⬜ TODO |
| 10 | agents/long_term.py | ⬜ TODO |
| 11 | agents/portfolio.py | ⬜ TODO |
| 12 | services/market_data.py + POST /api/sync | ⬜ TODO |
| 13 | services/excel_parser.py + POST /api/excel | ⬜ TODO |
| 14 | services/webhook.py + POST /webhook | ⬜ TODO |

מצבים: ⬜ TODO → 🔨 IN PROGRESS → ✅ DONE → 🔒 LOCKED
