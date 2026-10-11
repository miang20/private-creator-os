from __future__ import annotations
from typing import Optional
from .config import openai_api_key

def ai_text(prompt: str, system: str = "You are a practical creator strategy assistant.") -> Optional[str]:
    """Use OpenAI API when configured. Returns None when no API key is configured."""
    key = openai_api_key()
    if not key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip() or None
    except Exception as exc:
        raise RuntimeError(f"AI provider request failed: {exc}") from exc
