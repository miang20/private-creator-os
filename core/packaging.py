from __future__ import annotations
from .ai import ai_text


def make_packaging(topic: str, audience: str = "US / Tier-1", format_type: str = "Short") -> str:
    """Build a zero-cost packaging draft using deterministic local templates."""
    clean = " ".join(topic.split()) or "Your video idea"
    audience_clean = " ".join(audience.split()) or "US / Tier-1"
    fmt = format_type.strip() or "Short"
    hook = f"Watch what happens when {clean.lower()}."
    return (
        f"TITLE\n{clean} — The Moment Everything Changes 😳\n\n"
        f"HOOK\n{hook}\n\n"
        f"DESCRIPTION\nThis {fmt.lower()} shows {clean.lower()}. Made for viewers interested in {audience_clean}; the title and description should match the actual footage.\n\n"
        f"HASHTAGS\n#Shorts #UnexpectedMoments #Satisfying #Video\n\n"
        f"THUMBNAIL CONCEPT\nOne clear focal subject, high contrast, action frozen at its most surprising point; use 2–4 words only if they add context.\n\n"
        f"VIEWER PROMISE\nDeliver the exact moment implied by the title quickly, without misleading setup.\n\n"
        f"MODE\nFree local template; no paid AI API or API key required."
    )


def build_caption_plan(transcript: str, max_words: int = 3) -> str:
    """Split supplied transcript into readable word groups without external AI."""
    if not 1 <= int(max_words) <= 10:
        raise ValueError("max_words must be between 1 and 10")
    words = transcript.split()
    return "\n".join(" ".join(words[i:i + int(max_words)]) for i in range(0, len(words), int(max_words)))
