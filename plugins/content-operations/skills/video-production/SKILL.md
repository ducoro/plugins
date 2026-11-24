---
name: video-production
description: Neutral video production advisor and validation toolkit for Douyin, TikTok, YouTube, Bilibili, WeChat Channels, and Kuaishou—covering scripts, SRT subtitles, UI safe zones, loudness/codec checks, exact-pixel covers, and code-driven or footage-based packaging.
---

# Video Scripting, Packaging & Validation Workshop

Advise on platform-native video structure, pacing, subtitles, audio loudness, safe zones, and thumbnails for short vertical video (`9:16`) and mid/long horizontal video (`16:9`). Always pair with the target platform skill (`platform-douyin`, `platform-tiktok`, `platform-youtube`, `platform-bilibili`, `platform-wechat-channels`, `platform-kuaishou`).

> **Scope of built-in video tooling**: This plugin does not bundle a generative text-to-video backend. It supports (1) **code-driven programmatic video** (e.g., Remotion, HyperFrames) rendered to `H.264/AAC MP4`, and (2) **any user-supplied footage, screen recordings, or externally produced clips** packaged with scripts, validated SRT captions, loudness/codec checks, and exact-pixel covers.

## References & Scripts
- `references/video-and-script-guide.md` — per-platform UI safe-zone coordinates, `-14 LUFS` loudness & `bt709` color standards, CN/EN speaking-rate benchmarks, hook & chapter patterns, line-indexed long-to-short clipping workflow, and cover packaging.
- `scripts/video_ops.py` — zero-dependency CLI for `probe [--loudness]`, `validate-srt`, `estimate-duration`, `index-transcript`, `plan-clips`, and `slice-clips`.

## Workflow

1. **Read the target video platform skill & `specs.json` first.**
   - Lock exact aspect ratio (`9:16` `1080x1920` vertical vs. `16:9` `1920x1080` landscape), duration bounds (e.g. YouTube Shorts `<= 180s`), and cover specs.
2. **Author `script.md` separately from the publishable caption (or repurpose long-form video via line-indexed clipping).**
   - Save spoken lines, `[Visual / Cut]` cues, and beat timings in `<workspace>/drafts/<draft-id>/script.md`, then check estimated runtime:
     ```sh
     python3 scripts/video_ops.py estimate-duration <workspace>/drafts/<draft-id>/script.md
     ```
   - **Long-to-short repurposing (podcasts, talks, demos with `.srt`/`.vtt` captions)**: never ask a model to guess raw timestamps—index the subtitle cues first, select exact non-overlapping `[from, to]` cue index ranges (default 20–90s), validate deterministically, then slice with local `ffmpeg` and rebased `.srt` files:
     ```sh
     python3 scripts/video_ops.py index-transcript <source.srt> --text-only
     python3 scripts/video_ops.py plan-clips <source.srt> --plan <clips.json> --min-sec 20 --max-sec 90
     python3 scripts/video_ops.py slice-clips <source.mp4> <source.srt> --plan <clips.json> --out-dir <out-dir> --aspect 9:16
     ```
   - Keep `variants/<platform>.md` strictly to the ```` ```json ```` metadata fence (`platform`, `mode: "video"|"shorts"`, `title`, `topics`, top-level `cover: {"path": "..."}`, `media: [{"type": "video", "path": "...", "durationSec": ...}]`) plus publishable caption/description.
3. **Inspect video, subtitles & cover deterministically.**
   ```sh
   python3 scripts/video_ops.py probe <draft-dir>/assets/<video>.mp4 --loudness
   python3 scripts/video_ops.py validate-srt <draft-dir>/assets/<captions>.srt
   python3 ../content-ops-loop/scripts/check_media_specs.py <workspace>/drafts/<draft-id> --update-meta
   ```
   - Build exact-pixel covers/thumbnails (`thumb-16x9` `1280x720`, `9:16` cover, etc.) using `../shortform-social/scripts/card_deck.py` or `../content-ops-loop/scripts/image_ops.py`.

## Done When
- `script.md` runtime matches target duration; optional `.srt` passes `video_ops.py validate-srt`.
- Video passes `video_ops.py probe` (`H.264/AAC MP4`, clean loudness/aspect) and `check_media_specs.py --update-meta` exits `0`.
