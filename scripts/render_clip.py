"""Render a 9:16 vertical short clip with burned-in captions and optional hook title."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


STYLE_PRESETS = {
    "classic": {
        "base_color": "&H00FFFFFF",
        "active_ass": r"{\c&H00FFFF&}",
        "reset_ass": r"{\c&HFFFFFF&}",
        "hook_color": "&H0000FFFF",
    },
    "neon": {
        "base_color": "&H00FFFFFF",
        "active_ass": r"{\c&HFFFF00&}",
        "reset_ass": r"{\c&HFFFFFF&}",
        "hook_color": "&H00FFFF00",
    },
    "emerald": {
        "base_color": "&H00FFFFFF",
        "active_ass": r"{\c&H66FF00&}",
        "reset_ass": r"{\c&HFFFFFF&}",
        "hook_color": "&H0066FF00",
    },
    "fire": {
        "base_color": "&H00FFFFFF",
        "active_ass": r"{\c&H006BFF&}",
        "reset_ass": r"{\c&HFFFFFF&}",
        "hook_color": "&H00006BFF",
    },
    "clean": {
        "base_color": "&H00CCCCCC",
        "active_ass": r"{\c&HFFFFFF&}",
        "reset_ass": r"{\c&HCCCCCC&}",
        "hook_color": "&H00FFFFFF",
    },
}


def build_ass_header(style: str = "classic") -> str:
    """Build ASS header with the selected caption and hook style preset."""
    preset = STYLE_PRESETS[style]
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,74,{preset['base_color']},&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,560,1
Style: Hook,Arial,80,{preset['hook_color']},&H00FFFFFF,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,3,12,0,8,70,70,250,1
Style: Watermark,Arial,32,&H88FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,3,30,45,380,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def fmt_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cc."""
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"


