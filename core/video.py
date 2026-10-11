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




def _has_audio_stream(source: str) -> bool:
    if not shutil.which("ffprobe"):
        return False
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", source],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode == 0 and "audio" in result.stdout.lower()


def _detect_silences(source: str) -> list[tuple[float, float]]:
    """Detect sustained low-volume gaps once per source; timestamps are source-relative."""
    if not _has_audio_stream(source) or not shutil.which("ffmpeg"):
        return []
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", source, "-vn",
         "-af", "silencedetect=noise=-38dB:d=0.65", "-f", "null", "-"],
        capture_output=True, text=True, timeout=900,
    )
    if result.returncode not in (0, 1):
        return []
    log = (result.stderr or "") + "\n" + (result.stdout or "")
    silences = []
    pending_start = None
    for line in log.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)", line)
        end_match = re.search(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)", line)
        if start_match:
            pending_start = float(start_match.group(1))
        if end_match and pending_start is not None:
            end = float(end_match.group(1))
            if end - pending_start >= 0.65:
                silences.append((pending_start, end))
            pending_start = None
    if pending_start is not None:
        duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", log)
        if duration_match:
            duration = int(duration_match.group(1)) * 3600 + int(duration_match.group(2)) * 60 + float(duration_match.group(3))
            if duration - pending_start >= 0.65:
                silences.append((pending_start, duration))
    return silences


def _active_intervals(start: float, end: float, silences: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Keep active sections while preserving a small amount of silence around cuts."""
    removed = []
    for silence_start, silence_end in silences:
        a = max(start, silence_start + 0.08)
        b = min(end, silence_end - 0.08)
        if b - a >= 0.50:
            removed.append((a, b))
    removed.sort()
    merged = []
    for a, b in removed:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    active = []
    cursor = start
    for a, b in merged:
        if a - cursor >= 0.18:
            active.append((cursor, a))
        cursor = max(cursor, b)
    if end - cursor >= 0.18:
        active.append((cursor, end))
    return active or [(start, end)]


def _remap_words_to_intervals(words: list[dict[str, Any]], intervals: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Map original word timestamps onto the concatenated silence-trimmed timeline."""
    mapped = []
    offset = 0.0
    for interval_start, interval_end in intervals:
        for item in words:
            try:
                a, b = float(item["start"]), float(item["end"])
                word = str(item["word"]).strip()
            except (KeyError, TypeError, ValueError):
                continue
            left, right = max(a, interval_start), min(b, interval_end)
            if word and right > left:
                mapped.append({"start": offset + left - interval_start, "end": offset + right - interval_start, "word": word})
        offset += interval_end - interval_start
    return sorted(mapped, key=lambda item: item["start"])



def _overlay_broll(source: str, broll: str, destination: str, start: float, end: float) -> bool:
    """Insert short full-frame B-roll cutaways while retaining the source audio."""
    duration = end - start
    if duration < 3.3 or not _has_video_stream(broll):
        return False
    cutaways = [t for t in (2.5 + 4.0 * i for i in range(100)) if t + 0.8 < duration]
    if not cutaways:
        return False
    enable = "+".join(f"between(t,{t:.2f},{t + 0.8:.2f})" for t in cutaways)
    if _has_video_stream(source):
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-ss", str(start), "-t", str(duration), "-i", source,
                   "-stream_loop", "-1", "-i", broll,
                   "-filter_complex",
                   f"[1:v][0:v]scale2ref=w=rw:h=rh[broll][base];[base][broll]overlay=shortest=1:enable='{enable}'[vout]",
                   "-map", "[vout]", "-map", "0:a?"]
    else:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r=30:d={duration}",
                   "-ss", str(start), "-t", str(duration), "-i", source,
                   "-stream_loop", "-1", "-i", broll,
                   "-filter_complex",
                   f"[2:v][0:v]scale2ref=w=rw:h=rh[broll][base];[base][broll]overlay=shortest=1:enable='{enable}'[vout]",
                   "-map", "[vout]", "-map", "1:a?"]
    command += ["-t", str(duration), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", destination]
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode != 0 or not os.path.exists(destination) or os.path.getsize(destination) < 1024:
        raise RuntimeError("B-roll cutaway render failed: " + (result.stderr[-1800:] or "No usable output."))
    return True


def _concat_active_intervals(source: str, intervals: list[tuple[float, float]], destination: str) -> float:
    """Concatenate non-silent intervals, keeping video and audio synchronized."""
    if not intervals:
        raise ValueError("Silence removal left no usable content.")
    has_video = _has_video_stream(source)
    filters = []
    labels = []
    for i, (start, end) in enumerate(intervals):
        if has_video:
            filters.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]")
        filters.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]" if has_video else f"[a{i}]")
    if has_video:
        filters.append("".join(labels) + f"concat=n={len(intervals)}:v=1:a=1[vout][aout]")
        maps = ["-map", "[vout]", "-map", "[aout]"]
    else:
        filters.append("".join(labels) + f"concat=n={len(intervals)}:v=0:a=1[aout]")
        maps = ["-map", "[aout]"]
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", source,
               "-filter_complex", ";".join(filters), *maps]
    if has_video:
        command += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18"]
    command += ["-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", destination]
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode != 0 or not os.path.exists(destination) or os.path.getsize(destination) < 1024:
        raise RuntimeError("Silence-removal render failed: " + (result.stderr[-1800:] or "No usable intermediate output."))
    return sum(end - start for start, end in intervals)


