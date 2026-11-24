---
name: platform-douyin
description: "Neutral Douyin platform advisor covering full-screen algorithmic video/carousel distribution, 3-second retention and completion levers, diverse short-video and photo-slide styles, UI safe zones, creator studio/API delivery, and compliance red lines."
---

# Douyin (抖音) Platform Expert Guide

Douyin is an **interest-graph full-screen discovery feed** plus a rapidly growing **short-video search engine**. Videos enter tiered traffic pools and expand strictly on viewer retention and engagement velocity.

## 1. Audience, Mindset & Distribution Mechanics
- **Consumption mindset**: Fast, sound-on, full-screen vertical swipe. Viewers decide within **1–3 seconds** whether to keep watching or swipe away—no warm-up intros.
- **Tiered traffic pool levers**: (1) **3-second retention & full completion rate (`完播率`)**; (2) **Re-watch rate (`复播`)**; (3) **Comments, shares, saves, and profile-click-to-follow**. Controversial or relatable comment hooks often double dwell time while viewers read replies.
- **Search traffic**: Keyword-rich spoken audio (ASR-indexed), burned-in captions, titles, and hashtags capture long-tail Douyin search ("抖音热点宝" / "巨量算数" / search dropdown).

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Title `<= 30` chars, body+tags `<= 1000` chars; `9:16` (`1080x1920`) `H.264/AAC MP4` up to 15 min (browser up to 4GB; OpenAPI `apiOverrides` caps at 100MB); photo-slide (`图文`) up to 12 images paired with trending audio.
- **Style spectrum (not one formula)**: Talking-head storytelling, cinematic B-roll & daily vlogs, street interviews, product demos, humorous skits, narrated visual explainers, and swipeable photo-music carousels.
- **Packaging & safe zones**: Keep subtitles and key visuals inside `x: 60–920`, `y: 220–1500` on `1080x1920` (avoid right action rail and bottom caption bar; see `../video-production/references/video-and-script-guide.md`). Run `../video-production/scripts/video_ops.py probe --loudness` (`-14 LUFS`, `bt709`).

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared Creator Studio / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py` (pass `--channel api` when using OpenAPI `100MB` cap). Default path: `https://creator.douyin.com/` (supports scheduling & custom cover). Optional OpenAPI: `scripts/client.py` (uses `DOUYIN_ACCESS_TOKEN`, returns H5 share/publish handoff). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Diversion & claims**: Never display QR codes, WeChat IDs, phone numbers, or third-party watermark logos (e.g., Kuaishou/Xiaohongshu watermarks trigger immediate suppression). Avoid absolute medical/financial/advertising claims; toggle AIGC disclosure when synthetic footage is used.
- **Rate cap**: Enforce `<= 6/hour`, `<= 40/day` (90–180s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `retention3s`, `completionRate`, `rewatchRate`, `avgWatchSec`, and `shareRate`.
