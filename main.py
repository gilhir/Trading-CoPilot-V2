"""
main.py — FastAPI routes בלבד.
אין לוגיקה עסקית כאן — רק קריאה לפונקציות database.py
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import database as db

app = FastAPI(title="Trading Co-pilot v2")

# ─── Static files (HTML/JS/CSS) ───────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"status": "ok", "message": "Trading Co-pilot v2"}


# ─── GET endpoints ────────────────────────────────────────

@app.get("/api/positions")
def get_positions():
    """כל הפוזיציות הפתוחות + P&L מחושב."""
    return db.get_positions()


@app.get("/api/positions/{symbol}")
def get_position(symbol: str):
    """פוזיציה בודדת."""
    pos = db.get_position(symbol.upper())
    if not pos:
        raise HTTPException(status_code=404, detail=f"לא נמצא: {symbol}")
    return pos


@app.get("/api/summary")
def get_summary():
    """4 KPIs לכותרת ה-dashboard."""
    return db.get_positions_summary()


@app.get("/api/watchlist")
def get_watchlist():
    """רשימת המעקב המלאה."""
    return db.get_watchlist()


@app.get("/api/watchlist/triggered")
def get_triggered():
    """רק התראות שהופעלו וממתינות."""
    return db.get_triggered_alerts()


@app.get("/api/advice")
def get_advice():
    """המלצת יועץ התיקים האחרונה."""
    advice = db.get_latest_advice()
    if not advice:
        return {"timestamp": None, "advice_text": None}
    return advice


@app.get("/api/ledger")
def get_ledger():
    """היסטוריית עסקאות."""
    return db.get_ledger()


@app.get("/api/health")
def health():
    """בדיקת חיים — תמיד מחזיר 200."""
    summary = db.get_positions_summary()
    return {
        "status": "ok",
        "positions": summary["position_count"],
        "db": str(db.DB_PATH),
    }


# ─── POST endpoints (stubs — מתמלאים בשלבים הבאים) ──────────────

from pydantic import BaseModel
from typing import Optional

class DismissBody(BaseModel):
    notes: Optional[str] = ""

@app.post("/api/watchlist/{symbol}/dismiss")
def dismiss_alert(symbol: str, body: DismissBody = DismissBody()):
    ok, msg = db.dismiss_alert(symbol.upper(), body.notes or "")
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"ok": True, "message": msg}


@app.post("/api/watchlist/{symbol}/investigate")
def investigate_alert(symbol: str):
    """פתיחת מצב תחקור — יחובר לסוכן בשלב הצ'אט."""
    item = db.get_watchlist_item(symbol.upper())
    if not item:
        raise HTTPException(status_code=404, detail=f"לא נמצא: {symbol}")
    return {"ok": True, "symbol": symbol.upper(), "item": item}


@app.post("/api/sync")
def sync_market():
    """רענון נתוני שוק — stub, יחובר ל-yfinance בשלב 12."""
    return {"ok": True, "message": "sync endpoint מוכן — יחובר ל-yfinance בשלב 12"}


@app.post("/webhook")
async def webhook(request: Request):
    """TradingView webhook — stub, יחובר בשלב 14."""
    body = await request.json()
    return {"ok": True, "received": body}


# ─── Chat endpoint ────────────────────────────────────────

from fastapi.responses import StreamingResponse
import json as _json
import asyncio

class ChatBody(BaseModel):
    message: str
    history: list = []   # [{"role": "user"|"assistant", "text": str}]

@app.post("/api/chat")
async def chat(body: ChatBody):
    """
    מקבל הודעה → router → סוכן → מזרים תשובה כ-SSE.
    כל chunk: data: {"text": "..."}\n\n
    סיום:    data: {"done": true, "agent": "..."}\n\n
    """
    from agents.router import route
    from agents.client import generate_with_history

    # system prompts בסיסיים לכל סוכן (יוחלפו בקבצים ייעודיים בשלבים הבאים)
    SYSTEM_PROMPTS = {
        "chart_analyst":  "אתה מנתח גרפים מקצועי. עברית מקצועית בלבד.",
        "short_term":     "אתה מנתח סווינג. עברית מקצועית בלבד.",
        "long_term":      "אתה מנתח מבני. עברית מקצועית בלבד.",
        "portfolio":      "אתה יועץ תיק השקעות. עברית מקצועית בלבד.",
        "trade_monitor":  "אתה מנהל עסקאות. עברית מקצועית בלבד.",
        "data_loader":    "אתה מנהל נתונים. עברית מקצועית בלבד.",
        "general":        "אתה עוזר מסחר. עברית מקצועית בלבד.",
    }

    MODEL_MAP = {
        "chart_analyst": "smart",
        "short_term":    "mid",
        "long_term":     "smart",
        "portfolio":     "mid",
        "trade_monitor": "mid",
        "data_loader":   "lite",
        "general":       "lite",
    }

    async def stream():
        try:
            # ניתוב
            routing = route(body.message, has_image=False)

            # CLARIFY — הסוכן לא בטוח, שולח שאלה חזרה
            if routing["agent"] == "CLARIFY":
                question = routing.get("question", "תוכל להבהיר?")
                yield f"data: {_json.dumps({'clarify': True, 'text': question}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': 'router'}, ensure_ascii=False)}\n\n"
                return

            agent   = routing["agent"]
            context = routing["context"]

            yield f"data: {_json.dumps({'agent': agent, 'context': context}, ensure_ascii=False)}\n\n"

            # הוספת מידע על תיק להקשר
            positions_text = db.positions_as_text()
            system = SYSTEM_PROMPTS.get(agent, SYSTEM_PROMPTS["general"])
            system += f"\n\nמידע על התיק הנוכחי:\n{positions_text}"

            # קריאה לסוכן
            model_key = MODEL_MAP.get(agent, "mid")
            response  = generate_with_history(
                model_key=model_key,
                system_prompt=system,
                history=body.history,
                user_prompt=body.message,
            )

            # שליחת התשובה chunk אחד (streaming אמיתי יבוא אחרי)
            chunk_size = 80
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i+chunk_size]
                yield f"data: {_json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {_json.dumps({'done': True, 'agent': agent}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ─── Chat Image endpoint ──────────────────────────────────────────
