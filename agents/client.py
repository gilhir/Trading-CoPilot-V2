"""
agents/client.py — חיבור ל-Gemini בלבד.
אחריות: אתחול client, בחירת מודל, retry על 429.
generate_with_history → client_history.py
"""
import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

MODELS = {
    "lite":  "gemini-3.1-flash-lite",
    "mid":   "gemini-2.5-flash",
    "smart": "gemini-3.5-flash",
}

_client = None

def get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from google import genai
    except ImportError:
        raise RuntimeError("חסר: pip install google-genai")
    api_key = (
        os.getenv("GEMINI_PAID_API_KEY") or
        os.getenv("GEMINI_FREE_API_KEY") or
        os.getenv("GEMINI_API_KEY") or
        os.getenv("GOOGLE_API_KEY")
    )
    if not api_key:
        raise RuntimeError("לא נמצא מפתח Gemini ב-.env")
    _client = genai.Client(api_key=api_key)
    return _client


def generate(
    model_key: str,
    system_prompt: str,
    user_prompt: str,
    images: list = None,
    max_retries: int = 3,
    initial_delay: float = 3.0,
) -> str:
    """שולח בקשה ל-Gemini ומחזיר תשובה כ-string."""
    from google.genai import types

    model_name = MODELS.get(model_key, MODELS["lite"])
    client = get_client()

    user_parts = []
    if images:
        for img in images:
            if hasattr(img, 'tobytes'):
                import io
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                img_bytes = buf.getvalue()
            else:
                img_bytes = img
            user_parts.append(
                types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            )
    user_parts.append(types.Part.from_text(text=user_prompt))

    contents = [types.Content(role="user", parts=user_parts)]
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,
        max_output_tokens=8192,   # ← הוגדל מ-4096 ל-8192
    )

    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name, contents=contents, config=config,
            )
            return response.text or ""
        except Exception as e:
            last_error = e
            err = str(e)
            is_rate_limit = any(x in err for x in ["429", "RESOURCE_EXHAUSTED", "quota"])
            if is_rate_limit and attempt < max_retries - 1:
                print(f"[client] rate limit — ממתין {delay:.0f}ש' ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2.0
                continue
            raise

    raise last_error


# re-export לתאימות לאחור
from agents.client_history import generate_with_history  # noqa: F401


def health_check() -> dict:
    try:
        result = generate(
            model_key="lite",
            system_prompt="ענה בעברית בקצרה.",
            user_prompt="אמור 'מחובר' בלבד.",
            max_retries=1,
        )
        return {"ok": True, "response": result.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
