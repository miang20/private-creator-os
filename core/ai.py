from __future__ import annotations
from typing import Optional


def ai_text(prompt: str, system: str = "You are a practical creator strategy assistant.") -> Optional[str]:
    """Paid AI providers are intentionally disabled in the free-only build.

    Planner and packaging modules use deterministic local templates instead.
    This compatibility function remains so existing imports do not break.
    """
    return None
