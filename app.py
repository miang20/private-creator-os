from __future__ import annotations
import csv
import io
import streamlit as st
from core.config import openai_api_key, youtube_api_key
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
    st.markdown("**Connection status**")
    st.write("OpenAI API:", "Connected" if openai_api_key() else "Template mode (no API key)")
    st.write("YouTube Data API:", "Connected" if youtube_api_key() else "Not configured")
    st.write("FFmpeg:", "Available" if ffmpeg_available() else "Not found")
    st.caption("Keep API keys in Streamlit Secrets, never in source code.")
st.info("Personal-use creator tool. Upload only media you own or are licensed to process. API use may incur separate charges; ChatGPT subscription does not include API credits.")

if module == "Repurposing Studio":
    st.subheader("AI Long-Video Repurposing Studio")
    st.write("Upload a source video, choose timestamps for the strongest moments, and render MP4 clips. This first build uses explicit timestamps rather than pretending automatic moment detection is connected.")
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
    st.caption("This searches public videos ranked by views; it does not prove channel growth or new-channel status.")

elif module == "Transformation Planner":
    st.subheader("AI Transformation Video Planner")
    concept = st.text_area("Transformation idea", placeholder="e.g. restore a rusted vintage motorcycle")
    fmt = st.selectbox("Target format", ["YouTube Short (9:16)","YouTube long-form (16:9)","Both"])
    if st.button("Build transformation plan", type="primary", disabled=not concept.strip()):
        try:
            result = plan_transformation(concept, fmt)
            st.text_area("Production plan", result, height=440)
            st.download_button("Download plan", result, "transformation_plan.txt", "text/plain")
        except Exception as exc:
            st.error(str(exc))

elif module == "Story-to-Video Studio":
    st.subheader("AI Story-to-Video Studio")
    premise = st.text_area("Story premise", placeholder="Describe the protagonist, conflict, and payoff…")
    style = st.selectbox("Visual style", ["Cinematic realistic","Stylized 3D","Anime-inspired","Documentary"])
    if st.button("Create scene plan", type="primary", disabled=not premise.strip()):
        try:
            result = plan_story(premise, style)
            st.text_area("Scene and continuity plan", result, height=460)
            st.download_button("Download scene plan", result, "story_scene_plan.txt", "text/plain")
        except Exception as exc:
            st.error(str(exc))

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
    st.subheader("Viral Packaging Lab")
    topic = st.text_area("Video idea / actual content", placeholder="Describe what really happens in the video…")
    audience = st.text_input("Target audience", "US / Tier-1")
    fmt = st.radio("Video format", ["Short","Long-form"], horizontal=True)
    if st.button("Generate title, hook & thumbnail brief", type="primary", disabled=not topic.strip()):
        try:
            result = make_packaging(topic, audience, fmt)
            st.text_area("Packaging set", result, height=400)
            st.download_button("Download packaging", result, "youtube_packaging.txt", "text/plain")
        except Exception as exc:
            st.error(str(exc))

st.divider()
st.caption("Build status: modular starter with working timestamp-based FFmpeg exports, planning and packaging templates, optional OpenAI generation, and optional YouTube API search. Automatic moment detection, full transcription, generated scene footage, long-form assembly, and background cloud rendering remain future integrations.")