def _caption_force_style(caption_style: str, vertical: bool) -> str:
    """Return readable caption styling for the selected export preset."""
    preset = (caption_style or "Creator Pop").strip().lower()
    if preset == "clean white":
        color, outline, bold = "&H00FFFFFF", 3, -1
        font_size, margin_v = (48, 270) if vertical else (38, 70)
    elif preset == "classic yellow":
        color, outline, bold = "&H0000FFFF", 3, -1
        font_size, margin_v = (50, 270) if vertical else (40, 70)
    else:
        color, outline, bold = "&H0000FFFF", 5, -1
        font_size, margin_v = (56, 285) if vertical else (44, 76)
    style = f"FontName=Arial,FontSize={font_size},Bold={bold},PrimaryColour={color},OutlineColour=&H00000000,BorderStyle=1,Outline={outline},Shadow=2,Alignment=2,MarginV={margin_v}"
    return style.replace(",", r"\,")


def _quality_settings(output_quality: str) -> tuple[str, str]:
    preset = (output_quality or "Balanced 1080p").strip().lower()
    if preset == "high quality 1080p":
        return "18", "medium"
    if preset == "fast preview":
        return "23", "veryfast"
    return "20", "veryfast"


def cut_segment(source: str, destination: str, start: float, end: float, vertical: bool = True, subtitle_file: str | None = None, normalize_audio: bool = True, edit_profile: str = "general_visual", dynamic_zoom: bool = False, caption_style: str = "Creator Pop", output_quality: str = "Balanced 1080p", hook_text: str | None = None, zoom_strength: float = 0.04, crop_position: float = 0.5) -> None:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed. Streamlit Cloud installs it from packages.txt; check deployment logs.")
    if start < 0 or end <= start:
        raise ValueError("Clip end must be after clip start and start cannot be negative.")
    output_size = "1080x1920" if vertical else "1920x1080"
    crop_position = max(0.0, min(1.0, float(crop_position)))
    vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:x='(iw-1080)*{crop_position:.3f}':y='(ih-1920)/2'" if vertical else "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    if dynamic_zoom:
        # Gentle centered zoom pulse; this is not AI subject tracking.
        zoom_strength = max(0.01, min(0.10, float(zoom_strength)))
        vf += f",zoompan=z='1+{zoom_strength:.3f}*(1-cos(2*PI*on/150))/2':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={output_size}:fps=30"
    vf += ",fps=30,setsar=1"
    # Add an optional opening hook using a text file so punctuation cannot break FFmpeg parsing.
    hook_path = None
    if hook_text:
        hook_path = Path(destination).with_suffix(".hook.txt")
        hook_path.write_text(str(hook_text).replace("\n", " ")[:90], encoding="utf-8")
        hook_file = str(hook_path.resolve()).replace("\\", "\\\\").replace(":", "\\:")
        hook_size = 58 if vertical else 46
        vf += f",drawtext=textfile='{hook_file}':fontcolor=white:fontsize={hook_size}:borderw=4:bordercolor=black:x=(w-text_w)/2:y=h*0.12:enable='lt(t,1.8)'"
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
        style = _caption_force_style(caption_style, vertical)
        vf += f",subtitles='{sub}':force_style='{style}'"
    has_video = _has_video_stream(source)
    if has_video:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-i", source, "-t", str(end-start), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    else:
        # Podcast/audio-only uploads receive a clean black vertical or landscape canvas.
        size = "1080x1920" if vertical else "1920x1080"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={size}:r=30", "-ss", str(start), "-i", source, "-t", str(end-start), "-map", "0:v:0", "-map", "1:a:0?", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]
    crf, encoder_preset = _quality_settings(output_quality)
    if "-crf" in command:
        command[command.index("-crf") + 1] = crf
    if "-preset" in command:
        command[command.index("-preset") + 1] = encoder_preset
    if normalize_audio:
        command[command.index("-c:a"):command.index("-c:a")] = ["-af", "loudnorm=I=-14:LRA=11:TP=-1.5"]
    command.append(destination)
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2500:] or "FFmpeg failed while rendering this clip.")
    if not os.path.exists(destination) or os.path.getsize(destination) < 1024:
        raise RuntimeError("FFmpeg returned without a usable output file.")


