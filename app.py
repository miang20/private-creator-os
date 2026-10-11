from __future__ import annotations
import csv
import io
import tempfile
import zipfile
from pathlib import Path
import streamlit as st

from core.config import youtube_api_key
from core.automation import analyze_media
from core.hook_engine import classify_content, build_hook_plan
from core.packaging import make_packaging, build_caption_plan
from core.planners import plan_story, plan_transformation
from core.research import search_youtube
from core.video import ffmpeg_available, parse_segments, render_zip, render_auto_zip


CONTENT_TYPES = ["Auto", "Funny / Unexpected", "Story / Drama", "Podcast / Opinion", "Satisfying / Transformation", "Tutorial / Educational", "Sports / Action", "Reaction / Commentary", "General / Visual-first"]


def to_csv(items):
    buf = io.StringIO()
    fields = ["title", "channel", "published_at", "views", "url"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(items)
    return buf.getvalue()


def extract_mp4s(archive: bytes) -> list[tuple[str, bytes]]:
    """Read rendered MP4s from the internal render archive for direct downloads."""
    with zipfile.ZipFile(io.BytesIO(archive), "r") as rendered_pack:
        return [
            (Path(name).name, rendered_pack.read(name))
            for name in rendered_pack.namelist()
            if name.lower().endswith(".mp4")
        ]


def analyze_uploaded(source, count: int, clip_length: int, transcribe: bool, model_size: str = "tiny", strategy: str = "Auto"):
    suffix = Path(source.name).suffix or ".mp4"
    with tempfile.TemporaryDirectory(prefix="creator_os_analysis_") as tmp:
        path = Path(tmp) / ("source" + suffix)
        path.write_bytes(source.getvalue())
        try:
            analysis = analyze_media(
                str(path), count=count, clip_length=clip_length,
                transcribe=transcribe, model_size=model_size,
                requested_strategy=strategy,
            )
        except TypeError as exc:
            # Compatibility with a hosted worker still importing an older
            # core.automation module whose analyze_media lacks this keyword.
            if "requested_strategy" not in str(exc) or "unexpected keyword argument" not in str(exc):
                raise
            analysis = analyze_media(
                str(path), count=count, clip_length=clip_length,
                transcribe=transcribe, model_size=model_size,
            )
        # Keep the UI functional during a stale-module/deployment mismatch.
        # The current engine already supplies this plan and strategy-aware ranks.
        if "hook_plan" not in analysis:
            analysis["hook_plan"] = build_hook_plan(analysis, strategy)
            route_key = analysis["hook_plan"]["key"]
            for moment in analysis.get("moments", []):
                moment.setdefault("strategy", route_key)
                moment.setdefault("reason", f"Compatibility fallback: review moment under {analysis['hook_plan']['label']} route.")
        return analysis


def show_moments(analysis):
    rows = [{"Clip": m["title"], "Start (s)": m["start"], "End (s)": m["end"], "Score": m["score"], "Words": m["words"], "Scene changes": m["scene_changes"], "Strategy": m.get("strategy", "general_visual"), "Why selected": m.get("reason", "")} for m in analysis["moments"]]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"Duration: {analysis['duration']:.1f}s · Detection: {analysis['method']} · Scene changes found: {len(analysis['scene_changes'])}")


def show_hook_plan(plan):
    st.subheader(f"Creative route: {plan['label']}")
    a, b, c = st.columns(3)
    a.metric("Route confidence", f"{plan['confidence']:.0%}")
    b.metric("Primary hook", plan["primary"])
    c.metric("Alternates", len(plan["alternates"]))
    st.write("**Opening direction**")
    st.info(plan["opening"])
    st.write("**Editing blueprint**")
    st.write(plan["edit"])
    st.write("**Rhythm**")
    st.write(plan["rhythm"])
    st.write("**Caption direction**")
    st.write(plan["caption"])
    st.write("**Alternative hook strategies**")
    st.write(" · ".join(plan["alternates"]))
    if plan.get("warning"):
        st.warning(plan["warning"])
    st.caption(plan["review_note"])