def escape_ass(text: str) -> str:
    """Escape special ASS characters."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def build_ass_subtitles(
    words: list[dict],
    clip_start: float,
    clip_end: float,
    title: str | None,
    words_per_chunk: int = 3,
    has_cam: bool = False,
    style: str = "classic",
    watermark: str | None = None,
) -> str:
    """Create ASS subtitle content with active-word highlight, hook title, and optional watermark."""
    preset = STYLE_PRESETS[style]
    lines = [build_ass_header(style)]
    clip_duration = clip_end - clip_start

    if watermark:
        lines.append(
            f"Dialogue: 2,0:00:00.00,{fmt_ass_time(clip_duration)},Watermark,,0,0,0,,{escape_ass(watermark)}"
        )

    if title:
        hook_end = min(3.5, clip_duration)
        # Keep hook above facecam when facecam is enabled, or centered in top blur otherwise
        hook_margin_v = 85 if has_cam else 250
        lines.append(
            f"Dialogue: 1,0:00:00.00,{fmt_ass_time(hook_end)},Hook,,0,0,{hook_margin_v},,{escape_ass(title.upper())}"
        )

    clip_words = [
        w for w in words if w["end"] > clip_start and w["start"] < clip_end
    ]
    for i in range(0, len(clip_words), words_per_chunk):
        chunk = clip_words[i : i + words_per_chunk]
        if not chunk:
            continue
        for active_idx, active_word in enumerate(chunk):
            w_start = max(0.0, active_word["start"] - clip_start)
            # Extend to next word's start (or chunk end) so captions never flicker
            if active_idx + 1 < len(chunk):
                w_end = max(w_start + 0.08, chunk[active_idx + 1]["start"] - clip_start)
            else:
                w_end = max(w_start + 0.15, active_word["end"] - clip_start)
            w_end = min(clip_duration, w_end)
            if w_end <= w_start:
                continue

            parts = []
            for j, w in enumerate(chunk):
                txt = escape_ass(w["word"].upper())
                if j == active_idx:
                    parts.append(preset["active_ass"] + txt + preset["reset_ass"])
                else:
                    parts.append(txt)
            lines.append(
                f"Dialogue: 0,{fmt_ass_time(w_start)},{fmt_ass_time(w_end)},Caption,,0,0,0,,{' '.join(parts)}"
            )

    return "\n".join(lines) + "\n"


def has_nvenc() -> bool:
    """Return True if ffmpeg can encode with h264_nvenc on this machine."""
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


def snap_start_to_speech(words: list[dict], start: float, end: float, pad: float = 0.15) -> float:
    """Snap clip start to just before the first spoken word in [start, end] to avoid dead air."""
    for w in words:
        if w["end"] > start and w["start"] < end:
            snapped = max(start, w["start"] - pad)
            if end - snapped >= 5.0:
                return round(snapped, 2)
            break
    return start


def compute_speech_keeps(
    words: list[dict], start: float, end: float, max_gap: float = 1.2, pad: float = 0.18
) -> list[tuple[float, float]]:
    """Return merged (seg_start, seg_end) speech intervals inside [start, end], cutting gaps > max_gap."""
    intervals: list[list[float]] = []
    for w in words:
        if w["end"] <= start or w["start"] >= end:
            continue
        s = max(start, w["start"] - pad)
        e = min(end, w["end"] + pad)
        if intervals and s - intervals[-1][1] <= max_gap:
            intervals[-1][1] = max(intervals[-1][1], e)
        else:
            intervals.append([s, e])
    if not intervals:
        return [(start, end)]
    return [(round(s, 3), round(e, 3)) for s, e in intervals]


def remap_words_for_keeps(words: list[dict], keeps: list[tuple[float, float]]) -> tuple[list[dict], float]:
    """Remap word timestamps onto the concatenated timeline of keep intervals."""
    remapped: list[dict] = []
    offset = 0.0
    for seg_s, seg_e in keeps:
        seg_len = seg_e - seg_s
        for w in words:
            if w["end"] > seg_s and w["start"] < seg_e:
                remapped.append(
                    {
                        "word": w["word"],
                        "start": offset + max(0.0, w["start"] - seg_s),
                        "end": offset + min(seg_len, w["end"] - seg_s),
                    }
                )
        offset += seg_len
    return remapped, round(offset, 3)


def build_cam_crop(cam_pos: str, cam_box: str | None = None) -> str:
    """Return ffmpeg crop expression for a corner facecam or explicit normalized x,y,w,h box."""
    if cam_box:
        x, y, w, h = (float(v.strip()) for v in cam_box.split(","))
        return f"crop=iw*{w:.4f}:ih*{h:.4f}:iw*{x:.4f}:ih*{y:.4f}"

    w = "iw*0.145"
    h = "ih*0.265"
    mx = "iw*0.015"
    my = "ih*0.015"
    positions = {
        "top-left": f"crop={w}:{h}:{mx}:{my}",
        "top-right": f"crop={w}:{h}:iw-{w}-{mx}:{my}",
        "bottom-left": f"crop={w}:{h}:{mx}:ih-{h}-{my}",
        "bottom-right": f"crop={w}:{h}:iw-{w}-{mx}:ih-{h}-{my}",
    }
    return positions[cam_pos]


def render_clip(
    video_path: Path,
    start: float,
    end: float,
    out_path: Path,
    ass_path: Path,
    layout: str,
    cam_pos: str = "none",
    cam_box: str | None = None,
    keeps: list[tuple[float, float]] | None = None,
) -> None:
    """Render 1080x1920 vertical clip with ffmpeg (uses NVENC GPU if available)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start
    if duration <= 0:
        raise ValueError("Clip end time must be greater than start time.")

    # Use relative filename for ass filter to avoid Windows drive-letter escaping issues
    ass_filename = ass_path.name
    use_concat = keeps is not None and len(keeps) >= 2

    if use_concat:
        cmd = ["ffmpeg", "-y", "-i", str(video_path.resolve())]
        trim_parts = []
        concat_inputs = []
        for idx, (ks, ke) in enumerate(keeps):
            trim_parts.append(f"[0:v]trim=start={ks:.3f}:end={ke:.3f},setpts=PTS-STARTPTS[tv{idx}];")
            trim_parts.append(f"[0:a]atrim=start={ks:.3f}:end={ke:.3f},asetpts=PTS-STARTPTS[ta{idx}];")
            concat_inputs.append(f"[tv{idx}][ta{idx}]")
        pre_fc = (
            "".join(trim_parts)
            + "".join(concat_inputs)
            + f"concat=n={len(keeps)}:v=1:a=1[srcv][srca];"
        )
        v_in = "[srcv]"
        a_map = "[aout]"
        a_filter = f";[srca]loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.2f}",
            "-i",
            str(video_path.resolve()),
            "-t",
            f"{duration:.2f}",
        ]
        pre_fc = ""
        v_in = "[0:v]"
        a_map = "0:a?"
        a_filter = ""

    if layout == "center-crop":
        fc = (
            f"{pre_fc}{v_in}scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,ass={ass_filename},format=yuv420p[v]{a_filter}"
        )
        cmd.extend(["-filter_complex", fc, "-map", "[v]", "-map", a_map])
    elif cam_pos != "none" or cam_box:
        # Facecam split: hook at top, lanczos+unsharp facecam at y=240 (520px tall), gameplay at y=775
        cam_crop = build_cam_crop(cam_pos, cam_box)
        fc = (
            f"{pre_fc}{v_in}split=3[vbg][vcam][vgame];"
            "[vbg]scale=270:480:force_original_aspect_ratio=increase,"
            "crop=270:480,boxblur=6:2,scale=1080:1920,eq=brightness=-0.18[bg];"
            f"[vcam]{cam_crop},scale=-2:520:flags=lanczos,unsharp=5:5:0.7:5:5:0.0[cam];"
            "[vgame]scale=1080:-2:force_original_aspect_ratio=decrease[game];"
            "[bg][cam]overlay=(W-w)/2:240[bgcam];"
            f"[bgcam][game]overlay=(W-w)/2:775,setsar=1,ass={ass_filename},format=yuv420p[v]{a_filter}"
        )
        cmd.extend(["-filter_complex", fc, "-map", "[v]", "-map", a_map])
    else:
        # gaming-split: downscale-blur background (8x faster than full-res boxblur) + crisp 16:9 gameplay
        fc = (
            f"{pre_fc}{v_in}split=2[vbg][vfg];"
            "[vbg]scale=270:480:force_original_aspect_ratio=increase,"
            "crop=270:480,boxblur=6:2,scale=1080:1920,eq=brightness=-0.12[bg];"
            "[vfg]scale=1080:-2:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2-80,setsar=1,ass={ass_filename},format=yuv420p[v]{a_filter}"
        )
        cmd.extend(["-filter_complex", fc, "-map", "[v]", "-map", a_map])

    if has_nvenc():
        video_enc = [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p5",
            "-rc",
            "vbr",
            "-cq",
            "18",
            "-b:v",
            "8M",
            "-maxrate",
            "12M",
            "-bufsize",
            "16M",
        ]
    else:
        video_enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-maxrate", "12M", "-bufsize", "16M"]

    audio_af = [] if use_concat else ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd.extend(
        [
            *audio_af,
            *video_enc,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_path.resolve()),
        ]
    )
    result = subprocess.run(cmd, cwd=str(ass_path.parent.resolve()), capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"ffmpeg render failed with exit code {result.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a vertical 9:16 gaming clip.")
    parser.add_argument("--input", required=True, help="Source video path.")
    parser.add_argument("--analysis", required=True, help="Path to analysis.json.")
    parser.add_argument("--start", type=float, required=True, help="Clip start time in seconds.")
    parser.add_argument("--end", type=float, required=True, help="Clip end time in seconds.")
    parser.add_argument("--title", default="", help="Optional 3-5 word hook title at top.")
    parser.add_argument(
        "--layout",
        choices=["gaming-split", "center-crop"],
        default="gaming-split",
        help="Vertical framing layout.",
    )
    parser.add_argument(
        "--cam-pos",
        choices=["none", "top-left", "top-right", "bottom-left", "bottom-right"],
        default="none",
        help="Optional corner facecam to stack above gameplay in gaming-split.",
    )
    parser.add_argument(
        "--cam-box",
        default=None,
        help="Optional exact normalized facecam box x,y,w,h (e.g. 0.855,0.015,0.135,0.265).",
    )
    parser.add_argument(
        "--no-snap",
        action="store_true",
        help="Disable automatic snapping of start time to the first spoken word.",
    )
    parser.add_argument(
        "--style",
        choices=list(STYLE_PRESETS.keys()),
        default="classic",
        help="Caption and hook color preset.",
    )
    parser.add_argument(
        "--watermark",
        default=None,
        help="Optional channel handle watermark (e.g. @KlipDeck).",
    )
    parser.add_argument(
        "--trim-silence",
        action="store_true",
        help="Automatically cut internal silent gaps longer than --silence-gap seconds.",
    )
    parser.add_argument(
        "--silence-gap",
        type=float,
        default=1.2,
        help="Minimum silent gap in seconds to trim when --trim-silence is enabled.",
    )
    parser.add_argument("--out", required=True, help="Output MP4 path.")
    args = parser.parse_args()

    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8-sig"))
    words = analysis.get("words", [])
    start_t = args.start if args.no_snap else snap_start_to_speech(words, args.start, args.end)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path = out_path.with_suffix(".ass")

    has_cam = args.cam_pos != "none" or bool(args.cam_box)
    keeps = None
    sub_words = words
    sub_start = start_t
    sub_end = args.end

    if args.trim_silence:
        candidate_keeps = compute_speech_keeps(words, start_t, args.end, max_gap=args.silence_gap)
        if len(candidate_keeps) >= 2:
            keeps = candidate_keeps
            sub_words, total_dur = remap_words_for_keeps(words, keeps)
            sub_start = 0.0
            sub_end = total_dur

    ass_content = build_ass_subtitles(
        sub_words,
        sub_start,
        sub_end,
        args.title or None,
        has_cam=has_cam,
        style=args.style,
        watermark=args.watermark,
    )
    ass_path.write_text(ass_content, encoding="utf-8")

    render_clip(
        video_path=Path(args.input),
        start=start_t,
        end=args.end,
        out_path=out_path,
        ass_path=ass_path,
        layout=args.layout,
        cam_pos=args.cam_pos,
        cam_box=args.cam_box,
        keeps=keeps,
    )

    final_dur = (sub_end - sub_start) if keeps else (args.end - start_t)
    meta_path = out_path.with_suffix(".metadata.txt")
    hook_title = args.title.strip() if args.title else out_path.stem.replace("_", " ").title()
    meta_content = (
        f"Title: {hook_title}\n"
        f"Caption: {hook_title} 😂🔥 #gaming #shorts #gta #clips\n"
        f"Duration: {final_dur:.1f}s ({start_t:.1f}s - {args.end:.1f}s)\n"
    )
    meta_path.write_text(meta_content, encoding="utf-8")
    print(f"Rendered clip: {out_path}")
    print(f"Saved metadata: {meta_path}")


if __name__ == "__main__":
    main()
