#!/usr/bin/env python3
"""Render a quiz MP3: Alice asks each question, 8s think-pause, Daniel answers.

Script format (scripts/quiz_mcp.md):
  INTRO: ...     (optional, spoken by Alice)
  Q: ...         (question, Alice)
  A: ...         (answer, Daniel)
  OUTRO: ...      (optional, spoken by Alice)

An 8-second silence is inserted after every question (before its answer).

  export ELEVENLABS_API_KEY=sk_...   # or the sk_ token in the key file below
  python3 build_quiz.py --script scripts/quiz_mcp.md --out "episodes/quiz/MCP Quiz.mp3" --go
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

API = "https://api.elevenlabs.io/v1"
KEY_FILE = Path(os.environ.get("ELEVENLABS_KEY_FILE", str(Path.home() / ".elevenlabs_key")))
ASK = "Xb7hH8MSUJpSbSDYk0k2"   # Alice — questions
ANS = "onwK4e9ZLuTAKqWW03F9"   # Daniel — answers
MODEL = "eleven_v3"
THINK_PAUSE_S = 8.0            # silence after each question
GAP_S = 1.0                   # gap after each answer


def key() -> str:
    k = os.environ.get("ELEVENLABS_API_KEY")
    if k:
        return k.strip()
    m = re.search(r"sk_[A-Za-z0-9]+", KEY_FILE.read_text()) if KEY_FILE.exists() else None
    if m:
        return m.group(0)
    sys.exit("no API key")


def parse(path: Path) -> list[tuple[str, str]]:
    """Return [(kind, text)] where kind ∈ {intro, q, a, outro}."""
    turns = []
    for raw in path.read_text().splitlines():
        s = raw.strip()
        for tag, kind in (("INTRO:", "intro"), ("Q:", "q"), ("A:", "a"), ("OUTRO:", "outro")):
            if s.startswith(tag):
                turns.append((kind, s[len(tag):].strip()))
                break
    return turns


def silence(seconds: float, path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", str(seconds), "-q:a", "9", str(path)],
        check=True, capture_output=True)


def tts(api_key: str, voice: str, text: str, out: Path) -> None:
    r = requests.post(f"{API}/text-to-speech/{voice}",
                      json={"text": text, "model_id": MODEL},
                      headers={"xi-api-key": api_key, "Content-Type": "application/json",
                               "Accept": "audio/mpeg"}, timeout=180)
    if r.status_code != 200:
        sys.exit(f"TTS {r.status_code}: {r.text[:300]}")
    out.write_bytes(r.content)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="scripts/quiz_mcp.md")
    ap.add_argument("--out", default="episodes/quiz/MCP Quiz.mp3")
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args()

    turns = parse(Path(args.script))
    chars = sum(len(t) for _, t in turns)
    nq = sum(1 for k, _ in turns if k == "q")
    print(f"Quiz: {len(turns)} spoken segments, {nq} questions, ~{chars} credits.")
    if not args.go:
        print("DRY RUN — add --go to render."); return

    api_key = key()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        seq: list[Path] = []            # ordered list of audio pieces to concat
        pause = td / "pause.mp3"; silence(THINK_PAUSE_S, pause)
        gap = td / "gap.mp3"; silence(GAP_S, gap)
        for i, (kind, text) in enumerate(turns):
            voice = ANS if kind == "a" else ASK
            seg = td / f"{i:03d}.mp3"
            print(f"  [{i+1}/{len(turns)}] {kind}: {text[:56]}...")
            tts(api_key, voice, text, seg)
            seq.append(seg)
            if kind == "q":
                seq.append(pause)       # 8s think-pause after each question
            else:
                seq.append(gap)
        lst = td / "l.txt"
        lst.write_text("\n".join(f"file '{p.resolve()}'" for p in seq))
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", str(out)], check=True, capture_output=True)
    print(f"\n✅ Quiz written: {out.resolve()}")


if __name__ == "__main__":
    main()
