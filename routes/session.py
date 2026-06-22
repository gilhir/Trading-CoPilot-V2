"""
routes/session.py — /api/chat/session endpoint.
המשך תחקיר פעיל — עוקף router, הולך ישירות לסוכן.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json as _json
import asyncio
import base64 as _b64

router = APIRouter()


class SessionBody(BaseModel):
    agent:          str        # "chart_analyst"
    context:        str        # "SHORT_TERM" | "LONG_TERM"
    message:        str = ""
    history:        list = []  # [{"role", "text"}]
    images:         list = []  # [base64] — תמונות חדשות בהודעה זו
    session_images: list = []  # [base64] — כל גרפי התחקיר עד כה


@router.post("/api/chat/session")
async def chat_session(body: SessionBody):
    """המשך תחקיר — עוקף router, מפנה לסוכן לפי body.agent."""
    from agents.chart_analyst_session import analyze_followup
    from agents.chart_analyst import to_watchlist_payload

    async def stream():
        try:
            yield f"data: {_json.dumps({'agent': body.agent, 'context': body.context, 'session': True}, ensure_ascii=False)}\n\n"

            if body.agent != "chart_analyst":
                yield f"data: {_json.dumps({'error': f'סוכן {body.agent} לא תומך ב-session עדיין'}, ensure_ascii=False)}\n\n"
                return

            # פענוח כל גרפי התחקיר
            all_images = [_b64.b64decode(img) for img in body.session_images if img]

            result = analyze_followup(
                history=body.history,
                user_message=body.message,
                session_images=all_images,
            )

            status = result.get("status")

            if status == "CLOSE":
                yield f"data: {_json.dumps({'text': result['text']}, ensure_ascii=False)}\n\n"
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

            # OK — ניתוח מעודכן
            risk   = "\n\n⚠️ HIGH RISK — מתחת ל-MA_150." if result.get("high_risk") else ""
            symbol = result.get("symbol", "?")
            trig   = result.get("trigger_price_zone", 0)
            stop   = result.get("stop_loss", 0)
            atr    = result.get("atr_note", "")
            thesis = result.get("thesis_summary", "")
            narr   = result.get("narrative", "")

            response = (
                f"**{symbol}** — ניתוח מעודכן{risk}\n\n{narr}\n\n"
                f"🎯 **טריגר:** ${trig:,.2f}\n"
                f"🛑 **סטופ:** ${stop:,.2f}  ({atr})\n"
                f"📝 **תזה:** {thesis}\n\n"
                f"האם לשמור ל-watchlist? (כן/לא)"
            )
            for i in range(0, len(response), 80):
                yield f"data: {_json.dumps({'text': response[i:i+80]}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {_json.dumps({'done': True, 'agent': body.agent, 'session_active': True, 'pending_watchlist': result}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