import base64 as _b64

class ChatImageBody(BaseModel):
    message: str = ""
    image_data: str          # base64
    image_mime: str = "image/png"
    history: list = []
    trade_type: str = "SHORT_TERM"

@app.post("/api/chat/image")
async def chat_image(body: ChatImageBody):
    """
    מקבל גרף TradingView (base64) → chart_analyst → SSE stream.
    הכניסה: { image_data, image_mime, message, trade_type, history }
    """
    from agents.chart_analyst import analyze_chart, validate_for_save
    from agents.router import route

    # ניתוב עם has_image=True — הסוכן יודע שיש תמונה
    routing        = route(body.message, has_image=True)
    effective_type = routing.get("trade_type", body.trade_type)

    async def stream():
        try:
            # CLARIFY — הסוכן לא בטוח, שולח שאלה, התמונה תישמר ב-client
            if routing["agent"] == "CLARIFY":
                question = routing.get("question", "תוכל להבהיר?")
                yield f"data: {_json.dumps({'clarify': True, 'text': question}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': 'router', 'keep_image': True}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {_json.dumps({'agent': 'chart_analyst', 'context': effective_type}, ensure_ascii=False)}\n\n"

            img_bytes = _b64.b64decode(body.image_data)
            result    = analyze_chart(
                image_bytes=img_bytes,
                trade_type=effective_type,
                extra_context=body.message,
            )

            # NEED_BETTER_CHART → בקש גרף חדש
            if result.get("status") == "NEED_BETTER_CHART":
                msg = "הגרף לא ברור מספיק. אנא העלה גרף ברזולוציה גבוהה יותר עם ציר זמן ומחירים גלויים."
                yield f"data: {_json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': 'chart_analyst'}, ensure_ascii=False)}\n\n"
                return

            # MISSING_FIELDS → ציין מה חסר
            if result.get("status") == "MISSING_FIELDS":
                missing = ", ".join(result.get("missing_fields", []))
                msg = f"ניתוח חלקי — חסרים שדות: {missing}. אנא ספק מידע נוסף."
                yield f"data: {_json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': 'chart_analyst'}, ensure_ascii=False)}\n\n"
                return

            # ERROR
            if result.get("status") == "ERROR":
                err = result.get("error", "שגיאה לא ידועה")
                yield f"data: {_json.dumps({'error': err}, ensure_ascii=False)}\n\n"
                return

            # OK — בנה תשובה טקסטואלית
            risk_flag = "\n\n⚠️ **HIGH RISK** — המחיר מתחת ל-MA_150." if result.get("high_risk") else ""
            narrative = result.get("narrative", "")
            symbol    = result.get("symbol", "?")
            trigger   = result.get("trigger_price_zone", 0)
            stop      = result.get("stop_loss", 0)
            atr_note  = result.get("atr_note", "")
            thesis    = result.get("thesis_summary", "")

            response = (
                f"**{symbol}** — ניתוח גרף{risk_flag}\n\n"
                f"{narrative}\n\n"
                f"🎯 **טריגר:** ${trigger:,.2f}\n"
                f"🛑 **סטופ:** ${stop:,.2f}  ({atr_note})\n"
                f"📝 **תזה:** {thesis}\n\n"
                f"האם לשמור ל-watchlist? (כן/לא)"
            )

            chunk_size = 80
            for i in range(0, len(response), chunk_size):
                yield f"data: {_json.dumps({'text': response[i:i+chunk_size]}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            # שמירה ל-session state — ה-caller יכול לאשר
            yield f"data: {_json.dumps({'done': True, 'agent': 'chart_analyst', 'pending_watchlist': result}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
