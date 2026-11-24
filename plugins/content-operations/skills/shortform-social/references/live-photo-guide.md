# Live Photo Motion-Card Production Guide

Use `scripts/live_photo.py` when the user supplies real video clips or screen recordings and wants **Xiaohongshu (`5s`)** or **WeChat Official Account (`3s`)** Live Photo motion cards.

> **Key principle:** Live Photo embeds short motion inside a normal `3:4` (`1080×1440`) social card. Its opening frame should stand cleanly as a static cover (`assets/examples/xhs-live-photo/index.html` provides a transparent typography overlay starter and layout geometry reference).

## 1. Platform Specs & Practical Gotchas

- **Duration ceilings**: Xiaohongshu `<= 5.0s` (hard ceiling `5.2s`); WeChat Official Account `<= 3.0s` (hard ceiling `3.2s`).
- **Mobile-only `.pvt` ingestion**: desktop web Creator Studios cannot import `.pvt` as Live Photo. Package `JPG + MOV` into a single Apple `.pvt` bundle, AirDrop (or transfer as one bundle) to iPhone, and upload via the mobile app. When publishing from desktop web or Android, offer `--fallback-mp4` or `--fallback-gif`.
- **Audio**: `live_photo.py compose` preserves the primary clip's ambient audio (AAC) by default—pass `--mute` when silence is preferred (e.g., noisy screen recordings or multi-clip collages).
- **HDR / HLG footage**: iPhone HDR/HLG clips can look washed out if re-encoded naively; inspect the exported key JPG and fallback MP4 visually before delivery.
- **Cover frame (`still-image-time`)**: `live_photo_packager.swift` pins the still cover frame at timestamp `0`, so choose `--start` where the opening frame reads clearly without black frames or blur.

## 2. Duration & Intake Workflow

1. **Probe first**:
   ```sh
   python3 scripts/live_photo.py probe <clip.mp4> --platform xiaohongshu --json
   ```
   - `long_video_needs_diagnosis`: generate a sparse contact sheet (`contact-sheet <clip.mp4> -o contact-sheet.png`), inspect timestamps visually, and confirm with the user whether to trim, speed up, or split into multiple wells.
   - `too_short_needs_confirm`: ask whether to provide a longer clip, accept a shorter Live Photo, or intentionally slow down—never freeze-frame silently.
2. **Preview static opening frame first**:
   ```sh
   python3 scripts/live_photo.py extract-frame <clip.mp4> --at 0.0 -o drafts/<id>/assets/first-frame.jpg
   ```

## 3. Six Layouts (`1080 × 1440`)

| Layout (`--layout`) | Clips | Notes |
|---|---|---|
| `single` | 1 | Full `3:4` frame; optional stationary transparent `--overlay <png>` (typography stays still while footage moves) |
| `grid-2` | 2 | Vertical two-stack (great for before/after or dual angles) |
| `stack-3` | 3 | Three wide horizontal strips stacked vertically (**best for 16:9 landscape footage or screen recordings**) |
| `grid-3` | 3 | Top wide hero + two lower squares |
| `triple-row` | 3 | Three vertical columns side by side (best for vertical `9:16` clips) |
| `grid-4` | 4 | `2×2` four-grid puzzle (`536×716` wells at default `--gap 8`) |

Use `--crop-x 0.15,0.5,0.8` (`0.0` left → `1.0` right) to protect off-center faces, products, or UI widgets, and `--bg-color 0xRRGGBB` to customize gutter color.

## 4. Compose, Package `.pvt` & Validate

```sh
python3 scripts/live_photo.py compose <clip.mp4> -o drafts/<id>/assets/motion-01.mov \
  --platform xiaohongshu --layout single --start 0.0 --duration 5.0 --crop-x 0.5 \
  --key-jpg drafts/<id>/assets/motion-01.jpg --fallback-mp4 drafts/<id>/assets/motion-01.mp4 --json

# macOS native (zero third-party packages); non-macOS hosts use --fallback-mp4 / --fallback-gif
python3 scripts/live_photo.py package-pvt drafts/<id>/assets/motion-01.jpg \
  drafts/<id>/assets/motion-01.mov -o drafts/<id>/assets/motion-01.pvt --json

python3 scripts/live_photo.py validate drafts/<id>/assets/motion-01.pvt --platform xiaohongshu --json
```