st.set_page_config(page_title="Creator OS", page_icon="🎬", layout="wide")
st.title("🎬 Creator OS")
st.caption("Free-first creator workspace · Detect → Strategize → Edit → Package")
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
st.info("Free-first creator workspace. Upload only media you own or are licensed to process. Automatic analysis uses local signals and transparent heuristics; it does not promise virality.")

if module == "Repurposing Studio":
    st.subheader("Adaptive Repurposing Studio")
    st.write("Upload a video. The local engine routes it to a content-specific hook/edit strategy, ranks moments with different weights per content type, then renders the clips. Review the suggested route before publishing.")
    source = st.file_uploader("Upload source video", type=["mp4", "mov", "m4v", "webm", "mkv"], key="repurpose_source")
    c1, c2, c3 = st.columns(3)
    with c1:
        clip_count = st.slider("Clips to export", 1, 10, 5, key="repurpose_count")
    with c2:
        clip_length = st.slider("Target clip length (seconds)", 15, 60, 30, step=5, key="repurpose_length")
    with c3:
        aspect = st.selectbox("Output format", ["Vertical 9:16 (Shorts)", "Landscape 16:9"], key="repurpose_aspect")
    c4, c5 = st.columns(2)
    with c4:
        strategy = st.selectbox("Content type / hook routing", CONTENT_TYPES, key="repurpose_strategy", help="Auto uses transcript signals. Select a route manually if the video has little speech or the auto-detection is wrong.")
    with c5:
        transcribe = st.checkbox("Run free local transcription", value=True, key="repurpose_transcribe")
    c6, c7 = st.columns(2)
    with c6:
        captions = st.checkbox("Burn word-timed captions when available", value=True, key="repurpose_captions", disabled=not transcribe)
    with c7:
        normalize = st.checkbox("Normalize audio", value=True, key="repurpose_normalize")
    dynamic_zoom = st.checkbox("Apply subtle dynamic zoom (centered)", value=True, key="repurpose_dynamic_zoom", help="Adds gentle movement; it does not track a person or object.")
    e1, e2 = st.columns(2)
    with e1:
        caption_style = st.selectbox("Caption style", ["Creator Pop", "Classic Yellow", "Clean White"], key="repurpose_caption_style")
    with e2:
        output_quality = st.selectbox("Render quality", ["Balanced 1080p", "High Quality 1080p", "Fast Preview"], key="repurpose_quality")

    if st.button("Analyze → choose hook strategy → render clips", type="primary", disabled=source is None, key="auto_repurpose"):
        try:
            with st.spinner("Analyzing local signals. First transcription may download model weights and take several minutes…"):
                analysis = analyze_uploaded(source, clip_count, clip_length, transcribe, strategy=strategy)
            show_hook_plan(analysis["hook_plan"])
            show_moments(analysis)
            if analysis["warning"]:
                st.warning(analysis["warning"] + " Available visual signals were used where possible.")
            if transcribe and not analysis["transcript"]["segments"]:
                st.warning("No transcript was produced. The visual fallback cannot reliably infer story meaning; review each candidate.")
            notes = (f"Content route: {analysis['hook_plan']['label']}\nPrimary hook: {analysis['hook_plan']['primary']}\n"
                     f"Editing rhythm: {analysis['hook_plan']['rhythm']}\nDetection method: {analysis['method']}\n"
                     "Scores are heuristic, not guaranteed viral predictions. Review context and payoff before publishing.")
            with st.spinner("Rendering MP4 clips and preparing ZIP…"):
                archive = render_auto_zip(source, analysis["moments"], words=analysis["transcript"]["words"], vertical=aspect.startswith("Vertical"), captions=captions, normalize_audio=normalize, notes=notes, edit_profile=analysis["hook_plan"]["key"], dynamic_zoom=dynamic_zoom, caption_style=caption_style, output_quality=output_quality)
            mp4_files = extract_mp4s(archive)
            st.success(f"Rendered {len(mp4_files)} MP4 clip(s) using the {analysis['hook_plan']['label']} route.")
            st.subheader("Download finished MP4 video(s)")
            for mp4_name, mp4_data in mp4_files:
                st.download_button(
                    f"Download {mp4_name}", data=mp4_data, file_name=mp4_name,
                    mime="video/mp4", key=f"download_mp4_{mp4_name}", on_click="ignore",
                )
            with st.expander("Optional: download the complete ZIP pack"):
                st.download_button("Download adaptive clip pack (.zip)", archive, file_name="creator_os_adaptive_clips.zip", mime="application/zip", key="download_auto_repurpose", on_click="ignore")
            with st.expander("Transcript and evidence"):
                st.write(analysis["transcript"]["text"][:12000] or "No transcript available.")
                st.json({"strategy": analysis["hook_plan"], "moments": analysis["moments"]})
        except Exception as exc:
            st.error(f"Automatic repurposing failed: {exc}")
    st.divider()
    st.markdown("**Manual timestamp mode**")
    st.caption("Fallback for precise edits or when automatic analysis is unavailable.")
    manual_source = st.file_uploader("Upload source for manual clipping", type=["mp4", "mov", "m4v", "webm", "mkv"], key="manual_repurpose_source")
    aspect_manual = st.radio("Manual output format", ["Vertical 9:16 (Shorts)", "Landscape 16:9"], horizontal=True, key="manual_aspect")
    segment_text = st.text_area("Clip timestamp plan (start_seconds,end_seconds,title)", value="12,28,Best_Moment\n35,52,Second_Moment", height=100)
    if st.button("Render manual clips", disabled=manual_source is None, key="manual_render"):
        try:
            segments = parse_segments(segment_text)
            archive = render_zip(manual_source, segments, vertical=aspect_manual.startswith("Vertical"), dynamic_zoom=dynamic_zoom, caption_style=caption_style, output_quality=output_quality)
            for mp4_name, mp4_data in extract_mp4s(archive):
                st.download_button(
                    f"Download {mp4_name}", data=mp4_data, file_name=mp4_name,
                    mime="video/mp4", key=f"download_manual_mp4_{mp4_name}", on_click="ignore",
                )
            with st.expander("Optional: download manual ZIP pack"):
                st.download_button("Download manual clip pack", archive, "creator_os_manual_clips.zip", "application/zip", key="download_manual", on_click="ignore")
        except Exception as exc:
            st.error(str(exc))
    transcript = st.text_area("Paste transcript for 1–3 word caption beats", key="repurpose_transcript")
    if st.button("Create caption beat plan", key="caption_plan") and transcript.strip():
        result = build_caption_plan(transcript)
        st.text_area("Caption beats", result, height=180)
        st.download_button("Download caption plan", result, "caption_beats.txt", "text/plain")

