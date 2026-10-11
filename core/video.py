from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def parse_segments(raw: str) -> list[tuple[float, float, str]]:
    """Parse one segment per line: start_seconds,end_seconds,title."""
    segments = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",", 2)]
        if len(parts) < 2:
            raise ValueError(f"Line {line_no}: use start_seconds,end_seconds,title")
        try:
            start, end = float(parts[0]), float(parts[1])
        except ValueError as exc:
            raise ValueError(f"Line {line_no}: timestamps must be numbers in seconds") from exc
        title = parts[2] if len(parts) == 3 and parts[2] else f"clip_{line_no}"
        if start < 0 or end <= start:
            raise ValueError(f"Line {line_no}: end must be greater than start and start cannot be negative")
        segments.append((start, end, title))
    if not segments:
        raise ValueError("Add at least one valid segment.")
    return segments


def _safe_name(value: str) -> str:
    return (re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "clip")[:60]


def _has_video_stream(source: str) -> bool:
    if not shutil.which("ffprobe"):
        return True
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", source], capture_output=True, text=True, timeout=20)
    return result.returncode == 0 and "video" in result.stdout.lower()


def _srt_time(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_caption_srt(path: Path, words: list[dict[str, Any]], start: float, end: float, max_words: int = 3) -> bool:
    selected = []
    for item in words:
        try:
            a, b = float(item["start"]), float(item["end"])
            word = str(item["word"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if word and b > start and a < end and b > a:
            selected.append({"start": max(0.0, a - start), "end": min(end - start, b - start), "word": word})
    chunks = []
    for i in range(0, len(selected), max_words):
        group = selected[i:i + max_words]
        if not group:
            continue
        a, b = group[0]["start"], group[-1]["end"]
        if b <= a:
            b = a + 0.12
        chunks.append(f"{len(chunks)+1}\n{_srt_time(a)} --> {_srt_time(b)}\n{' '.join(w['word'] for w in group)}\n")
    if not chunks:
        return False
    path.write_text("\n".join(chunks), encoding="utf-8")
    return True


def cut_segment(source: str, destination: str, start: float, end: float, vertical: bool = True, subtitle_file: str | None = None, normalize_audio: bool = True, edit_profile: str = "general_visual") -> None:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed. Streamlit Cloud installs it from packages.txt; check deployment logs.")
    if start < 0 or end <= start:
        raise ValueError("Clip end must be after clip start and start cannot be negative.")
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1" if vertical else "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1"
    # Content-specific finishing: restrained by design so source footage stays truthful.
    profile = (edit_profile or "general_visual").strip().lower()
    if profile in {"funny_unexpected", "sports_action", "reaction_commentary"}:
        vf += ",eq=contrast=1.05:saturation=1.08"
    elif profile == "satisfying_transformation":
        vf += ",eq=contrast=1.04:saturation=1.10,unsharp=5:5:0.35:3:3:0.0"
    elif profile in {"podcast_opinion", "tutorial_education"}:
        vf += ",eq=contrast=1.04:saturation=1.02"
    elif profile == "story_drama":
        vf += ",eq=contrast=1.06:saturation=0.96"
    if subtitle_file:
        sub = str(Path(subtitle_file).resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        font_size = 18 if profile in {"podcast_opinion", "tutorial_education"} else 20
        margin_v = 260 if vertical else 70
        style = f"FontName=Arial,FontSize={font_size},PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV={margin_v}".replace(",", "\\,")
        vf += f",subtitles='{sub}':force_style='{style}'"
    has_video = _has_video_stream(source)
    if has_video:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-i", source, "-t", str(end-start), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    else:
        # Podcast/audio-only uploads receive a clean black vertical or landscape canvas.
        size = "1080x1920" if vertical else "1920x1080"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={size}:r=30", "-ss", str(start), "-i", source, "-t", str(end-start), "-map", "0:v:0", "-map", "1:a:0?", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]
    if normalize_audio:
        command[command.index("-c:a"):command.index("-c:a")] = ["-af", "loudnorm=I=-14:LRA=11:TP=-1.5"]
    command.append(destination)
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2500:] or "FFmpeg failed while rendering this clip.")
    if not os.path.exists(destination) or os.path.getsize(destination) < 1024:
        raise RuntimeError("FFmpeg returned without a usable output file.")


def _render_archive(source_path: Path, source_name: str, segments: list[tuple[float, float, str]], vertical: bool, words: list[dict[str, Any]] | None = None, captions: bool = False, normalize_audio: bool = True, notes: str = "", edit_profile: str = "general_visual") -> bytes:
    root = source_path.parent
    outputs = []
    words = words or []
    for index, (start, end, title) in enumerate(segments, 1):
        output = root / f"{index:02d}_{_safe_name(title)}.mp4"
        subtitle_path = root / f"{index:02d}_{_safe_name(title)}.srt"
        subtitle_file = str(subtitle_path) if captions and _write_caption_srt(subtitle_path, words, start, end) else None
        cut_segment(str(source_path), str(output), start, end, vertical=vertical, subtitle_file=subtitle_file, normalize_audio=normalize_audio, edit_profile=edit_profile)
        outputs.append(output)
    manifest = root / "edit_manifest.txt"
    manifest.write_text("Creator OS edit manifest\nSource: " + source_name + "\nContent-specific edit profile: " + edit_profile + "\nAspect: " + ("9:16 vertical" if vertical else "16:9 landscape") + "\nCaptions burned in: " + ("yes" if captions and words else "no (word timestamps unavailable or captions disabled)") + "\nAudio normalization: " + ("on" if normalize_audio else "off") + "\nSegments (source timestamps in seconds):\n" + "\n".join(f"{i}. {start:.2f}s–{end:.2f}s | {title}" for i,(start,end,title) in enumerate(segments,1)) + "\n\n" + notes + "\nUse only media you own or have permission to edit.\n", encoding="utf-8")
    archive = root / "creator_os_export.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for output in outputs:
            zf.write(output, output.name)
        zf.write(manifest, manifest.name)
    return archive.read_bytes()


def render_zip(uploaded_file, segments: Iterable[tuple[float, float, str]], vertical: bool = True) -> bytes:
    segments = list(segments)
    if not segments:
        raise ValueError("Select at least one clip to render.")
    with tempfile.TemporaryDirectory(prefix="creator_os_") as tmp:
        root = Path(tmp)
        source = root / _safe_name(uploaded_file.name)
        source.write_bytes(uploaded_file.getvalue())
        return _render_archive(source, uploaded_file.name, segments, vertical=vertical)


def render_auto_zip(uploaded_file, moments: list[dict[str, Any]], words: list[dict[str, Any]] | None = None, vertical: bool = True, captions: bool = True, normalize_audio: bool = True, notes: str = "", edit_profile: str = "general_visual") -> bytes:
    """Render ranked auto-detected moments and optionally burn local Whisper word captions."""
    segments = [(float(m["start"]), float(m["end"]), str(m.get("title") or f"Moment_{i+1:02d}")) for i, m in enumerate(moments)]
    if not segments:
        raise ValueError("No moment candidates were found. Try a shorter clip length or inspect the source media.")
    with tempfile.TemporaryDirectory(prefix="creator_os_auto_") as tmp:
        root = Path(tmp)
        source = root / _safe_name(uploaded_file.name)
        source.write_bytes(uploaded_file.getvalue())
        return _render_archive(source, uploaded_file.name, segments, vertical=vertical, words=words, captions=captions, normalize_audio=normalize_audio, notes=notes, edit_profile=edit_profile)
