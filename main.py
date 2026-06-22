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



# ─── Chat & Session endpoints ─────────────────────────────
from routes.chat import router as chat_router
from routes.image_session import router as image_session_router
from routes.session import router as session_router
app.include_router(chat_router)
app.include_router(image_session_router)
app.include_router(session_router)