def _render_archive(source_path: Path, source_name: str, segments: list[tuple[float, float, str]], vertical: bool, words: list[dict[str, Any]] | None = None, captions: bool = False, normalize_audio: bool = True, notes: str = "", edit_profile: str = "general_visual", dynamic_zoom: bool = False, caption_style: str = "Creator Pop", output_quality: str = "Balanced 1080p", hook_texts: list[str] | None = None, remove_silence: bool = False, zoom_strength: float = 0.04, caption_words_per_beat: int = 3, crop_position: float = 0.5, broll_path: str | None = None) -> bytes:
    root = source_path.parent
    outputs = []
    words = words or []
    silences = _detect_silences(str(source_path)) if remove_silence else []
    for index, (start, end, title) in enumerate(segments, 1):
        output = root / f"{index:02d}_{_safe_name(title)}.mp4"
        subtitle_path = root / f"{index:02d}_{_safe_name(title)}.srt"
        intervals = _active_intervals(start, end, silences) if remove_silence else [(start, end)]
        did_remove = bool(remove_silence and (len(intervals) > 1 or intervals[0][0] > start + 0.10 or intervals[-1][1] < end - 0.10))
        render_source = source_path
        render_start, render_end = start, end
        caption_words = words
        if did_remove:
            silence_cut = root / f"{index:02d}_{_safe_name(title)}_silencecut.mp4"
            render_end = _concat_active_intervals(str(source_path), intervals, str(silence_cut))
            render_source = silence_cut
            render_start = 0.0
            caption_words = _remap_words_to_intervals(words, intervals)
        if broll_path:
            broll_output = root / f"{index:02d}_{_safe_name(title)}_broll.mp4"
            if _overlay_broll(str(render_source), broll_path, str(broll_output), render_start, render_end):
                if not did_remove:
                    caption_words = _remap_words_to_intervals(words, [(start, end)])
                    subtitle_file = str(subtitle_path) if captions and _write_caption_srt(subtitle_path, caption_words, 0.0, end - start, max_words=max(1, min(3, int(caption_words_per_beat)))) else None
                render_source = broll_output
                render_start, render_end = 0.0, render_end - render_start
        hook_text = hook_texts[index - 1] if hook_texts and index <= len(hook_texts) else None
        cut_segment(str(render_source), str(output), render_start, render_end, vertical=vertical, subtitle_file=subtitle_file, normalize_audio=normalize_audio, edit_profile=edit_profile, dynamic_zoom=dynamic_zoom, caption_style=caption_style, output_quality=output_quality, hook_text=hook_text, zoom_strength=zoom_strength, crop_position=crop_position)
        outputs.append(output)
    manifest = root / "edit_manifest.txt"
    manifest.write_text("Creator OS edit manifest\nSource: " + source_name + "\nContent-specific edit profile: " + edit_profile + "\nAspect: " + ("9:16 vertical" if vertical else "16:9 landscape") + "\nCaptions burned in: " + ("yes" if captions and words else "no (word timestamps unavailable or captions disabled)") + "\nCaption style: " + caption_style + "\nOutput quality: " + output_quality + "\nDynamic zoom: " + ("on" if dynamic_zoom else "off") + "\nSilence removal: " + ("on" if remove_silence else "off") + "\nAudio normalization: " + ("on" if normalize_audio else "off") + "\nSegments (source timestamps in seconds):\n" + "\n".join(f"{i}. {start:.2f}s–{end:.2f}s | {title}" for i,(start,end,title) in enumerate(segments,1)) + "\n\n" + notes + "\nUse only media you own or have permission to edit.\n", encoding="utf-8")
    archive = root / "creator_os_export.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for output in outputs:
            zf.write(output, output.name)
        zf.write(manifest, manifest.name)
    return archive.read_bytes()


