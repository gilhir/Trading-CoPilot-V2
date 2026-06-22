"""
routes/chat.py — Chat, Image ו-Session endpoints.
מופרד מ-main.py כי main.py חרג מ-150 שורות.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json as _json
import asyncio
import base64 as _b64
import database as db

router = APIRouter()


# ─── Chat endpoint ────────────────────────────────────────

class ChatBody(BaseModel):
    message: str
    history: list = []   # [{"role": "user"|"assistant", "text": str}]

@router.post("/api/chat")
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

