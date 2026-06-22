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
    מנתח גרף לפי 6 חוקי מיכה + מתקף תזת משתמש אם סופקה.
    status: OK | NEED_BETTER_CHART | MISSING_FIELDS | DRILL_DOWN_REQUIRED | ERROR
    """
    system = build_initial_prompt(positions_text, watchlist_text)

    # הגדרת תזה מפורשת — המודל יפעיל בלוק תיקוף
    if extra_context.strip():
        thesis_line = f"תזת המשתמש לתיקוף: {extra_context.strip()}\n"
        action_line = "נתח את הגרף לפי 6 החוקים, תקף את התזה, וענה בפורמט שהוגדר."
    else:
        thesis_line = ""
        action_line = "נתח את הגרף לפי 6 החוקים וענה בפורמט שהוגדר."

    user_prompt = f"סוג עסקה: SHORT_TERM (סווינג)\n{thesis_line}{action_line}"

    # ── לוג מה נשלח למודל ────────────────────────────────────────
    print(f"[short_term] ── analyze_short_term ──")
    print(f"[short_term] model=mid | image={len(image_bytes)} bytes")
    print(f"[short_term] has_thesis={bool(extra_context.strip())}")
    print(f"[short_term] user_prompt:\n{user_prompt}")
    print(f"[short_term] system_prompt (ראשון 200 תווים): {system[:200]}...")

    try:
        raw = generate(
            model_key="mid",
            system_prompt=system,
            user_prompt=user_prompt,
            images=[image_bytes],
        )
    except Exception as e:
        print(f"[short_term] ❌ generate error: {e}")
        return {"status": "ERROR", "error": str(e)}

    # ── לוג מה חזר מהמודל ────────────────────────────────────────
    print(f"[short_term] raw response ({len(raw)} תווים):")
    print(raw[:500])
    if len(raw) > 500:
        print(f"... [קוצר, {len(raw)-500} תווים נוספים]")

    result = parse_initial_response(raw)
    print(f"[short_term] parsed status={result.get('status')} | symbol={result.get('symbol','?')}")
    return result


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
    status: OK | QUESTION | CONFIRMED | CLOSE | DRILL_DOWN_REQUIRED | ERROR
    """
    from agents.chart_analyst_session import _is_close, _parse_response

    if _is_close(user_message) and not session_images:
        return {"status": "CLOSE", "text": "התחקיר נסגר."}

    print(f"[short_term] ── analyze_st_followup ──")
    print(f"[short_term] message='{user_message[:60]}'")
    print(f"[short_term] session_images={len(session_images or [])} | history={len(history)}")

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
        print(f"[short_term] ❌ followup error: {e}")
        return {"status": "ERROR", "error": str(e)}

    print(f"[short_term] followup raw ({len(raw)} תווים): {raw[:200]}...")
    return _parse_response(raw)
