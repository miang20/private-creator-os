from __future__ import annotations
import re
from .hook_engine import classify_content


def make_packaging(topic: str, audience: str = "US / Tier-1", format_type: str = "Short", content_type: str = "Auto") -> str:
    """Create an offline packaging brief with hook strategies matched to the declared content."""
    clean = " ".join(topic.split()) or "Your video idea"
    audience_clean = " ".join(audience.split()) or "US / Tier-1"
    fmt = format_type.strip() or "Short"
    strategy = classify_content(clean, [], 0, content_type)
    words = clean.split()
    short_topic = " ".join(words[:12])
    title_recipes = {
        "funny_unexpected": [f"{short_topic} Happened at the PERFECT Time 😳", f"Nobody Expected This Moment 😂", f"Wait for the Ending…"],
        "story_drama": [f"The Moment Everything Changed", f"They Didn't See This Coming…", f"The Truth Finally Came Out"],
        "podcast_opinion": [f"The Truth About {short_topic}", f"Most People Get This Wrong", f"One Point That Changes the Conversation"],
        "satisfying_transformation": [f"From {short_topic} to a Clean Reveal ✨", f"Watch This Transformation", f"The Before-and-After Is Wild"],
        "tutorial_education": [f"How to {short_topic}", f"Stop Making This Mistake", f"The Simple Fix Explained"],
        "sports_action": [f"The Play Nobody Expected 😳", f"This Changed the Game", f"Wait for the Reaction"],
        "reaction_commentary": [f"That Reaction Says Everything 😳", f"Watch What They React To", f"No One Was Ready for This"],
        "general_visual": [f"{short_topic} — Watch Closely 👀", f"The Moment You Need to See", f"How Did This Happen?"],
    }
    titles = title_recipes[strategy["key"]]
    return (
        f"CONTENT ROUTE\n{strategy['label']} (confidence: {strategy['confidence']:.0%}; mode: {strategy['mode']})\n\n"
        f"TITLE OPTIONS — verify against footage\n1. {titles[0]}\n2. {titles[1]}\n3. {titles[2]}\n\n"
        f"PRIMARY HOOK STRATEGY\n{strategy['primary']}\n\nOPENING DIRECTION\n{strategy['opening']}\n\n"
        f"ALTERNATE HOOK STRATEGIES\n" + "\n".join(f"- {item}" for item in strategy["alternates"]) + "\n\n"
        f"EDITING RHYTHM\n{strategy['rhythm']}\n\nCAPTION DIRECTION\n{strategy['caption']}\n\n"
        f"DESCRIPTION\nThis {fmt.lower()} is about {clean}. Made for {audience_clean}. Keep every claim aligned with the actual footage; do not promise a reveal that the video does not deliver.\n\n"
        f"HASHTAGS\n#Shorts #CreatorContent\n\nTHUMBNAIL CONCEPT\nOne focal subject, clear emotional/action beat, strong contrast, and 0–4 words only when they add context.\n\n"
        f"VIEWER PROMISE\n{strategy['edit']}\n\nFREE MODE\nDeterministic local templates; no paid AI API required."
    )


def build_caption_plan(transcript: str, max_words: int = 3) -> str:
    """Split supplied transcript into readable word groups without external AI."""
    if not 1 <= int(max_words) <= 10:
        raise ValueError("max_words must be between 1 and 10")
    words = transcript.split()
    return "\n".join(" ".join(words[i:i + int(max_words)]) for i in range(0, len(words), int(max_words)))
