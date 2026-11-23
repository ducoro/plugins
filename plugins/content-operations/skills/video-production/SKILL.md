---
name: video-production
description: Plan, script, package, and validate short-form and long-form videos for Douyin, TikTok, YouTube, Bilibili, WeChat Channels, and Kuaishou. Strictly supports code-driven video (Remotion, HyperFrames) and real footage/screen recordings—never text-to-video APIs.
---

# Video Script, Packaging & Code-Driven Video Workshop

Produce native spoken scripts, shot lists, SRT captions, exact-pixel thumbnails/covers, and reproducible `H.264/AAC MP4` video deliverables without loading essay-writing rules. Always pair with the target platform skill (`../platform-douyin/SKILL.md`, `../platform-tiktok/SKILL.md`, `../platform-youtube/SKILL.md`, `../platform-bilibili/SKILL.md`, `../platform-wechat-channels/SKILL.md`, `../platform-kuaishou/SKILL.md`).

> **Hard Policy — Code-Driven Video & Real Footage Only (No Text-to-Video APIs)**:
> This plugin **explicitly excludes generative text-to-video APIs** (such as Seedance or diffusion video generators). Supported paths are strictly: (1) **code-driven programmatic video** (**Remotion** or **HyperFrames**) rendered deterministically into `H.264/AAC MP4`, and (2) **human-supplied real footage or screen recordings** packaged with scripts, SRT captions, covers, and optional local `ffmpeg`.

## References (Load on Demand)
- `references/video-and-script-guide.md` — 0–3s hook patterns, spoken script vs. publishable caption separation, subtitle safe zones, Remotion/HyperFrames checklist, cover aspect ratios, and `check_media_specs.py` video fields.

## Workflow

1. **Read the target video platform skill & `specs.json` first.**
   - Lock exact aspect ratio (`9:16` `1080x1920` vertical vs. `16:9` `1920x1080` landscape), duration bounds, cover specs, and platform pacing.
2. **Write the spoken script & shot list separately from the publishable caption.**
   - Save spoken lines, `[Visual / Cut]` cues, and timing in `<workspace>/drafts/<draft-id>/script.md` (plus `.srt` subtitles when needed).
   - Keep `variants/<platform>.md` strictly to the ```` ```json ```` metadata fence (`platform`, `mode: "video"`, `title`, `topics`, top-level `cover: {"path": "..."}`, and `media: [{"type": "video", "path": "...", "durationSec": ...}]`) plus the publishable caption/description. Never mix images and video inside `media[]`.
3. **Render video & exact-pixel cover assets.**
   - **Code-driven video**: author reproducible scenes in Remotion or HyperFrames (combining React/HTML/CSS/SVG, optional `image_generate` illustrations, and user-supplied voiceover/audio) and render `H.264/AAC MP4` into `drafts/<draft-id>/assets/`.
   - **Real footage / screen recordings**: inspect duration/codec/resolution, burn or attach SRT captions above the bottom 20% UI overlay zone, and generate crisp covers via `image_generate` + `ducoro-cli board shot` (`../shortform-social/assets/card-deck-template/index.html`, e.g., `thumb-16x9` `1280x720`) + `../content-ops-loop/scripts/image_ops.py`.
4. **Validate all media & specs before Gate 2.**
   ```sh
   python3 ../content-ops-loop/scripts/check_media_specs.py <workspace>/drafts/<draft-id> --update-meta
   ```

## Done When
- `script.md` contains clear 0–3s hook, spoken pacing, and visual cues; `variants/<platform>.md` holds clean caption + JSON metadata.
- Video file (`H.264/AAC MP4`) and cover image sit under `drafts/<draft-id>/assets/` with verified duration and dimensions.
- `../content-ops-loop/scripts/check_media_specs.py --update-meta` exits `0` with zero errors.
