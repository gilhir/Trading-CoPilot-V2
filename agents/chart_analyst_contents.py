"""
agents/chart_analyst_contents.py — בניית contents לGemini עבור session.
מופרד כדי לשמור על chart_analyst_session.py מתחת ל-150 שורות.
"""
from __future__ import annotations


def build_session_contents(
    history: list[dict],
    user_message: str,
    session_images: list[bytes],
) -> list:
    """
    בונה contents לGemini עם implicit caching.
    סדר קבוע: תמונות ראשונות → היסטוריה → הודעה נוכחית.
    התמונות תמיד באותו מיקום → Gemini מזהה ו-cache אוטומטית.
    """
    from google.genai import types

    contents = []

    # ── Turn קבוע: כל תמונות ה-session (implicit cache) ──────────
    if session_images:
        img_parts = [
            types.Part.from_bytes(data=img, mime_type="image/png")
            for img in session_images
        ]
        img_parts.append(
            types.Part.from_text(text="אלו הגרפים של התחקיר. נתח לפיהם.")
        )
        contents.append(types.Content(role="user", parts=img_parts))
        contents.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text="הגרפים התקבלו. מוכן להמשיך.")]
        ))

    # ── היסטוריית שיחה ────────────────────────────────────────────
    for msg in history:
        role = "model" if msg.get("role") in ("assistant", "model") else "user"
        contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=msg.get("text", ""))]
        ))

    # ── הודעה נוכחית ──────────────────────────────────────────────
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)]
    ))

    return contents
