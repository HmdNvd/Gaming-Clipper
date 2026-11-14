"""Fetch a video from a URL (via yt-dlp) or validate a local video file."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def download_video(url: str, output_dir: Path, max_height: int = 1080) -> Path:
    """Download a video from YouTube, Twitch, Kick, etc. into output_dir as MP4."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(output_dir / "%(id)s.%(ext)s")

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "-f",
        f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_height}][ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "--print",
        "after_move:filepath",
        "-o",
        out_template,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"yt-dlp failed with exit code {result.returncode}")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("yt-dlp did not return an output file path.")
    return Path(lines[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch or validate source video.")
    parser.add_argument("--source", required=True, help="Video URL or local file path.")
    parser.add_argument(
        "--out-dir",
        default="workspace/source",
        help="Directory to store downloaded videos.",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=1080,
        help="Max video height when downloading (default: 1080).",
    )
    args = parser.parse_args()

    local_path = Path(args.source)
    if local_path.exists() and local_path.is_file():
        resolved = local_path.resolve()
    else:
        resolved = download_video(args.source, Path(args.out_dir), args.max_height).resolve()

    print(json.dumps({"video_path": str(resolved)}, indent=2))


if __name__ == "__main__":
    main()
