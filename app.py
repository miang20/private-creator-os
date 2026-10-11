from __future__ import annotations
import csv
import io
import tempfile
from pathlib import Path
import streamlit as st
from core.config import youtube_api_key
from core.automation import analyze_media
from core.packaging import make_packaging, build_caption_plan
from core.planners import plan_story, plan_transformation
from core.research import search_youtube
from core.video import ffmpeg_available, parse_segments, render_zip, render_auto_zip


def to_csv(items):
    buf = io.StringIO()
    fields = ["title", "channel", "published_at", "views", "url"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(items)
    return buf.getvalue()


def analyze_uploaded(source, count: int, clip_length: int, transcribe: bool, model_size: str = "tiny"):
    suffix = Path(source.name).suffix or ".mp4"
    with tempfile.TemporaryDirectory(prefix="creator_os_analysis_") as tmp:
        path = Path(tmp) / ("source" + suffix)
        path.write_bytes(source.getvalue())
        return analyze_media(str(path), count=count, clip_length=clip_length, transcribe=transcribe, model_size=model_size)


def show_moments(analysis):
    rows = [{"Clip": m["title"], "Start (s)": m["start"], "End (s)": m["end"], "Score": m["score"], "Words": m["words"], "Scene changes": m["scene_changes"]} for m in analysis["moments"]]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"Duration: {analysis['duration']:.1f}s · Detection: {analysis['method']} · Scene changes found: {len(analysis['scene_changes'])}")


st.set_page_config(page_title="Creator OS", page_icon="🎬", layout="wide")
st.title("🎬 Creator OS")
st.caption("Free-first creator workspace · Research → Analyze → Edit → Package")
with st.sidebar:
    st.header("Your studio")
    module = st.radio("Select module", ["Repurposing Studio", "Breakout Radar", "Transformation Planner", "Story-to-Video Studio", "Podcast-to-Shorts", "Packaging Lab"])
    st.divider()
    st.markdown("**System status**")
    st.write("Paid AI API:", "Disabled in this build")
    st.write("Local transcription:", "faster-whisper / tiny model")
    st.write("YouTube Data API:", "Optional (free quota applies)" if youtube_api_key() else "Optional key not configured")
    st.write("FFmpeg:", "Available" if ffmpeg_available() else "Not found")
    st.caption("No paid AI API key is used. First transcription can download model weights; host CPU/RAM/runtime limits apply.")
st.info("Free-first creator workspace. Automatic analysis runs on the app host; longer videos may be slow or exceed free-host limits. Upload only media you own or are licensed to process.")

