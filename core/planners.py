from __future__ import annotations
from .ai import ai_text
from .hook_engine import classify_content


def plan_transformation(concept: str, format_type: str) -> str:
    clean = " ".join(concept.split())
    fmt = format_type.strip() or "YouTube Short (9:16)"
    shots = [
        ("HOOK / BEFORE", "Open on the most visibly damaged or unfinished detail; show a one-second preview of the finished result, then return to the start state.", "Extreme close-up into wide reveal", "Fast push-in, then locked frame"),
        ("ESTABLISH", "Show the entire object or space, all visible damage, and the fixed camera position that will anchor later match cuts.", "Wide master", "Locked tripod"),
        ("PREP", "Remove clutter and loose debris; show tools and materials before work begins.", "Medium hands-and-work-surface", "Small controlled lateral move"),
        ("CLEAN / STRIP", "Show grime, rust, old coating, or broken material being removed in believable stages.", "Macro detail", "Short slider move"),
        ("REPAIR", "Show one meaningful repair at a time; include the actual tool-to-material contact and resulting change.", "Close-up", "Locked shot with clear action"),
        ("BUILD / REPLACE", "Fit or rebuild essential components; preserve the same layout and orientation between shots.", "Medium three-quarter view", "Slow push-in"),
        ("SURFACE FINISH", "Show sanding, polishing, painting, sealing, or finishing with visible progress and realistic material response.", "Macro texture shot", "Slow lateral move"),
        ("MIDPOINT MATCH", "Repeat the opening angle so viewers can compare the original state with the partially restored state.", "Matched wide shot", "Locked frame"),
        ("DETAIL PASS", "Show two or three satisfying finishing details; avoid repeating the same action or hiding defects with jump cuts.", "Macro sequence", "Gentle controlled movement"),
        ("FINAL PAYOFF", "Reveal the complete result from the original angle, then finish with one clean detail shot and a short hold.", "Wide reveal into close-up", "Slow pull-back then hold"),
    ]
    hook = classify_content(clean, [], 0, "Satisfying / Transformation")
    lines = [f"TRANSFORMATION PRODUCTION PLAN: {clean}", f"FORMAT: {fmt}", "", "GLOBAL RULES", "- Every shot must show a real visible state change or add necessary context.", "- Preserve object geometry, location, lighting direction, tool identity, and camera geography.", "- Use match cuts for before/after comparisons; do not jump from ruined to finished without intermediate states.", "- Keep tool contact believable; no morphing, flickering, or instant material replacement.", "- For Shorts, make the first visual change visible in the first 1–2 seconds; for long-form, allow more process detail.", "", "SHOT LIST"]
    lines.extend(["", "HOOK STRATEGY", f"Primary: {hook['primary']}", f"Opening: {hook['opening']}", "Alternates: " + " · ".join(hook["alternates"]), f"Edit rhythm: {hook['rhythm']}", ""])
    for i, (name, action, framing, movement) in enumerate(shots, 1):
        lines.extend([f"{i:02d}. {name}", f"Action: {action} Target concept: {clean}.", f"Framing: {framing}. Camera: {movement}.", f"Continuity: match the previous shot's state, direction, and lighting; document the new state before cutting.", f"Prompt scaffold: {fmt}; {clean}; {action} {framing}; realistic material detail, consistent geometry, no text artifacts.", ""])
    lines.extend(["SOUND DESIGN", "Use original tool sounds as the primary texture, light room tone underneath, and restrained transitions. Avoid loud effects over important mechanical details.", "", "QUALITY CHECK", "Before export, compare opening and final matched frames, check continuity across every intermediate state, and remove shots that do not show progress."])
    return "\n".join(lines)


