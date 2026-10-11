from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

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

def cut_segment(source: str, destination: str, start: float, end: float, vertical: bool = True) -> None:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed. Streamlit Cloud installs it from packages.txt; check deployment logs.")
    if end <= start:
        raise ValueError("Clip end must be after clip start.")
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1" if vertical else "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1"
    command = ["ffmpeg","-hide_banner","-loglevel","error","-y","-ss",str(start),"-i",source,"-t",str(end-start),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-b:a","192k","-movflags","+faststart",destination]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2500:] or "FFmpeg failed while rendering this clip.")
    if not os.path.exists(destination) or os.path.getsize(destination) < 1024:
        raise RuntimeError("FFmpeg returned without a usable output file.")

def render_zip(uploaded_file, segments: Iterable[tuple[float, float, str]], vertical: bool = True) -> bytes:
    segments = list(segments)
    with tempfile.TemporaryDirectory(prefix="creator_os_") as tmp:
        root = Path(tmp)
        source = root / _safe_name(uploaded_file.name)
        source.write_bytes(uploaded_file.getvalue())
        outputs = []
        for index, (start, end, title) in enumerate(segments, 1):
            output = root / f"{index:02d}_{_safe_name(title)}.mp4"
            cut_segment(str(source), str(output), start, end, vertical=vertical)
            outputs.append(output)
        manifest = root / "edit_manifest.txt"
        manifest.write_text("Creator OS edit manifest\nSource: " + uploaded_file.name + "\nAspect: " + ("9:16 vertical" if vertical else "16:9 landscape") + "\nSegments (source timestamps in seconds):\n" + "\n".join(f"{i}. {start:.2f}s–{end:.2f}s | {title}" for i,(start,end,title) in enumerate(segments,1)) + "\n\nUse only media you own or have permission to edit.\n", encoding="utf-8")
        archive = root / "creator_os_export.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for output in outputs:
                zf.write(output, output.name)
            zf.write(manifest, manifest.name)
        return archive.read_bytes()
