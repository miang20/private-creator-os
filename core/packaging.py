from __future__ import annotations
from .ai import ai_text

def make_packaging(topic: str, audience: str = "US / Tier-1", format_type: str = "Short") -> str:
    prompt = f"""Create one strong YouTube packaging set for this video.
Topic: {topic}
Audience: {audience}
Format: {format_type}
Return: best title (no hashtags in title), 3-second on-screen hook, description, 5 relevant hashtags, thumbnail concept, viewer promise. Do not invent facts about the video."""
    result = ai_text(prompt, "You are an expert YouTube editor and packaging strategist. Be specific, concise, and honest.")
    if result:
        return result
    clean = topic.strip() or "Your video idea"
    return (
        f"TITLE\n{clean} — The Moment Everything Changes 😳\n\n"
        f"HOOK\nWait for the exact moment this changes.\n\n"
        f"DESCRIPTION\nWatch this {format_type.lower()} about {clean.lower()}. The key moment is presented clearly, with no unnecessary setup.\n\n"
        f"HASHTAGS\n#Shorts #ViralMoments #Unexpected #Creator #Video\n\n"
        f"THUMBNAIL CONCEPT\nOne clear focal subject, high contrast, action frozen at its most surprising point; use 2–4 words only if they add context.\n\n"
        f"NOTE\nTemplate mode is active. Add OPENAI_API_KEY in Streamlit Secrets for custom AI-generated packaging."
    )

def build_caption_plan(transcript: str, max_words: int = 3) -> str:
    prompt = f"Split this transcript into sequential caption beats of 1 to {max_words} words each. Preserve meaning and order. One beat per line; do not add words. Transcript:\n{transcript}"
    result = ai_text(prompt, "You create accurate word-highlight subtitle plans. Never invent dialogue.")
    if result:
        return result
    words = transcript.split()
    return "\n".join(" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words))