def render_zip(uploaded_file, segments: Iterable[tuple[float, float, str]], vertical: bool = True, dynamic_zoom: bool = False, caption_style: str = "Creator Pop", output_quality: str = "Balanced 1080p", remove_silence: bool = False, zoom_strength: float = 0.04, crop_position: float = 0.5) -> bytes:
    segments = list(segments)
    if not segments:
        raise ValueError("Select at least one clip to render.")
    with tempfile.TemporaryDirectory(prefix="creator_os_") as tmp:
        root = Path(tmp)
        source = root / _safe_name(uploaded_file.name)
        source.write_bytes(uploaded_file.getvalue())
        return _render_archive(source, uploaded_file.name, segments, vertical=vertical, dynamic_zoom=dynamic_zoom, caption_style=caption_style, output_quality=output_quality, remove_silence=remove_silence, zoom_strength=zoom_strength, crop_position=crop_position)


def render_auto_zip(uploaded_file, moments: list[dict[str, Any]], words: list[dict[str, Any]] | None = None, vertical: bool = True, captions: bool = True, normalize_audio: bool = True, notes: str = "", edit_profile: str = "general_visual", dynamic_zoom: bool = False, caption_style: str = "Creator Pop", output_quality: str = "Balanced 1080p", hook_overlay: bool = False, remove_silence: bool = False, zoom_strength: float = 0.04, caption_words_per_beat: int = 3, crop_position: float = 0.5, broll_file: Any | None = None) -> bytes:
    """Render ranked auto-detected moments and optionally burn local Whisper word captions."""
    segments = [(float(m["start"]), float(m["end"]), str(m.get("title") or f"Moment_{i+1:02d}")) for i, m in enumerate(moments)]
    if not segments:
        raise ValueError("No moment candidates were found. Try a shorter clip length or inspect the source media.")
    with tempfile.TemporaryDirectory(prefix="creator_os_auto_") as tmp:
        root = Path(tmp)
        source = root / _safe_name(uploaded_file.name)
        source.write_bytes(uploaded_file.getvalue())
        broll_path = None
        if broll_file is not None:
            broll_path_obj = root / ("broll_" + _safe_name(broll_file.name))
            broll_path_obj.write_bytes(broll_file.getvalue())
            broll_path = str(broll_path_obj)
        hook_texts = []
        if hook_overlay:
            for i, moment in enumerate(moments, 1):
                text = str(moment.get("transcript_excerpt") or moment.get("title") or f"Moment {i}").strip()
                hook_texts.append(re.sub(r"\s+", " ", text)[:90])
        return _render_archive(source, uploaded_file.name, segments, vertical=vertical, words=words, captions=captions, normalize_audio=normalize_audio, notes=notes, edit_profile=edit_profile, dynamic_zoom=dynamic_zoom, caption_style=caption_style, output_quality=output_quality, hook_texts=hook_texts, remove_silence=remove_silence, zoom_strength=zoom_strength, caption_words_per_beat=caption_words_per_beat, crop_position=crop_position, broll_path=broll_path)
