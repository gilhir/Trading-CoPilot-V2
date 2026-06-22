"""
agents/short_term.py — סוכן קצר הטווח (סווינג).
אחריות: API calls בלבד — ניתוח ראשוני + המשך תחקיר.
parsing → short_term_parser.py | prompt → short_term_prompt.py

ממשק ציבורי:
  analyze_short_term()   ← ניתוח ראשוני (גרף ראשון)
  analyze_st_followup()  ← המשך תחקיר (session)
  validate_for_save()    ← re-export מ-parser
  to_watchlist_payload() ← re-export מ-parser
"""
from __future__ import annotations

from agents.client import generate, get_client, MODELS
from agents.short_term_prompt import build_initial_prompt, build_session_prompt
from agents.short_term_contents import build_st_contents
from agents.short_term_parser import (
    parse_initial_response,
    validate_for_save,
    to_watchlist_payload,
)


# ─── ניתוח ראשוני ────────────────────────────────────────────────

def analyze_short_term(
    image_bytes: bytes,
    extra_context: str = "",
    positions_text: str = "",
    watchlist_text: str = "",
) -> dict:
    """
    מנתח גרף לפי 6 חוקי מיכה.
    status: OK | NEED_BETTER_CHART | MISSING_FIELDS | ERROR
    """
    system = build_initial_prompt(positions_text, watchlist_text)
    user_prompt = (
        "סוג עסקה: SHORT_TERM (סווינג)\n"
        + (f"הערות: {extra_context}\n" if extra_context else "")
        + "נתח את הגרף לפי 6 החוקים. ענה בפורמט שהוגדר."
    )

    try:
        raw = generate(
            model_key="mid",
            system_prompt=system,
            user_prompt=user_prompt,
            images=[image_bytes],
        )
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

    return parse_initial_response(raw)


# ─── המשך תחקיר ──────────────────────────────────────────────────

def analyze_st_followup(
    history: list[dict],
    user_message: str,
    session_images: list[bytes] = None,
    positions_text: str = "",
    watchlist_text: str = "",
) -> dict:
    """
    ממשיך תחקיר סווינג עם כל הגרפים שנאספו.
    status: OK | QUESTION | CONFIRMED | CLOSE | ERROR
    """
    from agents.chart_analyst_session import _is_close, _parse_response

    if _is_close(user_message) and not session_images:
        return {"status": "CLOSE", "text": "התחקיר נסגר."}

    try:
        from google.genai import types
        client     = get_client()
        model_name = MODELS["mid"]

        contents = build_st_contents(
            history=history,
            user_message=user_message,
            session_images=session_images or [],
        )
        config = types.GenerateContentConfig(
            system_instruction=build_session_prompt(positions_text, watchlist_text),
            temperature=0.1,
            max_output_tokens=4096,
        )
        response = client.models.generate_content(
            model=model_name, contents=contents, config=config,
        )
        raw = response.text or ""

    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

    return _parse_response(raw)