elif module == "Breakout Radar":
    st.subheader("New-Channel Breakout Radar")
    st.write("Search public videos using the official YouTube Data API. Its free daily quota applies; no unofficial scraping is used.")
    query = st.text_input("Search topic / niche", placeholder="e.g. satisfying restoration shorts")
    count = st.slider("Public videos to inspect", 5, 25, 10)
    if st.button("Search YouTube", type="primary", disabled=not query.strip()):
        with st.spinner("Querying public YouTube data…"):
            result = search_youtube(query, count)
        if not result["configured"]:
            st.warning(result["message"])
            st.markdown("[Open YouTube search](https://www.youtube.com/results?search_query=" + query.strip().replace(" ", "+") + ")")
        elif result["items"]:
            st.caption(result["message"])
            st.dataframe(result["items"], use_container_width=True, hide_index=True)
            st.download_button("Download research CSV", to_csv(result["items"]), "breakout_radar.csv", "text/csv")
        else:
            st.error(result["message"])
    st.caption("Views are snapshots, not proof of retention or future growth.")

elif module == "Transformation Planner":
    st.subheader("Transformation Planner")
    concept = st.text_area("Transformation idea", placeholder="e.g. restore a rusted vintage motorcycle")
    fmt = st.selectbox("Target format", ["YouTube Short (9:16)", "YouTube long-form (16:9)", "Both"])
    if st.button("Build transformation plan", type="primary", disabled=not concept.strip()):
        result = plan_transformation(concept, fmt)
        st.text_area("Production plan", result, height=440)
        st.download_button("Download plan", result, "transformation_plan.txt", "text/plain")

