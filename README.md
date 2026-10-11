# Creator OS

A free-first personal creator workspace. No paid AI API key or per-video AI API fee is required. The app uses local open-source transcription where available, deterministic local heuristics, and FFmpeg rendering. It does not bypass the CPU/RAM/runtime limits of the hosting platform.

## Deploy

1. Open https://share.streamlit.io/.
2. Connect the GitHub account that owns `miang20/private-creator-os`.
3. Select branch `main` and main file `app.py`.
4. No OpenAI API key is needed. First local transcription may download the small Whisper model weights and may take several minutes.
5. Optional: add `YOUTUBE_API_KEY` in Streamlit Secrets to use official YouTube Data API research. Its free daily quota still applies.

Never commit API keys into source code.

## Current features

- Adaptive content routing for funny/unexpected, story/drama, podcast/opinion, satisfying/transformation, tutorial/education, sports/action, reaction/commentary, and visual-first footage.
- Strategy-weighted moment ranking, evidence-based transcript candidates, alternate hook approaches, and per-content-type edit/caption finishing profiles.
- Automatic clip candidates ranked using local Whisper transcript signals and FFmpeg scene-change signals.
- One-click analysis and export for uploaded video and podcast/audio sources.
- MP4 output at 9:16 or 16:9, 30 fps, H.264/AAC, and optional loudness normalization.
- Word-timed captions burned in when local transcription supplies word timestamps.
- ZIP export with MP4s and edit manifest.
- Manual timestamp mode for precise cuts.
- Local template-based story and transformation plans with dedicated hook blueprints, adaptive packaging, and caption-beat helpers.
- Optional official YouTube Data API research.

## Important limits

This is not unlimited cloud compute. Local Whisper inference can be slow or fail on free-host memory/time limits; the app attempts to fall back to visual scene-change ranking. Automatic routing and ranking are heuristic and need human review. Strategy confidence is not a viral prediction; scene changes do not equal semantic highlights. Visual finishing is intentionally restrained and does not replace subject tracking, reframing review, or a human edit pass. Audio-only podcast exports use a plain background unless you add visual footage. This app does not generate finished AI footage, perform speaker diarization, or promise viral performance. YouTube Data API research is optional but quota-limited. Use media you own or have permission to edit.
