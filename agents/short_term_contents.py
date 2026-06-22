"""
agents/short_term_contents.py — בניית contents לGemini עבור short_term session.
עוטף את build_session_contents מ-chart_analyst_contents עם prompt שונה.
אחריות: סדר contents בלבד. אין לוגיקה, אין API.
"""
from __future__ import annotations
from agents.chart_analyst_contents import build_session_contents


def build_st_contents(
    history: list[dict],
    user_message: str,
    session_images: list[bytes],
) -> list:
    """
    בונה contents לGemini עבור short_term session.
    מאציל ל-build_session_contents — הסדר הקבוע זהה:
    תמונות session → היסטוריה → הודעה נוכחית.
    implicit caching עובד כי הגרפים תמיד ראשונים.
    """
    return build_session_contents(
        history=history,
        user_message=user_message,
        session_images=session_images,
    )
