"""Delete temporary source videos and WAV files after clips are rendered."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up large temporary source/WAV files.")
    parser.add_argument("--workspace", default="workspace", help="Workspace directory.")
    args = parser.parse_args()

    ws = Path(args.workspace)
    removed = 0
    freed_bytes = 0

    for pattern in ["source/*", "*_16k.wav"]:
        for path in ws.glob(pattern):
            if path.is_file():
                freed_bytes += path.stat().st_size
                path.unlink()
                removed += 1

    freed_mb = freed_bytes / (1024 * 1024)
    print(f"Cleaned up {removed} temporary files ({freed_mb:.1f} MB freed).")


if __name__ == "__main__":
    main()
