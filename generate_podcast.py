#!/usr/bin/env python3
"""Turn a multi-voice podcast markdown script into a single MP3 via ElevenLabs.

- Model: eleven_v3 (most expressive; supports [audio tags] like [laughs]).
- Parses `**NAME:**  spoken text` turns, one voice per speaker.
- Estimates credit cost and REFUSES to spend unless you pass --go
  (so you never burn credits by accident). Use --sample N for a cheap test.

Key resolution order:
  1. $ELEVENLABS_API_KEY
  2. the sk_ token inside $ELEVENLABS_KEY_FILE (default: ~/.elevenlabs_key)

Examples:
  python3 generate_podcast.py --script scripts/tech_ep1_why_mcp.md --sample 4
  python3 generate_podcast.py --script scripts/tech_ep1_why_mcp.md --go
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

API_BASE = "https://api.elevenlabs.io/v1"
KEY_FILE = Path(os.environ.get("ELEVENLABS_KEY_FILE", str(Path.home() / ".elevenlabs_key")))

# --- Voice assignment (public premade voice IDs; swap freely) ---------------
VOICES = {
    # Technical "Defending the Build" series
    "JORDAN": "Xb7hH8MSUJpSbSDYk0k2",  # Alice  — clear, confident British interviewer
    "KESH":   "onwK4e9ZLuTAKqWW03F9",  # Daniel — deep, measured British builder
    # Accessible "Analyst That Never Sleeps" series
    "MAYA":   "AZnzlk1XvdvUeBnXmlld",  # Domi   — energetic female host
    "SAM":    "JBFqnCBsd6RMkjVDRZzb",  # George — warm British engineer
}

MODEL_ID = "eleven_v3"   # override with --model
PAUSE_MS = 500           # silence between turns (needs ffmpeg)


def get_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key.strip()
    if KEY_FILE.exists():
        m = re.search(r"sk_[A-Za-z0-9]+", KEY_FILE.read_text())
        if m:
            return m.group(0)
    sys.exit("ERROR: no API key. Set $ELEVENLABS_API_KEY or put it in the key file.")


def parse_script(path: Path) -> list[tuple[str, str]]:
    """Return [(speaker, text)] turns. Keeps [audio tags]; strips markdown."""
    turns: list[tuple[str, str]] = []
    pattern = re.compile(r"^\*\*([A-Z][A-Z ]+?):\*\*\s*(.+)$")
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(raw.strip())
        if not m:
            continue
        speaker = m.group(1).strip()
        text = m.group(2).strip()
        text = re.sub(r"\*\((.*?)\)\*", "", text)   # *(markdown stage dir)* -> gone
        text = text.replace("**", "").replace("*", "").replace("_", "")
        text = re.sub(r"\s+", " ", text).strip()     # keeps [v3 audio tags] intact
        if not text:
            continue
        if speaker in VOICES:
            turns.append((speaker, text))
        else:
            print(f"  ! No voice mapped for '{speaker}' — skipping.")
    return turns


def estimate(turns: list[tuple[str, str]]) -> int:
    return sum(len(t) for _, t in turns)


def synthesize(api_key: str, voice_id: str, text: str, model: str, out_path: Path) -> None:
    payload = {"text": text, "model_id": model}
    if model != "eleven_v3":  # v3 is happiest with defaults; tune older models
        payload["voice_settings"] = {"stability": 0.4, "similarity_boost": 0.75, "style": 0.35}
    headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    url = f"{API_BASE}/text-to-speech/{voice_id}"
    # Retry transient network/5xx/429 failures so a blip mid-render doesn't kill the whole run.
    last = ""
    for attempt in range(5):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=180)
        except requests.exceptions.RequestException as exc:
            last = str(exc)
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            out_path.write_bytes(r.content)
            return
        if r.status_code in (429, 500, 502, 503, 504):
            last = f"{r.status_code}: {r.text[:200]}"
            time.sleep(2 * (attempt + 1))
            continue
        sys.exit(f"ERROR from ElevenLabs ({r.status_code}): {r.text[:400]}")  # non-retryable
    sys.exit(f"ERROR from ElevenLabs after retries: {last}")


def stitch(segments: list[Path], out: Path) -> str:
    if shutil.which("ffmpeg"):
        with tempfile.TemporaryDirectory() as td:
            silence = Path(td) / "sil.mp3"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                 "-t", f"{PAUSE_MS/1000}", "-q:a", "9", str(silence)],
                check=True, capture_output=True)
            lst = Path(td) / "l.txt"
            lines = []
            for i, seg in enumerate(segments):
                lines.append(f"file '{seg.resolve()}'")
                if i != len(segments) - 1:
                    lines.append(f"file '{silence.resolve()}'")
            lst.write_text("\n".join(lines))
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                 "-c", "copy", str(out)], check=True, capture_output=True)
        return "ffmpeg (with pauses)"
    with out.open("wb") as f:
        for seg in segments:
            f.write(seg.read_bytes())
    return "raw concat (no ffmpeg)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", default=None, help="output mp3 (default: sibling of script)")
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--sample", type=int, default=0, help="only render the first N turns (cheap test)")
    ap.add_argument("--go", action="store_true", help="actually spend credits (otherwise dry-run estimate only)")
    args = ap.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        sys.exit(f"ERROR: script not found: {script_path}")

    turns = parse_script(script_path)
    if not turns:
        sys.exit("ERROR: no speaker lines parsed. Check format (**NAME:** text).")

    if args.sample:
        turns = turns[:args.sample]

    chars = estimate(turns)
    speakers = sorted(set(s for s, _ in turns))
    print(f"Script : {script_path.name}")
    print(f"Model  : {args.model}")
    print(f"Turns  : {len(turns)}  |  Speakers: {speakers}")
    print(f"Cost   : ~{chars} characters ≈ ~{chars} credits")
    if args.sample:
        print(f"(SAMPLE MODE — first {args.sample} turns only)")

    if not args.go:
        print("\nDRY RUN — nothing generated, no credits spent.")
        print("Re-run with --go to generate (add --sample N to test cheaply first).")
        return

    api_key = get_api_key()
    out = Path(args.out) if args.out else script_path.with_suffix(".mp3")

    with tempfile.TemporaryDirectory() as td:
        segments: list[Path] = []
        for i, (speaker, text) in enumerate(turns):
            seg = Path(td) / f"{i:03d}_{speaker}.mp3"
            print(f"  [{i+1}/{len(turns)}] {speaker}: {text[:64]}...")
            synthesize(api_key, VOICES[speaker], text, args.model, seg)
            segments.append(seg)
        how = stitch(segments, out)
    print(f"\n✅ Done via {how}: {out.resolve()}")


if __name__ == "__main__":
    main()
