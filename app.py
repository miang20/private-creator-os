from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

APP_NAME = "Creator OS"
MODULES = {
    "Repurposing Studio": "Turn source videos you own or are licensed to use into a coherent long-form edit and short clips.",
    "Breakout Radar": "Research niches, emerging channels, and unusually strong public videos.",
    "Transformation Planner": "Build satisfying construction, restoration, and transformation concepts with shot plans.",
    "Story-to-Video Studio": "Turn a story idea into scenes, visual prompts, and a continuity plan.",
    "Podcast-to-Shorts": "Find strong speaker moments and plan caption-ready short clips.",
    "Packaging Lab": "Develop hooks, titles, descriptions, and thumbnail directions.",
}

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="wide")

st.title("🎬 Creator OS")
st.caption("Your private-use creator workspace · Research → Plan → Produce → Review")

with st.sidebar:
    st.header("Workspace")
    selected_module = st.radio("Choose a studio", list(MODULES.keys()))
    st.divider()
    st.caption("Creator OS is an early build. A visible module is not yet proof that its complete processing pipeline is connected.")

st.subheader(selected_module)
st.write(MODULES[selected_module])

if selected_module == "Repurposing Studio":
    st.info("Upload source media you own or have permission to edit. Full rendering will be enabled after the processing worker and storage are connected.")
    uploads = st.file_uploader(
        "Add source videos",
        type=["mp4", "mov", "m4v", "webm"],
        accept_multiple_files=True,
        help="For the first cloud test, use short sample files. Streamlit hosting has upload and resource limits.",
    )
    col1, col2 = st.columns(2)
    with col1:
        target_long = st.checkbox("Plan one coherent long-form edit", value=True)
        target_shorts = st.checkbox("Plan 3–4 Shorts", value=True)
    with col2:
        caption_toggle = st.checkbox("Include word-highlight caption plan", value=True)
        vertical = st.checkbox("Shorts output: vertical 9:16", value=True)
    if uploads:
        st.write(f"Selected files: {len(uploads)}")
        for item in uploads:
            st.write(f"• {item.name} — {item.size / (1024 * 1024):.1f} MB")
        st.warning("Files are only selected in this starter interface; no video has been analyzed or rendered yet.")
    st.button("Prepare production job", disabled=True, help="Enabled after the analysis/render worker is integrated.")

elif selected_module == "Breakout Radar":
    niche = st.text_input("Niche or audience", placeholder="e.g. satisfying restoration, US audience")
    st.selectbox("Research window", ["Last 7 days", "Last 30 days", "Last 90 days"])
    st.button("Research breakout opportunities", disabled=True, help="Public-source research connector is not integrated yet.")
    if niche:
        st.caption(f"Research target: {niche}")

elif selected_module == "Transformation Planner":
    concept = st.text_area("Transformation concept", placeholder="e.g. abandoned room restored into a modern studio")
    st.selectbox("Target format", ["YouTube Short (9:16)", "YouTube long-form (16:9)", "Both"])
    st.button("Build shot plan", disabled=True, help="Planning engine is not integrated yet.")
    if concept:
        st.caption("Concept captured locally in this session.")

elif selected_module == "Story-to-Video Studio":
    story = st.text_area("Story premise", placeholder="Describe the story, characters, and ending...")
    st.selectbox("Visual style", ["Cinematic realistic", "Stylized 3D", "Anime-inspired", "Documentary"])
    st.button("Create scene plan", disabled=True, help="Scene generation and consistency engine are not integrated yet.")
    if story:
        st.caption(f"Premise length: {len(story)} characters")

elif selected_module == "Podcast-to-Shorts":
    podcast = st.file_uploader("Upload a podcast/video file", type=["mp4", "mov", "mp3", "wav", "m4a"])
    st.selectbox("Target clip length", ["20–35 seconds", "35–60 seconds", "60–90 seconds"])
    st.button("Find standout moments", disabled=True, help="Transcription, speaker analysis, and rendering are not integrated yet.")
    if podcast:
        st.write(f"Selected: {podcast.name} ({podcast.size / (1024 * 1024):.1f} MB)")

elif selected_module == "Packaging Lab":
    topic = st.text_input("Video idea or working title")
    audience = st.text_input("Target audience", value="US / Tier-1")
    format_type = st.radio("Format", ["Short", "Long-form"], horizontal=True)
    st.button("Generate packaging", disabled=True, help="AI packaging provider is not configured yet.")
    if topic:
        st.caption(f"Packaging brief: {format_type} · {audience}")

st.divider()
st.caption("Build status: UI foundation committed. Analysis, AI providers, durable job queue, cloud rendering, and export delivery still need implementation and verification.")