def plan_story(premise: str, style: str) -> str:
    clean = " ".join(premise.split())
    visual_style = style.strip() or "Cinematic realistic"
    beats = [
        ("COLD OPEN", "Show the most intriguing consequence without explaining it yet.", "Extreme close-up or striking wide", "One short movement; immediate visual question"),
        ("CONTEXT", "Establish protagonist, place, time, and the normal state that will be disrupted.", "Wide establishing shot", "Slow push-in"),
        ("GOAL", "Show what the protagonist wants through a visible action, not exposition alone.", "Medium shot", "Follow the protagonist's movement"),
        ("INCITING PROBLEM", "Introduce the central obstacle with a clear visual cause-and-effect.", "Medium into close-up", "Whip or motivated pan only if the action justifies it"),
        ("FIRST ATTEMPT", "The protagonist tries a plausible solution; it partly works or reveals a new constraint.", "Over-shoulder / insert", "Controlled tracking"),
        ("ESCALATION", "Make the cost or stakes more visible; change the situation rather than repeat the same beat.", "Tighter framing", "Slightly faster movement"),
        ("LOW POINT", "Show the clearest setback and give the audience a brief emotional pause.", "Still close-up", "Hold; minimal movement"),
        ("TURNING POINT", "Reveal a clue, choice, ally, or new approach that logically changes the plan.", "Reveal from detail to medium", "Slow reveal"),
        ("PAYOFF ACTION", "Resolve the central problem with a concrete action that follows from earlier setup.", "Clear action master plus insert", "Track the action; preserve screen direction"),
        ("FINAL IMAGE", "Show the changed world or character and echo one visual element from the cold open.", "Matched composition", "Slow pull-back or calm hold"),
    ]
    hook = classify_content(clean, [], 0, "Story / Drama")
    lines = ["STORY-TO-VIDEO PRODUCTION PLAN", f"PREMISE: {clean}", f"VISUAL STYLE: {visual_style}", "", "CHARACTER BIBLE", "Define the protagonist's age range, face, hair, body shape, clothing, silhouette, voice, and one identifying detail. Keep these fixed in every prompt. Add a separate entry for each supporting character; do not let wardrobe, face, or scale drift between scenes.", "", "SETTING BIBLE", "Lock location layout, time of day, weather, key background landmarks, light direction, palette, and screen direction. Maintain a simple geography map so entrances, exits, and eyelines match.", "", "SCENE-BY-SCENE PLAN"]
    lines.extend(["", "HOOK STRATEGY", f"Primary: {hook['primary']}", f"Opening: {hook['opening']}", "Alternates: " + " · ".join(hook["alternates"]), f"Edit rhythm: {hook['rhythm']}", ""])
    for i, (name, purpose, framing, movement) in enumerate(beats, 1):
        lines.extend([f"SCENE {i:02d} — {name}", f"Story goal: {purpose}", f"Action: Use the premise '{clean}' to stage one visible action that advances this beat. The character must interact with the environment; avoid abstract emotions without a physical cue.", f"Shot design: {framing}. Camera: {movement}. Style: {visual_style}.", "Lighting: preserve the established direction and motivated practical sources; shift intensity only when the story beat warrants it.", "Continuity anchors: same character identity and wardrobe, consistent props, geography, eyelines, and screen direction. Carry the previous scene's action or emotional consequence forward.", f"Image prompt scaffold: {visual_style}; scene {i} of '{clean}'; {purpose} {framing}; coherent composition, stable character design, readable action, consistent setting.", f"Video prompt scaffold: animate one continuous action for this scene; {movement.lower()}; realistic motion, stable faces and hands, preserve the image prompt's layout and props; no sudden camera teleporting.", ""])
    lines.extend(["EDIT RHYTHM", "Open with the strongest unanswered visual question. Remove repeated information. Let the low point breathe; accelerate the escalation; hold the payoff long enough to read. Use sound bridges only when they preserve cause-and-effect.", "", "FINAL CONTINUITY PASS", "Check character identity, prop positions, hand use, lighting, screen direction, and time progression scene by scene. The plan is a production blueprint and prompt scaffold; it does not mean footage has already been generated."])
    return "\n".join(lines)
