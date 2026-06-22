"""
routes/image_session.py — Image ו-Session chat endpoints.
מופרד מ-chat.py כי chat.py + image + session חרגו מ-150 שורות.
תומך ב: chart_analyst (ניתוח כללי), short_term (6 חוקי מיכה).
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json as _json
import asyncio
import base64 as _b64
import database as db

router = APIRouter()


# ─── Chat Image endpoint ──────────────────────────────────────────

class ChatImageBody(BaseModel):
    message: str = ""
    image_data: str           # base64
    image_mime: str = "image/png"
    history: list = []
    trade_type: str = "SHORT_TERM"

@router.post("/api/chat/image")
async def chat_image(body: ChatImageBody):
    """
    מקבל גרף TradingView (base64) → router → סוכן → SSE stream.
    תומך ב-chart_analyst ו-short_term.
    """
    from agents.router import route
    from agents.chart_analyst import analyze_chart
    from agents.short_term import analyze_short_term

    routing        = route(body.message, has_image=True)
    effective_type = routing.get("trade_type", body.trade_type)
    agent          = routing["agent"]

    # ── לוג ניתוב — לאבחון בעיות routing ────────────────────────
    print(f"[image_session] ── בקשה חדשה ──")
    print(f"[image_session] message='{body.message[:60]}'")
    print(f"[image_session] has_image=True")
    print(f"[image_session] routing={routing}")
    print(f"[image_session] agent_selected='{agent}' | effective_type='{effective_type}'")

    async def stream():
        try:
            # CLARIFY
            if agent == "CLARIFY":
                question = routing.get("question", "תוכל להבהיר?")
                print(f"[image_session] → CLARIFY: {question[:50]}")
                yield f"data: {_json.dumps({'clarify': True, 'text': question}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': 'router', 'keep_image': True}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {_json.dumps({'agent': agent, 'context': effective_type}, ensure_ascii=False)}\n\n"

            img_bytes      = _b64.b64decode(body.image_data)
            positions_text = db.positions_as_text()
            watchlist_text = db.watchlist_as_text()

            # ── ניתוח לפי הסוכן שנבחר ────────────────────────────
            if agent == "short_term":
                print(f"[image_session] → analyze_short_term()")
                result = analyze_short_term(
                    image_bytes=img_bytes,
                    extra_context=body.message,
                    positions_text=positions_text,
                    watchlist_text=watchlist_text,
                )
            else:
                print(f"[image_session] → analyze_chart() [agent={agent}]")
                result = analyze_chart(
                    image_bytes=img_bytes,
                    trade_type=effective_type,
                    extra_context=body.message,
                )

            print(f"[image_session] result.status='{result.get('status')}' | symbol='{result.get('symbol', '?')}'")

            # ── טיפול בסטטוסים ────────────────────────────────────
            if result.get("status") == "NEED_BETTER_CHART":
                msg = "הגרף לא ברור מספיק. אנא העלה גרף עם ציר זמן, מחירים ו-SMA גלויים."
                yield f"data: {_json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': agent}, ensure_ascii=False)}\n\n"
                return

            if result.get("status") == "MISSING_FIELDS":
                missing = ", ".join(result.get("missing_fields", []))
                msg = f"ניתוח חלקי — חסרים: {missing}. אנא ספק מידע נוסף."
                yield f"data: {_json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': agent}, ensure_ascii=False)}\n\n"
                return

            if result.get("status") == "ERROR":
                err = result.get("error", "שגיאה לא ידועה")
                yield f"data: {_json.dumps({'error': err}, ensure_ascii=False)}\n\n"
                return

            # ── בניית תשובה ───────────────────────────────────────
            response = _build_response_text(result, agent)
            chunk_size = 80
            for i in range(0, len(response), chunk_size):
                yield f"data: {_json.dumps({'text': response[i:i+chunk_size]}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {_json.dumps({'done': True, 'agent': agent, 'pending_watchlist': result}, ensure_ascii=False)}\n\n"

        except Exception as e:
            print(f"[image_session] ❌ exception: {e}")
            yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ─── עזר: בניית תשובה ────────────────────────────────────────────

def _build_response_text(result: dict, agent: str) -> str:
    """בונה תשובה טקסטואלית מתוצאת ניתוח."""
    # תשובה נרטיבית מ-short_term (פורמט 6 חוקים)
    if result.get("raw_text"):
        return result["raw_text"] + "\n\nהאם לשמור ל-watchlist? (כן/לא)"

    symbol    = result.get("symbol", "?")
    trigger   = result.get("trigger_price_zone", 0)
    stop      = result.get("stop_loss", 0)
    atr_note  = result.get("atr_note", "סטופ טכני")
    thesis    = result.get("thesis_summary", "")
    narrative = result.get("narrative", "")
    label     = "ניתוח סווינג" if agent == "short_term" else "ניתוח גרף"

    return (
        f"**{symbol}** — {label}\n\n"
        f"{narrative}\n\n"
        f"🎯 **טריגר:** ${trigger:,.2f}\n"
        f"🛑 **סטופ:** ${stop:,.2f}  ({atr_note})\n"
        f"📝 **תזה:** {thesis}\n\n"
        f"האם לשמור ל-watchlist? (כן/לא)"
    )
