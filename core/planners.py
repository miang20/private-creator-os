from __future__ import annotations
from .ai import ai_text

def plan_transformation(concept: str, format_type: str) -> str:
    prompt = f"""Create a production-ready transformation video plan.
Concept: {concept}
Format: {format_type}
Include opening hook, 8-12 ordered shots, camera framing/movement, visible progress in every shot, continuity rules, sound design, final payoff, and negative prompts. Do not claim generated footage exists."""
    result = ai_text(prompt, "You are a transformation-video director specializing in satisfying restoration and construction stories.")
    if result:
        return result
    return f"""TRANSFORMATION PLAN: {concept}

FORMAT: {format_type}

1. OPENING HOOK — Show the most damaged / unfinished state and briefly preview the final result.
2. ESTABLISHING SHOT — Wide locked frame; show the full starting condition.
3. PREP — Remove clutter and damaged material; keep the camera angle consistent.
4. CLEAN / STRIP — Close-up of dirt, rust, old paint, or debris being removed.
5. REPAIR — Show a clear before/after change in each shot.
6. STRUCTURAL WORK — Install or rebuild essential elements.
7. DETAIL WORK — Tight shots of sanding, fitting, polishing, painting, or finishing.
8. MIDPOINT REVEAL — Match the opening camera angle and show visible progress.
9. FINAL FINISH — Slow, controlled detail shots with realistic materials.
10. PAYOFF — Reveal the finished result from the same angle as the opening.

CONTINUITY: preserve geometry, layout, lighting direction, and camera position. Every shot must begin where the previous one ended. Show believable intermediate states; avoid instant ruined-to-finished jumps.
NEGATIVE PROMPTS: extra limbs, morphing tools, flickering surfaces, changing layouts, text artifacts."""

def plan_story(premise: str, style: str) -> str:
    prompt = f"""Turn this premise into a scene-by-scene video plan.
Premise: {premise}
Visual style: {style}
Include character bible, setting bible, 8-12 scenes, action, shot size, camera movement, lighting, continuity anchors, and separate image/video prompts."""
    result = ai_text(prompt, "You are a visual story director and continuity supervisor.")
    if result:
        return result
    return f"""STORY-TO-VIDEO PLAN

PREMISE: {premise}
STYLE: {style}

CHARACTER BIBLE
Define age range, face, hair, clothing, silhouette, and one distinguishing feature before generating scenes. Keep appearance unchanged unless the story explicitly changes it.

SETTING BIBLE
Define location, time, palette, weather, and fixed background landmarks. Keep screen direction and geography consistent.

SCENE TEMPLATE
For each scene specify: story goal, one clear visible action, shot size, one camera movement, lighting, continuity anchors, image prompt for the key frame, and video prompt describing movement from that frame.

SUGGESTED BEAT ORDER
Hook → context → desire/problem → complication → escalation → turning point → payoff → final image."""
