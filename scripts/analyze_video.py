"""Analyze a video: extract audio energy spikes and word-level transcript."""

import argparse
import json
import math
import struct
import subprocess
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel


def extract_wav(video_path: Path, wav_path: Path) -> None:
    """Extract 16kHz mono 16-bit PCM WAV from video using ffmpeg."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-sample_fmt",
        "s16",
        str(wav_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def compute_energy_peaks(wav_path: Path, window_sec: float = 2.0, top_n: int = 15) -> tuple[float, list[dict]]:
    """Compute RMS audio energy per window and return duration + top hype peaks."""
    with wave.open(str(wav_path), "rb") as wf:
        rate = wf.getframerate()
        n_frames = wf.getnframes()
        duration = n_frames / float(rate)
        chunk_frames = max(1, int(rate * window_sec))

        windows: list[tuple[float, float]] = []
        idx = 0
        while True:
            raw = wf.readframes(chunk_frames)
            if not raw:
                break
            count = len(raw) // 2
            if count == 0:
                break
            samples = struct.unpack(f"<{count}h", raw)
            rms = math.sqrt(sum(s * s for s in samples) / count)
            start_t = round(idx * window_sec, 2)
            windows.append((start_t, round(rms, 2)))
            idx += 1

    if not windows:
        return duration, []

    avg_rms = sum(w[1] for w in windows) / len(windows)
    # Sort descending by RMS and pick non-overlapping peaks at least 15s apart
    sorted_wins = sorted(windows, key=lambda x: x[1], reverse=True)
    peaks: list[dict] = []
    for start_t, rms in sorted_wins:
        if any(abs(start_t - p["time"]) < 15.0 for p in peaks):
            continue
        peaks.append(
            {
                "time": start_t,
                "rms": rms,
                "ratio_to_avg": round(rms / avg_rms, 2) if avg_rms > 0 else 0.0,
            }
        )
        if len(peaks) >= top_n:
            break

    peaks.sort(key=lambda p: p["time"])
    return round(duration, 2), peaks


def load_wav_float32(wav_path: Path) -> np.ndarray:
    """Load 16kHz mono 16-bit PCM WAV into a normalized float32 numpy array."""
    with wave.open(str(wav_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(wav_path: Path, model_size: str, device: str, compute_type: str) -> tuple[list[dict], list[dict]]:
    """Run faster-whisper to get segments and word-level timestamps."""
    audio = load_wav_float32(wav_path)
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments_iter, _info = model.transcribe(audio, word_timestamps=True, vad_filter=True)
        segments_list = list(segments_iter)
    except RuntimeError as exc:
        if device == "auto" and ("cublas" in str(exc).lower() or "cuda" in str(exc).lower()):
            print("CUDA libraries unavailable; falling back to CPU (int8)...")
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments_iter, _info = model.transcribe(audio, word_timestamps=True, vad_filter=True)
            segments_list = list(segments_iter)
        else:
            raise

    segments: list[dict] = []
    words: list[dict] = []
    for seg in segments_list:
        segments.append(
            {
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            }
        )
        if seg.words:
            for w in seg.words:
                word_text = w.word.strip()
                if word_text:
                    words.append(
                        {
                            "start": round(w.start, 2),
                            "end": round(w.end, 2),
                            "word": word_text,
                        }
                    )
    return segments, words


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze video audio peaks and transcript.")
    parser.add_argument("--input", required=True, help="Path to source video file.")
    parser.add_argument("--out", default="workspace/analysis.json", help="Output JSON path.")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny, base, small, medium).")
    parser.add_argument("--device", default="auto", help="Device: auto, cpu, or cuda.")
    parser.add_argument("--compute-type", default="int8", help="Compute type: int8, float16, float32.")
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = out_path.parent / f"{video_path.stem}_16k.wav"

    print(f"Extracting audio from {video_path.name}...")
    extract_wav(video_path, wav_path)

    print("Detecting audio energy peaks...")
    duration, peaks = compute_energy_peaks(wav_path)

    print(f"Transcribing with faster-whisper ({args.model})...")
    segments, words = transcribe(wav_path, args.model, args.device, args.compute_type)

    payload = {
        "video_path": str(video_path),
        "duration": duration,
        "top_energy_peaks": peaks,
        "transcript_segments": segments,
        "words": words,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved analysis to {out_path} ({len(segments)} segments, {len(peaks)} peaks)")


if __name__ == "__main__":
    main()
