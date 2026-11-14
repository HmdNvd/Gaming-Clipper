---
name: gaming-clipper
description: >-
  Turn long-form gaming videos, VODs, or stream URLs into high-retention 9:16
  vertical Shorts/Reels/TikToks with hype-moment detection, hook titles, and
  burned-in word-synced captions.
---

# Gaming Clipper Workflow

Use this skill whenever the user provides a video URL (YouTube, Twitch, Kick) or
a local video file and wants to extract viral 9:16 vertical clips.

## Prerequisites

- Run all Python commands via `uv run` inside the project root so the managed
  `.venv` (`yt-dlp`, `faster-whisper`, `numpy`) is used. Works on Windows, macOS,
  and Linux.
- `ffmpeg` must be available on `PATH`.

## Step-by-Step Pipeline

### 0. Verify Environment (First Run)
```bash
uv run python scripts/check_env.py
```

### 1. Fetch the Source Video
Run `scripts/fetch_video.py` with the URL or local file path:

```bash
uv run python scripts/fetch_video.py --source "<URL_OR_PATH>" --out-dir workspace/source
```

Note the `video_path` printed in the JSON output.

### 2. Analyze Audio Energy & Transcribe
Run `scripts/analyze_video.py` on the `video_path`:

```bash
uv run python scripts/analyze_video.py --input "<video_path>" --out workspace/analysis.json --model base
```

Use `--model small` for higher accuracy on fast commentary if needed.

### 3. Select the Best Clip Moments (Agent Judgment)
Read `workspace/analysis.json` and inspect both:
- `top_energy_peaks` (loud reactions, explosions, laughter, hype spikes)
- `transcript_segments` (funny quotes, insane plays, dramatic reveals)

Pick **3 to 5 clips** following these retention rules:
- **Length:** 18 to 55 seconds (sweet spot: 25–40s).
- **Hook:** Start right on the action or an intriguing opening line—trim dead air before the moment starts.
- **Payoff:** End cleanly right after the punchline, reaction, or clutch finish.
- **Hook Title:** Write a 3–5 word curiosity/action hook in ALL CAPS (e.g., `THIS GTA GLITCH BROKE EVERYTHING`, `NO WAY HE SURVIVED THAT`).

### 4. Render Each 9:16 Vertical Clip
Run `scripts/render_clip.py` for each selected moment:

```bash
uv run python scripts/render_clip.py \
  --input "<video_path>" \
  --analysis workspace/analysis.json \
  --start 124.5 \
  --end 156.0 \
  --title "NO WAY HE SURVIVED THAT" \
  --layout gaming-split \
  --style classic \
  --out workspace/clips/clip_01.mp4
```

Options:
- `--layout gaming-split` (default): Blurred 9:16 background + crisp 16:9 gameplay centered so HUD and edges aren't lost.
- `--layout center-crop`: Full-screen 9:16 center crop (best for talking-head / IRL).
- `--cam-pos top-left|top-right|bottom-left|bottom-right`: Optional corner facecam stacked large above gameplay in `gaming-split` (or `--cam-box x,y,w,h` for exact normalized coordinates).
- `--style classic|neon|emerald|fire|clean`: Caption & hook color preset (`classic` = yellow, `neon` = cyan, `emerald` = green, `fire` = orange, `clean` = crisp white).
- Start times automatically snap to the first spoken word (`--no-snap` to disable) so clips never open on dead air.

### 5. Clean Up Heavy Source Files & Deliver Results
If the user doesn't need to keep the large downloaded source video/WAV, run:

```bash
uv run python scripts/cleanup.py
```

Report the rendered clip file paths, metadata files, timestamps, and hook titles to the user.
