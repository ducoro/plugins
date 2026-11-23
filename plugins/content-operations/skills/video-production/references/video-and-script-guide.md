# Video Scripting, Safe Zones & Code-Driven Production Checklist

## 1. Supported Video Production Paths (No Text-to-Video APIs)
- **Not supported**: generative text-to-video APIs (e.g., Seedance or similar prompt-to-video diffusion endpoints) are intentionally excluded because they cannot guarantee reproducible edits, legible product UI, or accurate typography.
- **Path A — Code-Driven / Programmatic Video (Remotion / HyperFrames)**: author deterministic scenes in code (React/HTML/CSS/SVG + optional `image_generate` artwork + user-supplied audio) and render `H.264/AAC MP4` (`9:16` `1080x1920` or `16:9` `1920x1080`) into `drafts/<draft-id>/assets/`.
- **Path B — Real Footage / Screen Recordings**: pair human-recorded clips with `script.md`, SRT subtitles, crisp thumbnails (`image_generate` + `ducoro-cli board shot`), and optional local `ffmpeg` trim/muxing.
- **Voiceover (TTS)**: text-to-speech is not a built-in host tool yet; deliver timed spoken copy and SRT captions for human recording or user-chosen external audio.

## 2. Spoken Script & Pacing (`drafts/<draft-id>/script.md`)
- **0–3s Hook**: immediate visual change, concrete result, or crisp tension—never slow logo intros or "Hey guys welcome back".
- **Spoken cadence**: short speakable clauses (one idea per beat), alternating `Spoken:` lines with `[Visual / Shot]` cues; add a concrete pivot or visual proof every 5–10 seconds for short vertical video.
- **Long/mid-form video (YouTube, Bilibili)**: chaptered outline (0–15s promise, proof, structured walkthrough, pitfalls/trade-offs, clear takeaway).
- Keep `script.md` separate from the publishable caption in `variants/<platform>.md`.

## 3. Cover, Safe Zones & Spec Hygiene
- **Aspect ratios**: `9:16` (`1080x1920`) for Douyin / TikTok / Reels / Shorts / WeChat Channels / Kuaishou; `16:9` (`1920x1080`, thumbnails `1280x720`) for YouTube / Bilibili.
- **Safe zones**: keep vertical video cover headlines and subtitles inside the middle 70% height and above the bottom 20% UI bar so platform overlays never clip text.
- **Metadata contract**: place the video cover under top-level `"cover": {"path": "assets/cover.jpg"}` (never inside `media[]`, which rejects mixed image+video) and declare `"durationSec"` on every video entry so `../content-ops-loop/scripts/check_media_specs.py` validates duration ceilings.
- **Export check**: verify `H.264/AAC MP4`, balanced vocal vs. background music (`-18` to `-24 dB`), clean cuts, and exact byte size against `../platform-<name>/references/specs.json`.