if module == "Repurposing Studio":
    st.subheader("Automatic Long-Video Repurposing")
    st.write("Upload a video, let local analysis rank candidate moments, then export vertical or landscape clips. Ranking uses local Whisper transcription (if enabled), speech density, hook-word heuristics, and FFmpeg scene changes; it is a heuristic, not human-level semantic judgment.")
    source = st.file_uploader("Upload source video", type=["mp4", "mov", "m4v", "webm", "mkv"], key="repurpose_source")
    c1, c2, c3 = st.columns(3)
    with c1:
        clip_count = st.slider("Clips to export", 1, 10, 5, key="repurpose_count")
    with c2:
        clip_length = st.slider("Target clip length (seconds)", 15, 60, 30, step=5, key="repurpose_length")
    with c3:
        aspect = st.selectbox("Output format", ["Vertical 9:16 (Shorts)", "Landscape 16:9"], key="repurpose_aspect")
    t1, t2 = st.columns(2)
    with t1:
        transcribe = st.checkbox("Run free local transcription", value=True, key="repurpose_transcribe")
    with t2:
        captions = st.checkbox("Burn word-timed captions when available", value=True, key="repurpose_captions", disabled=not transcribe)
    normalize = st.checkbox("Normalize audio for consistent loudness", value=True, key="repurpose_normalize")
    if st.button("Analyze, select moments & render clips", type="primary", disabled=source is None, key="auto_repurpose"):
        try:
            with st.spinner("Analyzing media locally. First run may download the tiny Whisper model; this can take several minutes…"):
                analysis = analyze_uploaded(source, clip_count, clip_length, transcribe)
            st.session_state["repurpose_analysis"] = analysis
            st.session_state["repurpose_analysis_name"] = source.name
            show_moments(analysis)
            if analysis["warning"]:
                st.warning(analysis["warning"] + " Continuing with available visual analysis.")
            if transcribe and not analysis["transcript"]["segments"]:
                st.warning("No transcript was produced. Clips can still be selected from scene changes, but captions will not be burned in.")
            notes = f"Detection method: {analysis['method']}\nRank scores are heuristic, not guaranteed viral predictions."
            with st.spinner("Rendering MP4 clips and preparing ZIP…"):
                archive = render_auto_zip(source, analysis["moments"], words=analysis["transcript"]["words"], vertical=aspect.startswith("Vertical"), captions=captions, normalize_audio=normalize, notes=notes)
            st.success(f"Finished: {len(analysis['moments'])} clip(s) rendered.")
            st.download_button("Download automatic clip pack (.zip)", archive, file_name="creator_os_auto_clips.zip", mime="application/zip", key="download_auto_repurpose")
            with st.expander("Transcript preview"):
                st.write(analysis["transcript"]["text"][:12000] or "No transcript available for this run.")
        except Exception as exc:
            st.error(f"Automatic repurposing failed: {exc}")
    st.divider()
    st.markdown("**Manual timestamp mode**")
    st.caption("Fallback for precise edits or when local analysis is unavailable.")
    manual_source = st.file_uploader("Upload source for manual clipping", type=["mp4", "mov", "m4v", "webm", "mkv"], key="manual_repurpose_source")
    aspect_manual = st.radio("Manual output format", ["Vertical 9:16 (Shorts)", "Landscape 16:9"], horizontal=True, key="manual_aspect")
    segment_text = st.text_area("Clip timestamp plan (start_seconds,end_seconds,title)", value="12,28,Best_Moment\n35,52,Second_Moment", height=100)
    if st.button("Render manual clips", disabled=manual_source is None, key="manual_render"):
        try:
            segments = parse_segments(segment_text)
            with st.spinner("Rendering with FFmpeg…"):
                archive = render_zip(manual_source, segments, vertical=aspect_manual.startswith("Vertical"))
            st.download_button("Download manual clip pack (.zip)", archive, "creator_os_manual_clips.zip", "application/zip", key="download_manual")
        except Exception as exc:
            st.error(str(exc))
    st.divider()
    transcript = st.text_area("Paste an existing transcript for 1–3 word caption beats", key="repurpose_transcript")
    if st.button("Create caption beat plan", key="caption_plan") and transcript.strip():
        result = build_caption_plan(transcript)
        st.text_area("Caption beats", result, height=180)
        st.download_button("Download caption plan", result, "caption_beats.txt", "text/plain")

elif module == "Breakout Radar":
    st.subheader("New-Channel Breakout Radar")
    st.write("Search public videos using the official YouTube Data API. The API's free daily quota still applies; no unofficial scraping is used.")
    query = st.text_input("Search topic / niche", placeholder="e.g. satisfying restoration shorts")
    count = st.slider("Public videos to inspect", 5, 25, 10)
    if st.button("Search YouTube", type="primary", disabled=not query.strip()):
        with st.spinner("Querying public YouTube data…"):
            result = search_youtube(query, count)
        if not result["configured"]:
            st.warning(result["message"])
            st.markdown("You can still open a direct YouTube search: [Search this topic](https://www.youtube.com/results?search_query=" + query.strip().replace(" ", "+") + ")")
        elif result["items"]:
            st.caption(result["message"])
            st.dataframe(result["items"], use_container_width=True, hide_index=True)
            st.download_button("Download research CSV", to_csv(result["items"]), "breakout_radar.csv", "text/csv")
        else:
            st.error(result["message"])
    st.caption("Views are snapshots. They do not prove new-channel growth, audience retention, or future performance.")

elif module == "Transformation Planner":
    st.subheader("Free Transformation Video Planner")
    concept = st.text_area("Transformation idea", placeholder="e.g. restore a rusted vintage motorcycle")
    fmt = st.selectbox("Target format", ["YouTube Short (9:16)", "YouTube long-form (16:9)", "Both"])
    if st.button("Build transformation plan", type="primary", disabled=not concept.strip()):
        result = plan_transformation(concept, fmt)
        st.text_area("Production plan", result, height=440)
        st.download_button("Download plan", result, "transformation_plan.txt", "text/plain")

