"""Verify local prerequisites for Gaming Clipper (cross-platform)."""

import importlib.util
import json
import platform
import shutil
import subprocess
import sys


def has_nvenc() -> bool:
    """Return True if ffmpeg can encode using h264_nvenc."""
    if not shutil.which("ffmpeg"):
        return False
    probe = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:d=0.1",
            "-c:v",
            "h264_nvenc",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def main() -> None:
    ffmpeg_path = shutil.which("ffmpeg")
    packages = {
        pkg: importlib.util.find_spec(pkg) is not None
        for pkg in ("yt_dlp", "faster_whisper", "numpy")
    }
    nvenc = has_nvenc()

    report = {
        "os": platform.system(),
        "python": platform.python_version(),
        "ffmpeg": ffmpeg_path or "MISSING",
        "h264_nvenc": nvenc,
        "packages": packages,
        "ready": bool(ffmpeg_path) and all(packages.values()),
    }
    print(json.dumps(report, indent=2))
    if not report["ready"]:
        print(
            "\nMissing dependencies. Install ffmpeg on PATH and run `uv sync`.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
