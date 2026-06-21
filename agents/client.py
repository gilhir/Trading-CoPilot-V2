"""
agents/client.py — חיבור ל-Gemini בלבד.
אחריות: אתחול client, בחירת מודל, retry על 429.
אין prompts, אין לוגיקה, אין DB.
"""
import os
import time
import base64
from pathlib import Path
from dotenv import load_dotenv

# טעינת .env מהספריה הראשית של הפרויקט
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── מודלים זמינים ───────────────────────────────────────────────
# lite  = gemini-3.1-flash-lite  → ניתוב, משימות פשוטות (הכי זול)
# mid   = gemini-2.5-flash       → ביניים (short_term, portfolio)
# smart = gemini-3.5-flash       → מורכב (chart_analyst, long_term)
MODELS = {
    "lite":  "gemini-3.1-flash-lite",   # router
    "mid":   "gemini-2.5-flash",        # short_term, portfolio
    "smart": "gemini-3.5-flash",        # chart_analyst, long_term
}

# ─── אתחול client (singleton) ─────────────────────────────────────
_client = None

def get_client():
    """מחזיר client יחיד — נוצר פעם אחת."""
    global _client
    if _client is not None:
        return _client

    try:
        from google import genai
    except ImportError:
        raise RuntimeError("חסר: pip install google-genai")

    # מפתח בתשלום קודם, אחרי כן חינמי
    api_key = (
        os.getenv("GEMINI_PAID_API_KEY") or
        os.getenv("GEMINI_FREE_API_KEY") or
        os.getenv("GEMINI_API_KEY") or
        os.getenv("GOOGLE_API_KEY")
    )

    if not api_key:
        raise RuntimeError(
            "לא נמצא מפתח Gemini ב-.env\n"
            "צפוי: GEMINI_PAID_API_KEY או GEMINI_FREE_API_KEY"
        )

    _client = genai.Client(api_key=api_key)
    return _client


# ─── פונקציה מרכזית ──────────────────────────────────────────────

def generate(
    model_key: str,
    system_prompt: str,
    user_prompt: str,
    images: list = None,   # list of PIL.Image או bytes
    max_retries: int = 3,
    initial_delay: float = 3.0,
) -> str:
    """
    שולח בקשה ל-Gemini ומחזיר תשובה כ-string.

    model_key: "flash" | "pro" | "flash-8"
    images:    רשימת תמונות (PIL.Image) לניתוח vision
    """
    from google.genai import types

    model_name = MODELS.get(model_key, MODELS["lite"])
    client = get_client()

    # בניית תוכן ההודעה
    user_parts = []

    # תמונות (vision)
    if images:
        for img in images:
            if hasattr(img, 'tobytes'):
                # PIL Image → bytes
                import io
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                img_bytes = buf.getvalue()
            else:
                img_bytes = img  # כבר bytes

            user_parts.append(
                types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            )

    user_parts.append(types.Part.from_text(text=user_prompt))

    contents = [
        types.Content(role="user", parts=user_parts)
    ]

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,
        max_output_tokens=4096,
    )

    # retry loop
    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            return response.text or ""

        except Exception as e:
            last_error = e
            err = str(e)
            is_rate_limit = any(x in err for x in ["429", "RESOURCE_EXHAUSTED", "quota"])

            if is_rate_limit and attempt < max_retries - 1:
                print(f"[client] rate limit — ממתין {delay:.0f}ש' (ניסיון {attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2.0
                continue

            # שגיאה שאינה rate limit — throw מיד
            raise

    raise last_error


# ─── פונקציה עם היסטוריה (לצ'אט) ────────────────────────────────

def generate_with_history(
    model_key: str,
    system_prompt: str,
    history: list,          # [{"role": "user"|"model", "text": str}]
    user_prompt: str,
    images: list = None,
    max_retries: int = 3,
    initial_delay: float = 3.0,
) -> str:
    """
    כמו generate() אבל עם היסטוריית שיחה.
    history: רשימת dict עם role ו-text.
    """
    from google.genai import types

    model_name = MODELS.get(model_key, MODELS["lite"])
    client = get_client()

    contents = []

    # היסטוריה קיימת
    for msg in history:
        role = "model" if msg.get("role") in ("assistant", "model") else "user"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=msg["text"])])
        )

    # הודעה נוכחית
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
    contents.append(types.Content(role="user", parts=user_parts))

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,
        max_output_tokens=4096,
    )

    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            return response.text or ""

        except Exception as e:
            last_error = e
            err = str(e)
            is_rate_limit = any(x in err for x in ["429", "RESOURCE_EXHAUSTED", "quota"])

            if is_rate_limit and attempt < max_retries - 1:
                print(f"[client] rate limit — ממתין {delay:.0f}ש' (ניסיון {attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2.0
                continue

            raise

    raise last_error


# ─── בדיקת חיבור ─────────────────────────────────────────────────

def health_check() -> dict:
    """בדיקה שהמפתח תקין ו-Gemini עונה."""
    try:
        result = generate(
            model_key="flash",
            system_prompt="ענה בעברית בקצרה.",
            user_prompt="אמור 'מחובר' בלבד.",
            max_retries=1,
        )
        return {"ok": True, "response": result.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