elif module == "Story-to-Video Studio":
    st.subheader("Free Story-to-Video Studio")
    premise = st.text_area("Story premise", placeholder="Describe the protagonist, conflict, and payoff…")
    style = st.selectbox("Visual style", ["Cinematic realistic", "Stylized 3D", "Anime-inspired", "Documentary"])
    if st.button("Create scene plan", type="primary", disabled=not premise.strip()):
        result = plan_story(premise, style)
        st.text_area("Scene and continuity plan", result, height=460)
        st.download_button("Download scene plan", result, "story_scene_plan.txt", "text/plain")
    st.caption("This creates production instructions and prompts, not finished generated footage; free local video generation is not bundled into this hosted app.")

elif module == "Podcast-to-Shorts":
    st.subheader("Automatic Podcast-to-Shorts Factory")
    st.write("Use local Whisper to transcribe audio/video, rank speech-dense moments, add word-timed captions when available, normalize audio, and export clips. Ranking is heuristic; review clips before publishing.")
    source = st.file_uploader("Upload podcast, interview, or audio", type=["mp4", "mov", "m4v", "webm", "mkv", "mp3", "wav", "m4a"], key="podcast_source")
    p1, p2 = st.columns(2)
    with p1:
        count = st.slider("Podcast clips", 1, 10, 5, key="podcast_count")
    with p2:
        length = st.slider("Clip length (seconds)", 15, 90, 45, step=5, key="podcast_length")
    p3, p4 = st.columns(2)
    with p3:
        podcast_aspect = st.selectbox("Podcast output", ["Vertical 9:16 (Shorts)", "Landscape 16:9"], key="podcast_aspect")
    with p4:
        podcast_captions = st.checkbox("Burn captions when word timestamps exist", value=True, key="podcast_captions")
    if st.button("Transcribe, find moments & render", type="primary", disabled=source is None, key="auto_podcast"):
        try:
            with st.spinner("Transcribing and ranking locally; first run may download model weights…"):
                analysis = analyze_uploaded(source, count, length, True)
            show_moments(analysis)
            if analysis["warning"]:
                st.warning(analysis["warning"])
            if not analysis["transcript"]["text"]:
                st.warning("No speech transcript was produced. The fallback uses visual scene changes or evenly spaced windows, so it may not identify the best spoken moments.")
            with st.spinner("Rendering podcast clips…"):
                archive = render_auto_zip(source, analysis["moments"], words=analysis["transcript"]["words"], vertical=podcast_aspect.startswith("Vertical"), captions=podcast_captions, normalize_audio=True, notes=f"Detection method: {analysis['method']}")
            st.success(f"Rendered {len(analysis['moments'])} podcast clip(s).")
            st.download_button("Download podcast Shorts (.zip)", archive, "podcast_shorts.zip", "application/zip", key="download_podcast")
            with st.expander("Transcript preview"):
                st.write(analysis["transcript"]["text"][:12000] or "No transcript available.")
        except Exception as exc:
            st.error(f"Podcast processing failed: {exc}")

elif module == "Packaging Lab":
    st.subheader("Free Viral Packaging Lab")
    topic = st.text_area("Video idea / actual content", placeholder="Describe what really happens in the video…")
    audience = st.text_input("Target audience", "US / Tier-1")
    fmt = st.radio("Video format", ["Short", "Long-form"], horizontal=True)
    if st.button("Generate title, hook & thumbnail brief", type="primary", disabled=not topic.strip()):
        result = make_packaging(topic, audience, fmt)
        st.text_area("Packaging set", result, height=400)
        st.download_button("Download packaging", result, "youtube_packaging.txt", "text/plain")

st.divider()
st.caption("Current capabilities: free local Whisper transcription when the model runs successfully, heuristic moment ranking, FFmpeg clip rendering, optional word-timed captions, audio normalization, template-based planning/packaging, and optional official YouTube research. Not bundled: AI-generated footage, semantic human-level clip judgment, speaker diarization, or unlimited background rendering. Free hosting limits apply.")
