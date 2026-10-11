from __future__ import annotations
import csv
import io
import streamlit as st
from core.config import youtube_api_key
from core.packaging import make_packaging, build_caption_plan
from core.planners import plan_story, plan_transformation
from core.research import search_youtube
from core.video import ffmpeg_available, parse_segments, render_zip

def to_csv(items):
    buf = io.StringIO()
    fields = ["title", "channel", "published_at", "views", "url"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(items)
    return buf.getvalue()

st.set_page_config(page_title="Creator OS", page_icon="🎬", layout="wide")
st.title("🎬 Creator OS")
st.caption("Personal creator workspace · Research → Plan → Edit → Package")
with st.sidebar:
    st.header("Your studio")
    module = st.radio("Select module", ["Repurposing Studio","Breakout Radar","Transformation Planner","Story-to-Video Studio","Podcast-to-Shorts","Packaging Lab"])
    st.divider()
    st.markdown("**System status**")
    st.write("AI generation:", "Free local templates (no paid API)")
    st.write("YouTube Data API:", "Configured (free quota applies)" if youtube_api_key() else "Optional key not configured")
    st.write("FFmpeg:", "Available" if ffmpeg_available() else "Not found")
    st.caption("No paid AI API key is used by this build. Never commit secrets to source code.")
st.info("Free-first creator workspace. Video processing runs on the app host and is subject to its CPU, memory, upload, and runtime limits. Upload only media you own or are licensed to process.")

if module == "Repurposing Studio":
    st.subheader("AI Long-Video Repurposing Studio")
    st.write("Upload a source video, choose timestamps for the strongest moments, and render MP4 clips. Automatic best-moment detection is not connected yet, so this build does not pretend the selected timestamps are AI-detected.")
    source = st.file_uploader("Upload one source video", type=["mp4","mov","m4v","webm"], key="repurpose_source")
    aspect = st.radio("Output format", ["Vertical 9:16 (Shorts)","Landscape 16:9"], horizontal=True)
    st.markdown("Enter one clip per line as start_seconds,end_seconds,title. Example: 12,28,Best_Moment")
    segment_text = st.text_area("Clip timestamp plan", value="12,28,Best_Moment\n35,52,Second_Moment", height=120)
    st.caption("Timestamps are seconds from the start of the uploaded source. Keep end times within the source duration.")
    if st.button("Render selected clips", type="primary", disabled=source is None):
        try:
            segments = parse_segments(segment_text)
            with st.spinner("Rendering clips with FFmpeg…"):
                archive = render_zip(source, segments, vertical=aspect.startswith("Vertical"))
            st.success(f"Rendered {len(segments)} clip(s). Export is ready.")
            st.download_button("Download rendered clips (.zip)", archive, file_name="creator_os_clips.zip", mime="application/zip")
        except Exception as exc:
            st.error(str(exc))
    st.divider()
    st.markdown("**Transcript / caption helper**")
    transcript = st.text_area("Paste a transcript to create a 1–3 word caption beat plan", key="repurpose_transcript")
    if st.button("Create caption beat plan", key="caption_plan") and transcript.strip():
        try:
            result = build_caption_plan(transcript)
            st.text_area("Caption beats", result, height=220)
            st.download_button("Download caption plan", result, "caption_beats.txt", "text/plain")
        except Exception as exc:
            st.error(str(exc))

elif module == "Breakout Radar":
    st.subheader("New-Channel Breakout Radar")
    query = st.text_input("Search topic / niche", placeholder="e.g. satisfying restoration shorts")
    count = st.slider("Public videos to inspect", 5, 25, 10)
    if st.button("Search YouTube", type="primary", disabled=not query.strip()):
        with st.spinner("Querying public YouTube data…"):
            result = search_youtube(query, count)
        if not result["configured"]:
            st.warning(result["message"])
        elif result["items"]:
            st.caption(result["message"])
            st.dataframe(result["items"], use_container_width=True, hide_index=True)
            st.download_button("Download research CSV", to_csv(result["items"]), "breakout_radar.csv", "text/csv")
        else:
            st.error(result["message"])
    st.caption("Official YouTube Data API search uses its free daily quota. Results are public-video snapshots, not proof of channel growth or new-channel status.")

elif module == "Transformation Planner":
    st.subheader("Free Transformation Video Planner")
    concept = st.text_area("Transformation idea", placeholder="e.g. restore a rusted vintage motorcycle")
    fmt = st.selectbox("Target format", ["YouTube Short (9:16)","YouTube long-form (16:9)","Both"])
    if st.button("Build transformation plan", type="primary", disabled=not concept.strip()):
        result = plan_transformation(concept, fmt)
        st.text_area("Production plan", result, height=440)
        st.download_button("Download plan", result, "transformation_plan.txt", "text/plain")

elif module == "Story-to-Video Studio":
    st.subheader("Free Story-to-Video Studio")
    premise = st.text_area("Story premise", placeholder="Describe the protagonist, conflict, and payoff…")
    style = st.selectbox("Visual style", ["Cinematic realistic","Stylized 3D","Anime-inspired","Documentary"])
    if st.button("Create scene plan", type="primary", disabled=not premise.strip()):
        result = plan_story(premise, style)
        st.text_area("Scene and continuity plan", result, height=460)
        st.download_button("Download scene plan", result, "story_scene_plan.txt", "text/plain")

elif module == "Podcast-to-Shorts":
    st.subheader("Podcast-to-Shorts Factory")
    st.write("Upload a podcast/video and specify timestamps for speaker moments. The FFmpeg engine exports MP4 clips.")
    source = st.file_uploader("Upload podcast or interview", type=["mp4","mov","m4v","webm","mp3","wav","m4a"], key="podcast_source")
    segment_text = st.text_area("Podcast moment timestamps (start_seconds,end_seconds,title)", value="45,75,Strong_Quote\n120,155,Story_Payoff")
    if st.button("Render podcast clips", type="primary", disabled=source is None):
        try:
            segments = parse_segments(segment_text)
            with st.spinner("Rendering podcast clips…"):
                archive = render_zip(source, segments, vertical=True)
            st.success(f"Rendered {len(segments)} podcast clip(s).")
            st.download_button("Download podcast clips (.zip)", archive, "podcast_shorts.zip", "application/zip")
        except Exception as exc:
            st.error(str(exc))
    st.caption("Automatic transcription, speaker diarization, and automatic best-moment detection are not implemented yet; this workflow uses chosen timestamps.")

elif module == "Packaging Lab":
    st.subheader("Free Viral Packaging Lab")
    topic = st.text_area("Video idea / actual content", placeholder="Describe what really happens in the video…")
    audience = st.text_input("Target audience", "US / Tier-1")
    fmt = st.radio("Video format", ["Short","Long-form"], horizontal=True)
    if st.button("Generate title, hook & thumbnail brief", type="primary", disabled=not topic.strip()):
        result = make_packaging(topic, audience, fmt)
        st.text_area("Packaging set", result, height=400)
        st.download_button("Download packaging", result, "youtube_packaging.txt", "text/plain")

st.divider()
st.caption("Build status: free local templates, working timestamp-based FFmpeg exports, and optional official YouTube Data API research (free quota applies). Automatic transcription, automatic best-moment detection, word-synced burned-in captions, generated footage, full long-form assembly, and background rendering are not connected yet. Streamlit hosting limits apply.")
