import shutil
import subprocess
from core.video import parse_segments, cut_segment, _write_caption_srt, _caption_force_style, _quality_settings, _active_intervals, _remap_words_to_intervals, _concat_active_intervals
from core.packaging import make_packaging, build_caption_plan
from core.planners import plan_story, plan_transformation
from core.automation import choose_moments
from core.hook_engine import classify_content, strategy_score


def test_parse_segments_accepts_valid_lines():
    assert parse_segments("1,3,first\n4,8,second") == [(1.0, 3.0, "first"), (4.0, 8.0, "second")]


def test_parse_segments_rejects_invalid_range():
    import pytest
    with pytest.raises(ValueError):
        parse_segments("5,3,bad")


def test_planner_templates_work_without_api_key():
    assert "TRANSFORMATION PRODUCTION PLAN" in plan_transformation("restore a chair", "Short")
    story = plan_story("a lost dog finds home", "Cinematic")
    assert "STORY-TO-VIDEO PRODUCTION PLAN" in story
    assert "SCENE 10" in story
    assert "HOOK STRATEGY" in story
    assert "HOOK STRATEGY" in plan_transformation("restore a chair", "Short")


def test_packaging_and_caption_fallbacks_work_without_api_key():
    assert "TITLE OPTIONS" in make_packaging("a satisfying restoration", content_type="Satisfying / Transformation")
    assert build_caption_plan("this is a small test", 2) == "this is\na small\ntest"


def test_strategy_router_uses_distinct_content_archetypes():
    funny = classify_content("Wait for it, that was a hilarious unexpected fail", [], 30)
    podcast = classify_content("I think the problem is people never explain the reason", [], 30)
    tutorial = classify_content("Here is how to fix this mistake, first step", [], 30)
    satisfying = classify_content("Watch this restoration and polishing transformation", [2, 4, 8], 20)
    assert funny["key"] == "funny_unexpected"
    assert podcast["key"] == "podcast_opinion"
    assert tutorial["key"] == "tutorial_education"
    assert satisfying["key"] == "satisfying_transformation"
    assert funny["mode"] == "transcript-signals"
    assert funny["confidence"] < 1.0
    assert len(set([funny["primary"], podcast["primary"], tutorial["primary"], satisfying["primary"]])) == 4


def test_strategy_score_prioritizes_visual_activity_for_visual_niches():
    visual_low = strategy_score(0.0, 0.5, 0.5, 0.1, 0, "satisfying_transformation")
    visual_high = strategy_score(0.0, 0.5, 0.5, 0.9, 0, "satisfying_transformation")
    speech_low = strategy_score(0.0, 0.5, 0.5, 0.1, 0, "podcast_opinion")
    speech_high = strategy_score(0.0, 0.5, 0.5, 0.9, 0, "podcast_opinion")
    assert visual_high - visual_low > speech_high - speech_low


def test_local_moment_ranking_returns_bounded_nonduplicate_windows():
    moments = choose_moments(120, [15, 30, 55, 80, 100], [{"start": 10, "end": 25, "text": "wait this is impossible"}], count=4, clip_length=20)
    assert 1 <= len(moments) <= 4
    assert all(0 <= item["start"] < item["end"] <= 120 for item in moments)
    assert len({item["start"] for item in moments}) == len(moments)
    assert all(item["strategy"] for item in moments)


def test_caption_srt_uses_clip_relative_word_timestamps(tmp_path):
    srt = tmp_path / "caption.srt"
    words = [{"start": 11.0, "end": 11.3, "word": "Hello"}, {"start": 11.3, "end": 11.6, "word": "there"}, {"start": 12.0, "end": 12.3, "word": "friend"}]
    assert _write_caption_srt(srt, words, 10.0, 15.0)
    result = srt.read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:02,300" in result
    assert "Hello there friend" in result


def test_ffmpeg_renders_clip_with_burned_captions_and_normalized_audio(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        import pytest
        pytest.skip("FFmpeg tools are not installed")
    source = tmp_path / "source.mp4"
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100",
        "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        import pytest
        pytest.skip("FFmpeg build cannot create the synthetic test video")
    srt = tmp_path / "captions.srt"
    srt.write_text("1\n00:00:00,200 --> 00:00:01,200\nHello there\n", encoding="utf-8")
    output = tmp_path / "rendered.mp4"
    cut_segment(str(source), str(output), 0, 3, vertical=True, subtitle_file=str(srt), normalize_audio=True, edit_profile="satisfying_transformation", dynamic_zoom=True, hook_text="WATCH THIS", output_quality="Fast Preview")
    assert output.exists() and output.stat().st_size > 1024



def test_caption_style_presets_are_readable_and_format_aware():
    creator_vertical = _caption_force_style("Creator Pop", vertical=True)
    white_landscape = _caption_force_style("Clean White", vertical=False)
    assert "FontSize=56" in creator_vertical
    assert "PrimaryColour=&H0000FFFF" in creator_vertical
    assert "FontSize=38" in white_landscape
    assert "PrimaryColour=&H00FFFFFF" in white_landscape


def test_export_quality_presets_map_to_expected_encoding_cost():
    assert _quality_settings("High Quality 1080p") == ("18", "medium")
    assert _quality_settings("Balanced 1080p") == ("20", "veryfast")
    assert _quality_settings("Fast Preview") == ("23", "veryfast")



def test_silence_removal_intervals_preserve_small_cut_margins():
    intervals = _active_intervals(0.0, 6.0, [(2.0, 4.0)])
    assert len(intervals) == 2
    assert intervals[0][0] == 0.0
    assert intervals[0][1] == 2.08
    assert intervals[1][0] == 3.92
    assert intervals[1][1] == 6.0


def test_caption_word_timestamps_are_remapped_after_silence_cuts():
    words = [
        {"start": 1.0, "end": 1.3, "word": "Keep"},
        {"start": 2.4, "end": 2.7, "word": "remove"},
        {"start": 4.2, "end": 4.5, "word": "gap"},
    ]
    mapped = _remap_words_to_intervals(words, [(0.0, 2.0), (4.0, 6.0)])
    assert [item["word"] for item in mapped] == ["Keep", "gap"]
    assert mapped[1]["start"] == 2.2


def test_silence_concat_keeps_video_and_audio_in_sync(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        import pytest
        pytest.skip("FFmpeg tools are not installed")
    source = tmp_path / "source_concat.mp4"
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        import pytest
        pytest.skip("FFmpeg build cannot create the synthetic test video")
    output = tmp_path / "trimmed.mp4"
    duration = _concat_active_intervals(str(source), [(0.0, 1.0), (2.0, 3.0)], str(output))
    assert output.exists() and output.stat().st_size > 1024
    assert duration == 2.0
