"""
routes/chat.py — POST /api/chat endpoint.
מופרד מ-main.py. ניתוב → סוכן → SSE stream.
short_term: מחובר ל-agents/short_term.py (ללא תמונה — טקסט בלבד).
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json as _json
import asyncio
import database as db

router = APIRouter()

# ─── system prompts כלליים (לסוכנים שאין להם קובץ ייעודי עדיין) ──
_GENERIC_PROMPTS = {
    "chart_analyst": "אתה מנתח גרפים מקצועי. עברית מקצועית בלבד.",
    "long_term":     "אתה מנתח מבני. עברית מקצועית בלבד.",
    "portfolio":     "אתה יועץ תיק השקעות. עברית מקצועית בלבד.",
    "trade_monitor": "אתה מנהל עסקאות. עברית מקצועית בלבד.",
    "data_loader":   "אתה מנהל נתונים. עברית מקצועית בלבד.",
    "general":       "אתה עוזר מסחר. עברית מקצועית בלבד.",
}

_MODEL_MAP = {
    "chart_analyst": "smart",
    "short_term":    "mid",
    "long_term":     "smart",
    "portfolio":     "mid",
    "trade_monitor": "mid",
    "data_loader":   "lite",
    "general":       "lite",
}


class ChatBody(BaseModel):
    message: str
    history: list = []   # [{"role": "user"|"assistant", "text": str}]


@router.post("/api/chat")
async def chat(body: ChatBody):
    """
    מקבל הודעה → router → סוכן → SSE stream.
    chunk:  data: {"text": "..."}\n\n
    סיום:  data: {"done": true, "agent": "..."}\n\n
    """
    from agents.router import route
    from agents.client import generate_with_history

    async def stream():
        try:
            routing = route(body.message, has_image=False)

            # CLARIFY
            if routing["agent"] == "CLARIFY":
                question = routing.get("question", "תוכל להבהיר?")
                yield f"data: {_json.dumps({'clarify': True, 'text': question}, ensure_ascii=False)}\n\n"
                yield f"data: {_json.dumps({'done': True, 'agent': 'router'}, ensure_ascii=False)}\n\n"
                return

            agent   = routing["agent"]
            context = routing["context"]
            yield f"data: {_json.dumps({'agent': agent, 'context': context}, ensure_ascii=False)}\n\n"

            positions_text = db.positions_as_text()
            watchlist_text = db.watchlist_as_text()

            # ── short_term — סוכן ייעודי ─────────────────────────
            if agent == "short_term":
                from agents.short_term_prompt import build_initial_prompt
                system = build_initial_prompt(positions_text, watchlist_text)
                response = generate_with_history(
                    model_key="mid",
                    system_prompt=system,
                    history=body.history,
                    user_prompt=body.message,
                )

            # ── שאר הסוכנים — prompt כללי ────────────────────────
            else:
                system = _GENERIC_PROMPTS.get(agent, _GENERIC_PROMPTS["general"])
                system += f"\n\nמידע על התיק:\n{positions_text}"
                response = generate_with_history(
                    model_key=_MODEL_MAP.get(agent, "mid"),
                    system_prompt=system,
                    history=body.history,
                    user_prompt=body.message,
                )

            # ── שליחת תשובה ──────────────────────────────────────
            for i in range(0, len(response), 80):
                yield f"data: {_json.dumps({'text': response[i:i+80]}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {_json.dumps({'done': True, 'agent': agent}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
