# Visual & Video Production Guide

## Cover & Visual Card Principles
1. **One visual focal point + one headline**: covers read at mobile thumbnail width (~160px wide). Avoid > 12–15 Chinese characters or > 8 English words on a cover.
2. **Match native aspect ratio before export**:
   - Xiaohongshu / Instagram feed: `3:4` (`1080x1440`) or `4:5` (`1080x1350`)
   - Douyin / TikTok / Reels / Shorts / WeChat Channels: `9:16` (`1080x1920`)
   - YouTube / Bilibili / X landscape / WeChat Official cover: `16:9` (`1920x1080` or `1280x720`)
   - Pinterest standard Pin: `2:3` (`1000x1500`)
3. **Safe zones**: keep cover text inside the middle 70% height on vertical video (`9:16`) so platform UI overlays (right-side action bar, bottom caption bar) never clip titles.

## Generative Prompt Skeleton (Model-Agnostic)
When calling any image or video generation tool available in the host environment, assemble prompts cleanly:
- **Subject & Action**: concrete visible subject, posture, environment.
- **Composition & Camera**: shot size, angle, aspect ratio, negative space reserved for title overlay.
- **Lighting & Palette**: consistent with `brand-profile.md`.
- **Constraints**: no garbled tiny text, no watermarks, no artifacts.

## Video Script & Edit Checklist
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
