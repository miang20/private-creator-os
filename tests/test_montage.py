import shutil
import subprocess
from pathlib import Path

import pytest

from core.montage import render_landscape_montage


class Upload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


def _make_clip(path: Path, with_audio: bool) -> bytes:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25"]
    if with_audio:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    command += ["-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        command += ["-c:a", "aac", "-shortest"]
    command += [str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        pytest.skip("FFmpeg build cannot create a synthetic test clip")
    return path.read_bytes()


def test_montage_requires_two_to_four_clips():
    with pytest.raises(ValueError, match="2–4 clips"):
        render_landscape_montage([Upload("one.mp4", b"not-video")])


def test_montage_renders_16_9_and_handles_missing_audio(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg tools are not installed")
    first = _make_clip(tmp_path / "first.mp4", True)
    second = _make_clip(tmp_path / "second.mp4", False)
    rendered, info = render_landscape_montage(
        [Upload("main.mp4", first), Upload("extra.mp4", second)],
        max_seconds_per_clip=10,
        normalize_audio=True,
        output_quality="Fast Preview",
    )
    assert b"ftyp" in rendered[:32]
    assert info["resolution"] == "1920×1080"
    assert info["fps"] == 30
    assert len(info["clips"]) == 2
    assert 3.5 <= info["duration_seconds"] <= 4.1
