"""Batch-render multiple 9:16 vertical clips from a JSON manifest."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-render clips from a JSON list.")
    parser.add_argument("--input", required=True, help="Source video path.")
    parser.add_argument("--analysis", required=True, help="Path to analysis.json.")
    parser.add_argument("--clips-json", required=True, help="Path to JSON array of clip specs.")
    parser.add_argument("--out-dir", default="workspace/clips", help="Output directory for clips.")
    parser.add_argument("--watermark", default=None, help="Default watermark handle for all clips.")
    parser.add_argument("--style", default="classic", help="Default caption style preset.")
    args = parser.parse_args()

    specs = json.loads(Path(args.clips_json).read_text(encoding="utf-8-sig"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    render_script = Path(__file__).with_name("render_clip.py")

    rendered = []
    for idx, spec in enumerate(specs, start=1):
        out_file = spec.get("out") or str(out_dir / f"batch_{idx:02d}.mp4")
        cmd = [
            sys.executable,
            str(render_script),
            "--input",
            args.input,
            "--analysis",
            args.analysis,
            "--start",
            str(spec["start"]),
            "--end",
            str(spec["end"]),
            "--title",
            spec.get("title", ""),
            "--layout",
            spec.get("layout", "gaming-split"),
            "--style",
            spec.get("style", args.style),
            "--out",
            out_file,
        ]
        if spec.get("cam_pos"):
            cmd.extend(["--cam-pos", spec["cam_pos"]])
        if spec.get("cam_box"):
            cmd.extend(["--cam-box", spec["cam_box"]])
        if spec.get("no_snap"):
            cmd.append("--no-snap")
        wm = spec.get("watermark", args.watermark)
        if wm:
            cmd.extend(["--watermark", wm])
        if spec.get("trim_silence"):
            cmd.append("--trim-silence")
            if spec.get("silence_gap") is not None:
                cmd.extend(["--silence-gap", str(spec["silence_gap"])])

        print(f"[{idx}/{len(specs)}] Rendering {out_file}...")
        subprocess.run(cmd, check=True)
        rendered.append(out_file)

    print(json.dumps({"rendered": rendered, "count": len(rendered)}, indent=2))


if __name__ == "__main__":
    main()
