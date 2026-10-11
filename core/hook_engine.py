from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Deterministic, offline strategy routing. Signals are intentionally transparent:
# this is useful local analysis, not a claim of semantic/viral certainty.
ARCHETYPES: dict[str, dict[str, Any]] = {
    "funny_unexpected": {
        "label": "Funny / Unexpected",
        "signals": r"\b(lol|haha|funny|hilarious|prank|fail|oops|unexpected|didn.t expect|plot twist|what are the odds|perfect timing|caught on camera|no way|wait for it)\b",
        "primary": "Payoff-first + curiosity gap",
        "alternates": ["Reaction-first", "Perfect-timing reveal", "Expectation vs. reality"],
        "edit": "Open on the clearest surprising frame; cut dead air before the setup; keep only enough context to make the payoff land; end immediately after the reaction/payoff.",
        "rhythm": "Fast cold open; short setup; accelerate into payoff; no long outro.",
        "caption": "Use short punchy phrases; emphasize the actual surprise word, not every sentence.",
        "opening": "Show the surprising moment first, then rewind just enough to explain how it happened.",
    },
    "story_drama": {
        "label": "Story / Drama",
        "signals": r"\b(revenge|betray|betrayed|secret|truth|exposed|discovered|revenge|he thought|she thought|until|then|finally|years later|plot twist|turns out|because|consequence|confession)\b",
        "primary": "Consequence-first open",
        "alternates": ["Mystery question", "Escalation ladder", "Reveal withheld until payoff"],
        "edit": "Open on a consequential image or a verified line; add only essential context; make each beat change the stakes; preserve the turning point and payoff.",
        "rhythm": "Cold open; compact context; rising beat density; brief pause before reveal; clean payoff.",
        "caption": "Highlight the turning-point phrase and names only when clear in the transcript.",
        "opening": "Lead with the consequence, then give viewers a clear reason to ask how it happened.",
    },
    "podcast_opinion": {
        "label": "Podcast / Opinion",
        "signals": r"\b(i think|i believe|in my opinion|the problem is|the truth is|honestly|here.s why|because|actually|people think|most people|wrong|right|advice|lesson|mistake|should|must|never|always)\b",
        "primary": "Strong statement → proof",
        "alternates": ["Counterintuitive claim", "Question → answer", "One useful takeaway"],
        "edit": "Start on a complete, understandable statement; remove pauses and repeated phrases; retain the proof/example; cut before the thought becomes repetitive.",
        "rhythm": "Immediate claim; one proof beat; optional counterpoint; concise takeaway.",
        "caption": "Readable 1–3 word beats; emphasize the claim and key contrast.",
        "opening": "Start at the strongest complete claim found in the transcript, not at the speaker's greeting.",
    },
    "satisfying_transformation": {
        "label": "Satisfying / Transformation",
        "signals": r"\b(restore|restoration|before and after|before|after|clean|cleaning|satisfying|polish|polishing|transform|transformation|repair|fixed|build|built|makeover|reveal|smooth|perfect|scrape|peel|paint|renovate)\b",
        "primary": "Visual reveal + before/after contrast",
        "alternates": ["Process-to-payoff", "Texture close-up", "Seamless loop ending"],
        "edit": "Open with a truthful glimpse of the finished state, match-cut to the starting state, show only visible progress, and return to the final reveal. Never imply a change the footage does not show.",
        "rhythm": "Instant visual proof; short process stages; varied detail shots; satisfying final hold.",
        "caption": "Keep text minimal; let visible material changes carry the story.",
        "opening": "Use the strongest visible state change; if the footage has no clear before/after, start on its most distinctive action instead.",
    },
    "tutorial_education": {
        "label": "Tutorial / Educational",
        "signals": r"\b(how to|step one|first|second|step|tutorial|tip|tips|here.s how|guide|learn|explained|three ways|mistake|method|technique|fix|solution|because|result)\b",
        "primary": "Problem → promised result",
        "alternates": ["Result preview", "Common mistake → fix", "Numbered micro-steps"],
        "edit": "Show the problem or result immediately; remove repeated explanation; preserve the steps in logical order; show proof of the result before ending.",
        "rhythm": "Problem/result; 2–4 clear steps; visible proof; no generic outro.",
        "caption": "Use concise action words and step markers; do not caption long paragraphs.",
        "opening": "State the specific problem and preview the result the footage actually demonstrates.",
    },
    "sports_action": {
        "label": "Sports / Action",
        "signals": r"\b(goal|scored|score|home run|strikeout|knockout|referee|ejected|ejection|fight|slam dunk|touchdown|save|race|finish line|penalty|overtime|championship|athlete|player|match point)\b",
        "primary": "Action-first + replay context",
        "alternates": ["Reaction-first", "Close-call tension", "Setup → decisive play"],
        "edit": "Lead with the decisive action or authentic reaction; keep enough lead-in to understand it; avoid cutting away before the result; use replay only if the source contains it.",
        "rhythm": "Short setup; action peak; reaction; quick exit.",
        "caption": "Emphasize the decisive action or result; don't invent player names or scores.",
        "opening": "Lead with the clearest action peak, then restore the minimum context needed to understand it.",
    },
    "reaction_commentary": {
        "label": "Reaction / Commentary",
        "signals": r"\b(react|reaction|my reaction|can't believe|cannot believe|oh my god|what|wow|seriously|are you kidding|look at|watch this|insane|unbelievable)\b",
        "primary": "Reaction-first",
        "alternates": ["Build anticipation", "Visual cue → reaction", "Question → reveal"],
        "edit": "Keep the trigger and reaction connected; start as close as possible to the genuine reaction; trim unrelated lead-in without changing meaning.",
        "rhythm": "Cue; reaction; short context; payoff.",
        "caption": "Emphasize authentic reaction words; avoid adding emotion not present in the source.",
        "opening": "Use the clearest genuine reaction paired with its cause.",
    },
    "general_visual": {
        "label": "General / Visual-first",
        "signals": "",
        "primary": "Visual curiosity + fast context",
        "alternates": ["Action-first", "Question → reveal", "Best-frame cold open"],
        "edit": "Start on a visually legible action or change; remove idle lead-in; keep cause and effect intact; finish on the natural payoff.",
        "rhythm": "Immediate visual hook; compact context; changing shot scale; decisive ending.",
        "caption": "Only burn captions when reliable word timestamps exist; keep them concise and away from important on-screen action.",
        "opening": "Choose the most visually distinctive moment that can be understood without invented context.",
    },
}

