# Creator OS

Personal creator workspace with six modules: timestamp-based video repurposing, optional official YouTube research, transformation planning, story-to-video scene planning, podcast clip export, and YouTube packaging.

## Deploy on Streamlit Community Cloud

1. Open https://share.streamlit.io/
2. Connect the GitHub account that owns this repository.
3. Select repository `miang20/private-creator-os`, branch `main`, main file `app.py`.
4. No OpenAI key or paid AI API is required. The planner, packaging, and caption-beat helpers use deterministic local templates/rules.
5. Optional: add `YOUTUBE_API_KEY` in Streamlit Secrets to use the official YouTube Data API. Its free daily quota and access rules still apply.

Never commit API keys into the repository. This project is designed to avoid paid AI API charges, not to bypass host resource limits or official service quotas.

## What works in this build

- Dashboard for all six studios.
- Timestamp-based video clipping to vertical 9:16 or landscape 16:9 MP4 using FFmpeg.
- ZIP export with rendered clips and an edit manifest.
- Local template-based story and transformation plans.
- Local template-based packaging and caption beat splitting.
- Optional official YouTube Data API search with public view-count snapshots.

## Current limitations

This is a free-first foundation, not a fully automatic video factory. Automatic transcript extraction, automatic best-moment detection, speaker diarization, contextual B-roll, word-synced captions burned into the video, generated scene footage, and a persistent background render queue are not yet connected. Streamlit hosting has CPU, memory, upload, and runtime limits, so large videos may not process reliably. YouTube Data API research is optional but quota-limited. Use media you own or have permission to edit.