elif module == "Story-to-Video Studio":
    st.subheader("Story-to-Video Studio")
    premise = st.text_area("Story premise", placeholder="Describe the protagonist, conflict, and payoff…")
    style = st.selectbox("Visual style", ["Cinematic realistic", "Stylized 3D", "Anime-inspired", "Documentary"])
    if st.button("Create scene plan", type="primary", disabled=not premise.strip()):
        result = plan_story(premise, style)
        st.text_area("Scene and continuity plan", result, height=460)
        st.download_button("Download scene plan", result, "story_scene_plan.txt", "text/plain")
    st.caption("This creates a production blueprint, not finished generated footage.")

elif module == "Podcast-to-Shorts":
    st.subheader("Podcast-to-Shorts Factory")
    st.write("Transcribe locally, select speech-led moments with a podcast-specific scoring route, add word-timed captions, normalize audio, and export clips.")
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
        podcast_captions = st.checkbox("Burn captions when timestamps exist", value=True, key="podcast_captions")
    p5, p6 = st.columns(2)
    with p5:
        podcast_caption_style = st.selectbox("Podcast caption style", ["Creator Pop", "Classic Yellow", "Clean White"], key="podcast_caption_style")
    with p6:
        podcast_quality = st.selectbox("Podcast render quality", ["Balanced 1080p", "High Quality 1080p", "Fast Preview"], key="podcast_quality")
    if st.button("Transcribe → rank → render", type="primary", disabled=source is None, key="auto_podcast"):
        try:
            with st.spinner("Transcribing and ranking locally; first run may download model weights…"):
                analysis = analyze_uploaded(source, count, length, True, strategy="Podcast / Opinion")
            show_hook_plan(analysis["hook_plan"])
            show_moments(analysis)
            if analysis["warning"]:
                st.warning(analysis["warning"])
            if not analysis["transcript"]["text"]:
                st.warning("No speech transcript was produced; review the visual fallback carefully.")
            with st.spinner("Rendering podcast clips…"):
                archive = render_auto_zip(source, analysis["moments"], words=analysis["transcript"]["words"], vertical=podcast_aspect.startswith("Vertical"), captions=podcast_captions, normalize_audio=True, notes=f"Content route: {analysis['hook_plan']['label']}\nPrimary hook: {analysis['hook_plan']['primary']}", dynamic_zoom=True, caption_style=podcast_caption_style, output_quality=podcast_quality)
            podcast_mp4s = extract_mp4s(archive)
            st.success(f"Rendered {len(podcast_mp4s)} podcast MP4 clip(s).")
            st.subheader("Download finished podcast MP4(s)")
            for mp4_name, mp4_data in podcast_mp4s:
                st.download_button(
                    f"Download {mp4_name}", data=mp4_data, file_name=mp4_name,
                    mime="video/mp4", key=f"download_podcast_mp4_{mp4_name}", on_click="ignore",
                )
            with st.expander("Optional: download podcast ZIP pack"):
                st.download_button("Download podcast Shorts (.zip)", archive, "podcast_shorts.zip", "application/zip", key="download_podcast", on_click="ignore")
            with st.expander("Transcript preview"):
                st.write(analysis["transcript"]["text"][:12000] or "No transcript available.")
        except Exception as exc:
            st.error(f"Podcast processing failed: {exc}")

elif module == "Packaging Lab":
    st.subheader("Adaptive Packaging Lab")
    topic = st.text_area("Video idea / actual content", placeholder="Describe what really happens in the video…")
    audience = st.text_input("Target audience", "US / Tier-1")
    p1, p2 = st.columns(2)
    with p1:
        fmt = st.radio("Video format", ["Short", "Long-form"], horizontal=True)
    with p2:
        packaging_type = st.selectbox("Content type", CONTENT_TYPES, key="packaging_type")
    if st.button("Generate adaptive titles, hooks & edit brief", type="primary", disabled=not topic.strip()):
        result = make_packaging(topic, audience, fmt, packaging_type)
        st.text_area("Packaging set", result, height=500)
        st.download_button("Download packaging brief", result, "youtube_packaging.txt", "text/plain")

st.divider()
st.caption("Current capabilities: offline strategy routing from transcript signals, strategy-weighted clip ranking, FFmpeg rendering, optional local Whisper word captions, loudness normalization, production planners, and template-based packaging. No paid AI API is required. Scores are heuristics; real footage still needs review. Hosted CPU/RAM/runtime limits apply.")
