# Creator OS

Personal creator workspace with six modules: timestamp-based video repurposing, public YouTube research, transformation planning, story-to-video scene planning, podcast clip export, and YouTube packaging.

## Deploy on Streamlit Community Cloud

1. Open https://share.streamlit.io/
2. Connect the GitHub account that owns this repository.
3. Select repository miang20/private-creator-os, branch main, main file app.py.
4. In app settings, add secrets if you want API-backed features:

OPENAI_API_KEY = "your-openai-api-key"
YOUTUBE_API_KEY = "your-youtube-data-api-key"

Never commit API keys into the repository. OpenAI API billing is separate from a ChatGPT subscription. YouTube Data API quota and access rules apply.

## What works in this build

- Dashboard for all six studios.
- Timestamp-based video clipping to vertical 9:16 or landscape 16:9 MP4 using FFmpeg.
- ZIP export with rendered clips and an edit manifest.
- Template-mode story and transformation plans.
- Template-mode packaging and caption beat splitting.
- Optional OpenAI API generation for plans, packaging, and caption beats.
- Optional YouTube Data API search with public view-count snapshots.

## Current limitations

This is the first deployable foundation, not a fully automatic AI video factory. Automatic transcript extraction, automatic best-moment detection, speaker diarization, contextual B-roll, word-synced captions burned into the video, generated scene footage, and a persistent background render queue are not yet connected. Streamlit Cloud has resource and upload limits, so large videos may require external storage and a dedicated render worker. Use media you own or have permission to edit.
