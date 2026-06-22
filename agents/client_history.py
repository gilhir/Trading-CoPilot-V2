"""
agents/client_history.py — generate_with_history בלבד.
מופרד מ-client.py כדי לעמוד במגבלת 150 שורות.
"""
from agents.client import get_client, MODELS
import time


def generate_with_history(
    model_key: str,
    system_prompt: str,
    history: list,
    user_prompt: str,
    images: list = None,
    max_retries: int = 3,
    initial_delay: float = 3.0,
) -> str:
    """כמו generate() אבל עם היסטוריית שיחה."""
    from google.genai import types

    model_name = MODELS.get(model_key, MODELS["lite"])
    client = get_client()

    contents = []
    for msg in history:
        role = "model" if msg.get("role") in ("assistant", "model") else "user"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=msg["text"])])
        )

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
        max_output_tokens=8192,
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