def classify_content(transcript: str = "", scene_changes: list[float] | None = None, duration: float = 0.0, requested: str = "Auto") -> dict[str, Any]:
    """Classify broad content type from visible transcript signals and editing signals."""
    requested_map = {
        "Auto": None,
        "Funny / Unexpected": "funny_unexpected",
        "Story / Drama": "story_drama",
        "Podcast / Opinion": "podcast_opinion",
        "Satisfying / Transformation": "satisfying_transformation",
        "Tutorial / Educational": "tutorial_education",
        "Sports / Action": "sports_action",
        "Reaction / Commentary": "reaction_commentary",
        "General / Visual-first": "general_visual",
    }
    if requested not in requested_map:
        requested = "Auto"
    text = " ".join((transcript or "").lower().split())
    if requested_map[requested]:
        key = requested_map[requested]
        confidence = 1.0
        mode = "user-selected"
    else:
        scores: Counter[str] = Counter()
        for key, spec in ARCHETYPES.items():
            pattern = spec["signals"]
            if pattern:
                matches = re.findall(pattern, text, flags=re.I)
                scores[key] = len(matches)
        if not text.strip():
            key = "satisfying_transformation" if len(scene_changes or []) >= 3 else "general_visual"
            confidence = 0.35 if key == "general_visual" else 0.4
            mode = "visual-fallback"
        elif scores:
            best = scores.most_common()
            key, top = best[0]
            second = best[1][1] if len(best) > 1 else 0
            if top == 0:
                key, confidence = "general_visual", 0.35
            else:
                confidence = min(0.92, 0.45 + 0.12 * top + (0.12 if top > second else 0.0))
            mode = "transcript-signals"
        else:
            key, confidence, mode = "general_visual", 0.35, "transcript-signals"
    spec = ARCHETYPES[key]
    # Build opening candidates only from observed transcript phrases, or honest instructions.
    sentences = [re.sub(r"\s+", " ", s).strip() for s in re.split(r"(?<=[.!?])\s+", transcript or "") if s.strip()]
    candidates = sorted(sentences, key=lambda s: (min(len(s.split()), 18), len(s)), reverse=True)
    observed_line = next((s for s in candidates if 4 <= len(s.split()) <= 22), "")
    if observed_line:
        opening = f'Observed transcript candidate: “{observed_line[:220]}”'
    else:
        opening = spec["opening"]
    return {
        "key": key,
        "label": spec["label"],
        "confidence": round(confidence, 2),
        "mode": mode,
        "primary": spec["primary"],
        "alternates": list(spec["alternates"]),
        "edit": spec["edit"],
        "rhythm": spec["rhythm"],
        "caption": spec["caption"],
        "opening": opening,
        "signals": {k: int(v) for k, v in (scores.items() if requested_map.get(requested) is None and text else [])},
        "warning": "Low-confidence route: review the strategy before publishing." if confidence < 0.5 else "",
    }

def build_hook_plan(analysis: dict[str, Any], requested: str = "Auto") -> dict[str, Any]:
    transcript = (analysis.get("transcript") or {}).get("text", "")
    scenes = analysis.get("scene_changes") or []
    plan = classify_content(transcript, scenes, float(analysis.get("duration") or 0), requested)
    segments = (analysis.get("transcript") or {}).get("segments") or []
    top_lines = []
    for seg in segments:
        line = " ".join(str(seg.get("text", "")).split())
        if line and len(line.split()) >= 4:
            top_lines.append({"start": round(float(seg.get("start", 0)), 2), "end": round(float(seg.get("end", 0)), 2), "text": line[:180]})
    plan["transcript_candidates"] = top_lines[:8]
    plan["candidate_count"] = len(analysis.get("moments") or [])
    plan["review_note"] = "Hook suggestions are editing directions, not claims about guaranteed virality. Verify every title and opening against the actual footage."
    return plan

def strategy_score(base_score: float, speech_density: float, word_density: float, visual_activity: float, hook_count: int, archetype: str) -> float:
    """Strategy-aware weighting for moment ranking; returns a bounded score."""
    if archetype in {"podcast_opinion", "tutorial_education"}:
        weights = (0.42, 0.28, 0.10, 0.20)
    elif archetype in {"funny_unexpected", "sports_action", "reaction_commentary"}:
        weights = (0.15, 0.12, 0.43, 0.30)
    elif archetype == "satisfying_transformation":
        weights = (0.08, 0.05, 0.62, 0.25)
    elif archetype == "story_drama":
        weights = (0.28, 0.20, 0.25, 0.27)
    else:
        weights = (0.24, 0.18, 0.34, 0.24)
    speech, words, visuals, hooks = weights
    return round(max(0.0, min(1.0, speech * speech_density + words * word_density + visuals * visual_activity + hooks * min(1.0, hook_count / 3.0))), 4)
