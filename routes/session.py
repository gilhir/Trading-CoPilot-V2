"""
routes/session.py — /api/chat/session endpoint.
המשך תחקיר פעיל — עוקף router, הולך ישירות לסוכן.
תומך ב: chart_analyst, short_term.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json as _json
import asyncio
import base64 as _b64
import database as db

router = APIRouter()


class SessionBody(BaseModel):
    agent:          str
    context:        str
    message:        str = ""
    history:        list = []
    images:         list = []   # base64 — תמונות חדשות בהודעה זו
    session_images: list = []   # base64 — כל גרפי התחקיר עד כה


@router.post("/api/chat/session")
async def chat_session(body: SessionBody):
    """המשך תחקיר — עוקף router, מפנה לסוכן לפי body.agent."""

    async def stream():
        try:
            yield f"data: {_json.dumps({'agent': body.agent, 'context': body.context, 'session': True}, ensure_ascii=False)}\n\n"

            # סוכנים נתמכים
            if body.agent not in ("chart_analyst", "short_term"):
                yield f"data: {_json.dumps({'error': f'סוכן {body.agent} לא תומך ב-session עדיין'}, ensure_ascii=False)}\n\n"
                return

            all_images = [_b64.b64decode(img) for img in body.session_images if img]

            # ── ניתוב לסוכן הנכון ────────────────────────────────
            if body.agent == "short_term":
                from agents.short_term import analyze_st_followup
                positions_text = db.positions_as_text()
                watchlist_text = db.watchlist_as_text()
                result = analyze_st_followup(
                    history=body.history,
                    user_message=body.message,
                    session_images=all_images,
                    positions_text=positions_text,
                    watchlist_text=watchlist_text,
                )
            else:
                from agents.chart_analyst_session import analyze_followup
                result = analyze_followup(
                    history=body.history,
                    user_message=body.message,
                    session_images=all_images,
                )

            # ── טיפול בסטטוסים ──────────────────────────────────
            status = result.get("status")

            if status == "CLOSE":
                yield f"data: {_json.dumps({'text': result.get('text', 'התחקיר נסגר.')}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': body.agent, 'session_closed': True}, ensure_ascii=False)}\n\n"
                return

            if status == "QUESTION":
                text = result.get("text", "")
                for i in range(0, len(text), 80):
                    yield f"data: {_json.dumps({'text': text[i:i+80]}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.02)
                yield f"data: {_json.dumps({'done': True, 'agent': body.agent, 'session_active': True}, ensure_ascii=False)}\n\n"
                return

            if status == "CONFIRMED":
                yield f"data: {_json.dumps({'text': 'מעולה! שומר ל-watchlist...'}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': body.agent, 'session_closed': True, 'pending_watchlist': result}, ensure_ascii=False)}\n\n"
                return

            if status == "ERROR":
                yield f"data: {_json.dumps({'error': result.get('error', 'שגיאה')}, ensure_ascii=False)}\n\n"
                return

            # ── OK — תשובה נרטיבית או מובנית ────────────────────
            response = _build_session_response(result, body.agent)

            for i in range(0, len(response), 80):
                yield f"data: {_json.dumps({'text': response[i:i+80]}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {_json.dumps({'done': True, 'agent': body.agent, 'session_active': True, 'pending_watchlist': result}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ─── עזר: בניית תשובת session ────────────────────────────────────

def _build_session_response(result: dict, agent: str) -> str:
    """בונה תשובת session טקסטואלית מתוצאת ניתוח."""
    # תשובה נרטיבית (short_term פורמט 6 חוקים)
    if result.get("raw_text"):
        risk = "\n\n⚠️ HIGH RISK — מתחת ל-MA_150." if result.get("high_risk") else ""
        return result["raw_text"] + risk + "\n\nהאם לשמור ל-watchlist? (כן/לא)"

    risk   = "\n\n⚠️ HIGH RISK — מתחת ל-MA_150." if result.get("high_risk") else ""
    symbol = result.get("symbol", "?")
    trig   = result.get("trigger_price_zone", 0)
    stop   = result.get("stop_loss", 0)
    atr    = result.get("atr_note", "1.5×ATR")
    thesis = result.get("thesis_summary", "")
    narr   = result.get("narrative", "")

    label = "ניתוח סווינג מעודכן" if agent == "short_term" else "ניתוח מעודכן"

    return (
        f"**{symbol}** — {label}{risk}\n\n{narr}\n\n"
        f"🎯 **טריגר:** ${trig:,.2f}\n"
        f"🛑 **סטופ:** ${stop:,.2f}  ({atr})\n"
        f"📝 **תזה:** {thesis}\n\n"
        f"האם לשמור ל-watchlist? (כן/לא)"
    )
