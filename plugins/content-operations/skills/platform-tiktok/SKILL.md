---
name: platform-tiktok
description: "Neutral TikTok platform advisor covering For You interest-graph testing, TikTok Search SEO, 9:16 video and Photo Mode (up to 35 slides) formats, UI safe zones, studio/API delivery, and compliance guardrails."
---

# TikTok Platform Expert Guide

TikTok is a **pure interest-graph discovery engine** paired with an increasingly dominant **short-form search habit** (especially among Gen Z and millennial audiences). Account size matters far less than whether a single post holds attention.

## 1. Audience, Mindset & Distribution Mechanics
- **Batch testing**: Every post starts in a small relevance batch; expansion to larger pools depends on **first-2-second hold**, **completion / rewatch rate**, **shares & saves**, and **comment activity**.
- **TikTok Search SEO**: Users actively search reviews, how-tos, travel tips, recipes, and product comparisons. TikTok indexes **spoken audio (ASR), on-screen text, caption keywords, and hashtags**—natural spoken keywords often outweigh hashtag stuffing.
- **Photo Mode (`image_text`, up to 35 slides)**: Swipeable photo carousels set to music frequently earn higher save rates and longer dwell time than talking-head clips for stories, lists, and visual comparisons.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Caption `<= 2200` chars; `9:16` (`1080x1920`) `H.264/AAC MP4` up to 10 min (`<= 4GB`); Photo Mode up to **35 images** (`jpg/jpeg/webp`, `3:4` or `9:16`).
- **Style spectrum**: Lo-fi candid talking-head stories, fast visual demos, POV/humor skits, mini-vlogs, swipeable Photo Mode essays, tutorials, and stitch/duet commentary.
- **Safe zones & audio**: Keep subtitles and focal visuals inside `x: 60–920`, `y: 220–1500` on `1080x1920` (avoid right action rail and bottom caption bar; see `../video-production/references/video-and-script-guide.md`). Check `-14 LUFS` loudness via `../video-production/scripts/video_ops.py probe --loudness`.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared Studio / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py`. Default path: `https://www.tiktok.com/tiktokstudio` (supports drafts, scheduling, sound picker, Photo Mode). Optional OpenAPI: `scripts/client.py` (`TIKTOK_ACCESS_TOKEN`; unaudited apps post privately to inbox drafts until TikTok review completes). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Enable **AI-generated content** label for realistic synthetic media, declare Branded Content truthfully, avoid unoriginal watermarked reposts, and steer clear of dangerous challenges or medical/financial guarantees.
- **Rate cap**: Enforce `<= 10/hour`, `<= 50/day` (45–90s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `retention2s`, `fullWatchRate`, `avgWatchSec`, `searchTrafficShare`, and `shareSaveRate`.
