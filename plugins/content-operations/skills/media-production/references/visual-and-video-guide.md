# Visual & Video Production Guide

## Cover & Visual Card Principles
1. **One visual focal point + one headline**: covers read at mobile thumbnail width (~160px wide). Avoid > 12–15 Chinese characters or > 8 English words on a cover.
2. **Match native aspect ratio before export**:
   - Xiaohongshu / Instagram feed: `3:4` (`1080x1440`) or `4:5` (`1080x1350`)
   - Douyin / TikTok / Reels / Shorts / WeChat Channels: `9:16` (`1080x1920`)
   - YouTube / Bilibili / X landscape / WeChat Official cover: `16:9` (`1920x1080` or `1280x720`)
   - Pinterest standard Pin: `2:3` (`1000x1500`)
3. **Safe zones**: keep cover text inside the middle 70% height on vertical video (`9:16`) so platform UI overlays (right-side action bar, bottom caption bar) never clip titles.

## Built-In AI Image Generation & Editing (`image_generate` in Ducoro)
When running inside Ducoro with the built-in `image_generate` tool available, call it directly instead of stopping at text prompts:
- **Supported parameters**:
  - `prompt`: concrete visual description or edit instruction.
  - `aspectRatio`: match target platform (`3:4`, `4:5`, `9:16`, `16:9`, `1:1`, `2:3`).
  - `size` (`1024x1024`, `2K`), `quality` (`auto` | `low` | `medium` | `high`), `outputFormat` (`png` | `jpeg` | `webp`), `background` (`auto` | `transparent` | `opaque`), `n` (`1`–`4`).
  - `referencePaths`: up to 16 **current-Space workspace-relative** paths for reference-guided editing or style consistency. If a reference image lives in the shared Local Folder (`~/.ducoro/workspaces/content-ops/...`), copy it into a temp subfolder of the current Space working directory first before passing its relative path.
- **Prompt skeleton**:
  - **Subject & Action**: concrete visible subject, posture, environment.
  - **Composition & Camera**: shot size, angle, aspect ratio, negative space reserved for title overlay.
  - **Lighting & Palette**: consistent with `brand-profile.md`.
  - **Constraints**: avoid tiny garbled text (render Chinese/UI typography via HTML `board shot` instead), no watermarks, no artifacts.
- **Cost & archival hygiene**: `image_generate` charges the user's wallet. Generate `n: 1` first to lock visual direction and confirm with the user before generating large batches. Copy approved outputs from the Space working folder into `content-ops/drafts/<draft-id>/assets/` and run `image_ops.py probe` / `compress` if needed.

## Built-In Exact-Pixel Card & Carousel Rendering (`ducoro-cli board shot`)
For Xiaohongshu / Instagram carousels, quote cards, checklists, YouTube/Bilibili thumbnails, or WeChat covers where crisp Chinese/English typography matters, **render HTML frames to exact-pixel PNGs directly using Ducoro's built-in Board renderer** rather than relying on AI text-in-image:

1. Create a dedicated artwork Board in the active Space:
   ```sh
   ducoro-cli board new --space <space-id> --title "<Draft Card Deck>" --json
   ```
2. Copy `assets/card-deck-template/index.html` into that Board folder (`<space-work-root>/boards/<board-id>/index.html`). Edit each `[data-ducoro-export-frame="<id>"]` card (e.g., `card-01`, `card-02` at `1080x1440`; `thumb-16x9` at `1280x720`; `wechat-cover` at `900x383`). Remove unused frames. To combine AI artwork with crisp typography, place `image_generate` outputs in that Board's `assets/` folder and reference them with relative paths (`assets/cover-art.png`).
3. Run geometry, overflow, resource, and font checks before rendering:
   ```sh
   ducoro-cli board check --space <space-id> --board boards/<board-id> --json
   ```
   Fix any reported overflow, clipping, missing asset, or font fallback until `clean: true` (or all warnings are resolved).
4. Export exact-pixel PNGs:
   - Single frame (`<id>.png`):
     ```sh
     ducoro-cli board shot --space <space-id> --board boards/<board-id> --query frame=card-01 --json
     ```
   - All declared frames in one ZIP (`export-frames.zip`):
     ```sh
     ducoro-cli board shot --space <space-id> --board boards/<board-id> --query pack=all --json
     ```
   - If `board shot` returns `ok: false` with `reason: renderer-installable`, **ask the user for confirmation** before running `ducoro-cli board install-renderer` (large browser download).
5. Visually inspect the rendered PNG(s) returned by `board shot`, then copy/unzip the verified PNGs into `content-ops/drafts/<draft-id>/assets/` (and run `check_media_specs.py` against `references/specs.json`).

## Video Script, Voiceover & Edit Checklist
> **Current host boundary**: AI video generation and text-to-speech (TTS) are **not** built-in Ducoro tools yet. For video deliverables, produce the full spoken script and shot list (`drafts/<draft-id>/script.md`), SRT subtitles, and exact-pixel covers (`image_generate` + `board shot`). When the user supplies footage/audio (or external video/TTS exports), inspect and package them (using local `ffmpeg` if installed) and validate against `specs.json`.

1. **0–3s Hook**: immediate visual change or concrete tension—never start with slow logo intros or "Hey guys welcome back".
2. **Audio continuity**: verify clear vocal intelligibility, balanced background music (-18 to -24 dB below speech), and clean cut boundaries without clicks.
3. **Subtitles**: burn in or provide SRT captions sized for mobile readability, positioned above the bottom 20% UI overlay zone.
4. **Export check**: inspect codec (`H.264/AAC MP4` is universally safest), exact duration, resolution, and file size against `specs.json`.

## Deterministic Image Pipeline (`scripts/image_ops.py`)
Use `image_ops.py` for repeatable non-AI pixel edits:
- `probe`: inspect width, height, aspect ratio, format, and file size (works with Python stdlib alone).
- `ratio-crop`: center or gravity-anchored crop to exact aspect ratio (e.g., `3:4`, `9:16`, `16:9`, `4:5`).
- `resize` / `compress`: fit pixel bounds and byte-size ceiling for target platform limits.
- `overlay` / `watermark` / `rounded`: composite logos, QR codes, or rounded corners using real probed coordinates.
