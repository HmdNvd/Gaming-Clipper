"""Compile 2-10 rendered 9:16 clips into a #N -> #1 countdown Short."""

import argparse
import subprocess
import sys
from pathlib import Path

from render_clip import escape_ass, fmt_ass_time, has_nvenc


COUNTDOWN_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: RankBadge,Arial,96,&H0000FFFF,&H00FFFFFF,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,3,14,0,7,60,60,95,1
Style: TopBanner,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,3,10,0,9,60,60,105,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def probe_duration(path: Path) -> float:
    """Return video duration in seconds via ffprobe."""
    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path.resolve()),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(res.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Stitch clips into a #N -> #1 countdown Short.")
    parser.add_argument(
        "--clips",
        nargs="+",
        required=True,
        help="Clip paths in playback order (e.g. #5 #4 #3 #2 #1).",
    )
    parser.add_argument("--title", default="", help="Optional top-right countdown banner title.")
    parser.add_argument("--out", required=True, help="Output countdown MP4 path.")
    args = parser.parse_args()

    clips = [Path(c).resolve() for c in args.clips]
    if len(clips) < 2:
        raise ValueError("Provide at least 2 clips for a countdown compilation.")
    for c in clips:
        if not c.exists():
            raise FileNotFoundError(f"Clip not found: {c}")

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path = out_path.with_suffix(".ass")

    durations = [probe_duration(c) for c in clips]
    total_dur = sum(durations)

    ass_lines = [COUNTDOWN_ASS_HEADER]
    if args.title.strip():
        ass_lines.append(
            f"Dialogue: 1,0:00:00.00,{fmt_ass_time(total_dur)},TopBanner,,0,0,0,,{escape_ass(args.title.strip().upper())}"
        )

    t = 0.0
    total_clips = len(clips)
    for idx, dur in enumerate(durations):
        rank = total_clips - idx
        ass_lines.append(
            f"Dialogue: 2,{fmt_ass_time(t)},{fmt_ass_time(t + dur)},RankBadge,,0,0,0,,#{rank}"
        )
        t += dur

    ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")

    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd.extend(["-i", str(c)])

    norm_parts = []
    concat_refs = []
    for idx in range(len(clips)):
        norm_parts.append(
            f"[{idx}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=60,setsar=1[v{idx}];"
        )
        norm_parts.append(
            f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{idx}];"
        )
        concat_refs.append(f"[v{idx}][a{idx}]")

    fc = (
        "".join(norm_parts)
        + "".join(concat_refs)
        + f"concat=n={len(clips)}:v=1:a=1[cv][ca];"
        + f"[cv]ass={ass_path.name},format=yuv420p[vout];"
        + "[ca]loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
    )

    if has_nvenc():
        video_enc = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "18", "-b:v", "8M"]
    else:
        video_enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17"]

    cmd.extend(
        [
            "-filter_complex",
            fc,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            *video_enc,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
    )
    res = subprocess.run(cmd, cwd=str(out_path.parent), capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"ffmpeg compile_top5 failed with exit code {res.returncode}")

    print(f"Compiled Top {total_clips} Short: {out_path} ({total_dur:.1f}s)")


if __name__ == "__main__":
    main()
