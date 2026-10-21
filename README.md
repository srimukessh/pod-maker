# pod-maker

Turn a two-voice (or multi-voice) markdown script into a single MP3 via [ElevenLabs](https://elevenlabs.io).
Built for long-form explainer / interview-prep "podcasts" you can listen to on repeat.

> ⛔ **All rights reserved — look, don't copy.** This repo is public for reference/portfolio
> purposes only. It is **not** open source: no permission is granted to copy, fork, run, reuse,
> or build on this code. See [`LICENSE`](LICENSE). Want to use any of it? Ask first:
> srimukessh1994@gmail.com

## What's here

| File | Does |
|------|------|
| `generate_podcast.py` | Renders a dialogue script → one stitched MP3 (one voice per speaker, pauses between turns). |
| `build_quiz.py` | Renders a quiz MP3: voice A asks, an 8-second think-pause, voice B answers. |
| `build_speeds.sh` | Derives `1.25x` / `1.5x` (etc.) speed variants from the `1x/` masters — re-times only, preserves pitch, spends **no** credits. |

## Setup

```bash
pip install requests          # the only dependency (ffmpeg recommended for pauses + speeds)
export ELEVENLABS_API_KEY=sk_...   # or put the sk_ token in ~/.elevenlabs_key
```

`ffmpeg` is used to stitch segments with pauses and to build speed variants. Without it,
`generate_podcast.py` falls back to a raw concat (no gaps).

## Script format

Each spoken turn is a bold speaker label followed by the line. Speaker names must exist in the
`VOICES` map at the top of `generate_podcast.py` (public ElevenLabs premade voice IDs — swap freely):

```markdown
**JORDAN:** So, what problem were we actually solving?

**KESH:** The data team was the bottleneck. Every question went through an analyst.
```

Markdown bold/italics and `*(stage directions)*` are stripped; ElevenLabs v3 `[audio tags]`
like `[laughs]` are kept.

## Usage

```bash
# dry run — prints the turn count + estimated credit cost, spends nothing
python3 generate_podcast.py --script scripts/my_episode.md

# cheap test — render only the first 4 turns
python3 generate_podcast.py --script scripts/my_episode.md --sample 4 --go

# full render (only --go actually spends credits)
python3 generate_podcast.py --script scripts/my_episode.md \
    --out "episodes/my-show/1x/My Episode.mp3" --go

# derive 1.25x / 1.5x speed folders from every <show>/1x/ master set
bash build_speeds.sh
```

**Cost guard:** nothing is rendered without `--go`. A dry run just prints
`~N characters ≈ ~N credits` so you never burn credits by accident. Use `--sample N` to test a
voice/script cheaply first.

## Layout it expects (for `build_speeds.sh`)

```
episodes/<show>/1x/      <- masters rendered by generate_podcast.py
episodes/<show>/1.25x/   <- derived by build_speeds.sh
episodes/<show>/1.5x/
```

## Notes

- Default model is `eleven_v3` (most expressive, supports audio tags). Override with `--model`.
- Edit `VOICES` / `SPEEDS` at the top of the respective files to change casting or speeds.
- Audio outputs are git-ignored by default — this repo is the tooling, not the episodes.
