from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .hook_engine import classify_content, build_hook_plan, strategy_score


def probe_duration(source: str) -> float:
    """Return media duration in seconds using ffprobe."""
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is unavailable. Install FFmpeg and make sure ffprobe is on PATH.")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", source],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1200:] or "Could not read media metadata.")
    try:
        duration = float(result.stdout.strip())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Media duration could not be determined.") from exc
    if duration <= 0:
        raise RuntimeError("Media duration is zero or invalid.")
    return duration


def detect_scene_changes(source: str, duration: float) -> list[float]:
    """Find rough visual cut points with FFmpeg; this is signal analysis, not semantic AI."""
    if not shutil.which("ffmpeg"):
        return []
    command = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-i", source, "-vf", "fps=2,select=gt(scene\\,0.28),showinfo", "-an", "-f", "null", "-"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=min(300, max(45, int(duration * 0.35))))
    except subprocess.TimeoutExpired:
        return []
    log = (result.stderr or "") + "\n" + (result.stdout or "")
    values = []
    for match in re.finditer(r"pts_time:([0-9]+(?:\\.[0-9]+)?)", log):
        value = float(match.group(1))
        if 0.25 < value < duration - 0.25 and (not values or value - values[-1] > 1.0):
            values.append(value)
    return values


def transcribe_media(source: str, model_size: str = "tiny") -> dict[str, Any]:
    """Run free local Whisper inference. First use may download model weights; host limits apply."""
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError("Local transcription package is unavailable. Check the app deployment logs for faster-whisper installation.") from exc
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=2)
        segments, info = model.transcribe(source, beam_size=1, vad_filter=True, word_timestamps=True)
        transcript_segments, words, text_parts = [], [], []
        for segment in segments:
            text = (segment.text or "").strip()
            if text:
                transcript_segments.append({"start": float(segment.start), "end": float(segment.end), "text": text})
                text_parts.append(text)
            for item in (getattr(segment, "words", None) or []):
                word = (item.word or "").strip()
                if word and item.start is not None and item.end is not None:
                    words.append({"start": float(item.start), "end": float(item.end), "word": word})
        return {"segments": transcript_segments, "words": words, "text": " ".join(text_parts), "language": getattr(info, "language", "unknown")}
    except Exception as exc:
        raise RuntimeError(f"Local transcription failed: {exc}") from exc


def _overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


def choose_moments(duration: float, scene_changes: list[float], transcript_segments: list[dict[str, Any]], count: int = 5, clip_length: int = 30, requested_strategy: str = "Auto") -> list[dict[str, Any]]:
    """Rank windows with strategy-specific weighting rather than one generic score."""
    if duration < 3:
        raise ValueError("Video is too short to make useful clips.")
    transcript_text = " ".join(str(s.get("text", "")) for s in transcript_segments)
    strategy = classify_content(transcript_text, scene_changes, duration, requested_strategy)
    archetype = strategy["key"]
    length = min(float(clip_length), duration)
    step = max(4.0, length / 4.0)
    starts = {max(0.0, min(duration - length, x)) for x in [i * step for i in range(int(max(1, (duration - length) / step)) + 1)]}
    starts.add(max(0.0, duration - length))
    for cut in scene_changes:
        starts.add(max(0.0, min(duration - length, cut - length * 0.35)))
        starts.add(max(0.0, min(duration - length, cut - length * 0.7)))
    hooks = {"why", "how", "wait", "never", "impossible", "finally", "actually", "secret", "crazy", "insane", "best", "worst", "but", "until", "because", "wow", "look", "watch"}
    candidates = []
    for start in sorted(starts):
        end = min(duration, start + length)
        spoken, word_count, hook_count = 0.0, 0, 0
        window_text = []
        for seg in transcript_segments:
            overlap = _overlap(start, end, float(seg["start"]), float(seg["end"]))
            if overlap > 0:
                spoken += overlap
                words = re.findall(r"[A-Za-z']+", str(seg.get("text", "")).lower())
                word_count += len(words)
                hook_count += sum(1 for word in words if word in hooks)
                window_text.append(str(seg.get("text", "")))
        cuts = sum(1 for cut in scene_changes if start <= cut <= end)
        speech_density = min(1.0, spoken / max(1.0, length))
        word_density = min(1.0, word_count / max(1.0, length * 2.2))
        visual_activity = min(1.0, cuts / max(1.0, length / 7.0))
        score = strategy_score(0.0, speech_density, word_density, visual_activity, hook_count, archetype)
        candidates.append({"start": round(start, 2), "end": round(end, 2), "score": score, "words": word_count, "scene_changes": cuts, "_text": " ".join(window_text)})
    candidates.sort(key=lambda x: (-x["score"], x["start"]))
    selected = []
    min_gap = length * 0.70
    for item in candidates:
        if all(abs(item["start"] - old["start"]) >= min_gap for old in selected):
            item = dict(item)
            local_text = item.pop("_text", "")
            if archetype == "podcast_opinion":
                title = "Strong_Statement"
            elif archetype == "tutorial_education":
                title = "Useful_Takeaway"
            elif archetype == "story_drama":
                title = "Story_Turning_Point"
            elif archetype == "sports_action":
                title = "Action_Peak"
            elif archetype == "reaction_commentary":
                title = "Reaction_Payoff"
            elif archetype == "satisfying_transformation":
                title = "Visual_Transformation"
            elif archetype == "funny_unexpected":
                title = "Unexpected_Payoff"
            else:
                title = "Visual_Hook"
            item["title"] = f"{title}_{len(selected) + 1:02d}"
            item["strategy"] = archetype
            item["reason"] = f"Strategy-weighted score for {strategy['label'].lower()}; review actual context and payoff."
            item["transcript_excerpt"] = local_text[:260]
            selected.append(item)
            if len(selected) >= max(1, min(12, int(count))):
                break
    if not selected:
        selected = [{"start": 0.0, "end": round(length, 2), "score": 0.0, "words": 0, "scene_changes": 0, "title": "Visual_Hook_01", "strategy": archetype, "reason": "Fallback window; manually review.", "transcript_excerpt": ""}]
    return sorted(selected, key=lambda x: x["start"])


def analyze_media(source: str, count: int = 5, clip_length: int = 30, transcribe: bool = True, model_size: str = "tiny", requested_strategy: str = "Auto") -> dict[str, Any]:
    duration = probe_duration(source)
    scenes = detect_scene_changes(source, duration)
    transcript = {"segments": [], "words": [], "text": "", "language": "unknown"}
    warning = ""
    if transcribe:
        try:
            transcript = transcribe_media(source, model_size=model_size)
        except Exception as exc:
            warning = str(exc)
    strategy = classify_content(transcript["text"], scenes, duration, requested_strategy)
    moments = choose_moments(duration, scenes, transcript["segments"], count=count, clip_length=clip_length, requested_strategy=strategy["label"])
    method = "local transcript + scene changes" if transcript["segments"] and scenes else "local transcript" if transcript["segments"] else "visual scene-change fallback"
    analysis = {"duration": duration, "scene_changes": scenes, "transcript": transcript, "moments": moments, "warning": warning, "method": method}
    analysis["hook_plan"] = build_hook_plan(analysis, strategy["label"])
    return analysis
