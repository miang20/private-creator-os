from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _safe_stem(name: str, index: int) -> str:
    stem = Path(name or f"clip_{index}").stem
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem).strip("_")
    return (cleaned or f"clip_{index}")[:48]


def _probe(source: str) -> tuple[float, bool, bool]:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is unavailable. The deployment must install FFmpeg/ffprobe.")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-show_entries", "stream=codec_type", "-of", "json", source],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-1200:] or "Could not inspect an uploaded clip.")
    import json
    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("An uploaded file has no readable duration.") from exc
    streams = data.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if duration <= 0 or not has_video:
        raise ValueError("Every montage input must be a valid video with a video stream.")
    return duration, has_video, has_audio


def _validate_rendered_output(source: str, expected_duration: float) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height,r_frame_rate",
         "-of", "json", source],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError("Rendered MP4 failed ffprobe validation: " + (result.stderr[-1000:] or "unknown probe error"))
    import json
    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        streams = data.get("streams", [])
        video = next(s for s in streams if s.get("codec_type") == "video")
        audio = any(s.get("codec_type") == "audio" for s in streams)
        width, height = int(video["width"]), int(video["height"])
        rate = str(video.get("r_frame_rate", "0/1")).split("/")
        fps = float(rate[0]) / max(1.0, float(rate[1]))
    except (ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError) as exc:
        raise RuntimeError("Rendered MP4 is missing required video/audio metadata.") from exc
    if width != 1920 or height != 1080:
        raise RuntimeError(f"Rendered MP4 has unexpected dimensions: {width}×{height}.")
    if abs(fps - 30.0) > 0.1:
        raise RuntimeError(f"Rendered MP4 is not 30 fps (reported {fps:.3f}).")
    if abs(duration - expected_duration) > max(0.35, expected_duration * 0.03):
        raise RuntimeError(f"Rendered duration mismatch: expected about {expected_duration:.2f}s, got {duration:.2f}s.")
    if not audio:
        raise RuntimeError("Rendered MP4 has no audio stream; expected source audio or a silent fallback track.")
    return {"duration_seconds": round(duration, 2), "resolution": f"{width}×{height}", "fps": round(fps, 3), "has_audio": audio}


def render_landscape_montage(
    uploaded_files: list[Any],
    max_seconds_per_clip: int = 30,
    normalize_audio: bool = True,
    output_quality: str = "Balanced 1080p",
    enhance_visuals: bool = True,
    opening_title: str = "",
) -> tuple[bytes, dict[str, Any]]:
    """Join 2–4 user-supplied video clips into one normalized 16:9 MP4.

    Each clip is capped to max_seconds_per_clip from its beginning. Every segment is
    normalized to 1920x1080, 30 fps, square pixels, H.264/AAC-compatible streams.
    Inputs without audio receive silence so concat remains reliable.
    """
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and ffprobe are required. Check packages.txt and deployment logs.")
    if not 2 <= len(uploaded_files) <= 4:
        raise ValueError("Upload 2–4 clips: one main clip plus 1–3 extra clips.")
    max_seconds_per_clip = max(5, min(180, int(max_seconds_per_clip)))
    quality = (output_quality or "Balanced 1080p").strip().lower()
    crf, preset = ("18", "medium") if quality == "High Quality 1080p" else (("23", "veryfast") if quality == "Fast Preview" else ("20", "veryfast"))

    with tempfile.TemporaryDirectory(prefix="creator_os_montage_") as tmp:
        root = Path(tmp)
        inputs: list[tuple[Path, str, float, bool]] = []
        manifest_rows = []
        for index, uploaded in enumerate(uploaded_files, 1):
            suffix = Path(getattr(uploaded, "name", "")).suffix.lower()
            if suffix not in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
                raise ValueError(f"Clip {index} has an unsupported extension. Use MP4, MOV, M4V, WEBM, or MKV.")
            path = root / f"{index:02d}_{_safe_stem(uploaded.name, index)}{suffix or '.mp4'}"
            path.write_bytes(uploaded.getvalue())
            duration, _, has_audio = _probe(str(path))
            used_duration = min(duration, float(max_seconds_per_clip))
            inputs.append((path, uploaded.name, used_duration, has_audio))
            manifest_rows.append({"clip": uploaded.name, "source_duration_seconds": round(duration, 2), "used_seconds": round(used_duration, 2), "audio": has_audio})

        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for path, _, _, _ in inputs:
            command += ["-i", str(path)]
        filters = []
        concat_labels = []
        title_path = None
        title_text = str(opening_title or "").replace("\\n", " ").strip()[:90]
        if title_text:
            title_path = root / "opening_title.txt"
            title_path.write_text(title_text, encoding="utf-8")
        for i, (_, _, duration, has_audio) in enumerate(inputs):
            video_filter = (
                f"[{i}:v:0]trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
                "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
                "fps=30,setsar=1,format=yuv420p"
            )
            if enhance_visuals:
                video_filter += ",eq=contrast=1.04:saturation=1.05,unsharp=5:5:0.2:3:3:0.0"
            if i == 0 and title_path:
                title_file = str(title_path.resolve()).replace("\\\\", "\\\\\\\\").replace(":", "\\\\:")
                video_filter += f",drawtext=textfile='{title_file}':fontcolor=white:fontsize=48:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.10:enable='lt(t,2.2)'"
            filters.append(video_filter + f"[v{i}]")
            if has_audio:
                filters.append(
                    f"[{i}:a:0]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,"
                    "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    f"apad,atrim=duration={duration:.3f}[a{i}]"
                )
            else:
                filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[a{i}]")
            concat_labels.append(f"[v{i}][a{i}]")
        filters.append("".join(concat_labels) + f"concat=n={len(inputs)}:v=1:a=1[vout][aout]")
        audio_map = "[aout]"
        if normalize_audio:
            filters.append("[aout]loudnorm=I=-14:LRA=11:TP=-1.5[afinal]")
            audio_map = "[afinal]"
        command += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", audio_map]
        command += ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-r", "30", "-movflags", "+faststart"]
        output = root / "creator_os_landscape_montage.mp4"
        command.append(str(output))
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError("Landscape montage render failed: " + (result.stderr[-2500:] or "FFmpeg returned an unknown error."))
        if not output.exists() or output.stat().st_size < 1024:
            raise RuntimeError("The renderer finished without creating a valid MP4.")
        total_duration = sum(row["used_seconds"] for row in manifest_rows)
        verified = _validate_rendered_output(str(output), total_duration)
        return output.read_bytes(), {
            "filename": output.name,
            "bytes": output.stat().st_size,
            **verified,
            "clips": manifest_rows,
            "audio_normalized": bool(normalize_audio),
            "quality": output_quality,
        }
