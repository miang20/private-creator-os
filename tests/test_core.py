from core.video import parse_segments
from core.packaging import make_packaging, build_caption_plan
from core.planners import plan_story, plan_transformation
from core.automation import choose_moments


def test_parse_segments_accepts_valid_lines():
    assert parse_segments("1,3,first\n4,8,second") == [(1.0, 3.0, "first"), (4.0, 8.0, "second")]


def test_parse_segments_rejects_invalid_range():
    try:
        parse_segments("5,3,bad")
    except ValueError:
        return
    raise AssertionError("Expected invalid range to be rejected")


def test_planner_templates_work_without_api_key():
    assert "TRANSFORMATION PLAN" in plan_transformation("restore a chair", "Short")
    assert "STORY-TO-VIDEO PLAN" in plan_story("a lost dog finds home", "Cinematic")


def test_packaging_and_caption_fallbacks_work_without_api_key():
    assert "TITLE" in make_packaging("a satisfying restoration")
    assert build_caption_plan("this is a small test", 2) == "this is\na small\ntest"


def test_local_moment_ranking_returns_bounded_nonduplicate_windows():
    moments = choose_moments(120, [15, 30, 55, 80, 100], [{"start": 10, "end": 25, "text": "wait this is impossible"}], count=4, clip_length=20)
    assert 1 <= len(moments) <= 4
    assert all(0 <= item["start"] < item["end"] <= 120 for item in moments)
    assert len({item["start"] for item in moments}) == len(moments)
