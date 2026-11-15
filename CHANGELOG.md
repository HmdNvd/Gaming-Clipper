# Changelog

All notable updates to **Gaming Clipper** (`KlipDeck` Pipeline) are documented here.

## 2026-11-16 — v1.1 (Launch-Week Pro Upgrades)
- **Internal Silence / Dead-Air Trimmer (`--trim-silence`, `--silence-gap`)** in `scripts/render_clip.py`:
  - Automatically detects silent gaps longer than `--silence-gap` (default `1.2s`) inside a clip, cuts them out with FFmpeg `trim`/`concat`, and remaps `.ass` word timestamps so captions stay 100% synced.
- **Channel Handle Watermark (`--watermark`)** in `scripts/render_clip.py`:
  - Burns a subtle semi-transparent `@Handle` watermark (e.g. `@KlipDeck`) in the safe bottom-right zone above platform UI bars.
- **Sharper Facecam Scaling** in `scripts/render_clip.py`:
  - Upgraded corner facecam scaling to `lanczos` + subtle `unsharp` filter (`520px` height) to reduce softness on 720p stream sources.
- **Batch Renderer (`scripts/batch_render.py`)**:
  - Renders an entire JSON list of clip specs in one command.
- **Top-N Countdown Compiler (`scripts/compile_top5.py`)**:
  - Normalizes and stitches 2–10 rendered 9:16 clips into a `#N → #1` countdown Short with automatic rank badges and optional top banner.

## 2026-11-15 — v1.0 (Marketplace & Cross-Platform Release)
- **Caption Style Presets (`--style`)** in `scripts/render_clip.py`:
  - Added `classic` (yellow), `neon` (cyan), `emerald` (green), `fire` (orange), and `clean` (white).
- **Environment Doctor (`scripts/check_env.py`)**:
  - Cross-platform pre-flight check for `ffmpeg`, `h264_nvenc`, `yt_dlp`, `faster_whisper`, and `numpy`.
- **Documentation & Showcase Assets**:
  - Added MIT `LICENSE`, cross-platform `SKILL.md` / `README.md`, 512×512 skill icons, and side-by-side preview showcases in `assets/`.
  - Packaged Agensi marketplace submission (`dist/gaming-clipper-agensi.zip`).

## 2026-11-14 — v0.1 (Initial Local Pipeline)
- Built `scripts/fetch_video.py`, `scripts/analyze_video.py`, `scripts/render_clip.py`, and `scripts/cleanup.py`.
- Added `gaming-split`, `center-crop`, `--cam-pos` / `--cam-box` facecam stacking, auto speech-start snapping, `-14 LUFS` loudness normalization, and `.metadata.txt` generation.
