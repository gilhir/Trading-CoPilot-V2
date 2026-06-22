"""
routes/image_session.py — Image ו-Session chat endpoints.
מופרד מ-chat.py כי chat.py + image + session חרגו מ-150 שורות.
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
import base64 as _b64

class ChatImageBody(BaseModel):
    message: str = ""
    image_data: str          # base64
    image_mime: str = "image/png"
    history: list = []
    trade_type: str = "SHORT_TERM"

@router.post("/api/chat/image")
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

