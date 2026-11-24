---
name: platform-kuaishou
description: "Neutral Kuaishou (快手) platform advisor covering dual-column discovery + strong follower-tab trust, down-to-earth community dynamics, short-video/photo-slide packaging, creator studio/API delivery, and compliance guardrails."
---

# Kuaishou (快手) Platform Expert Guide

Kuaishou blends **equitable discovery (`发现` / `精选`)** with an unusually loyal **follower tab (`关注`)**—creators with authentic, relatable presence build durable private trust (`老铁文化`) even without constant viral hits. Always defer to the mounted agent's own context (profile, memory, private skills, workspace state) for voice, goals, and targets.

## 1. Audience, Mindset & Distribution Mechanics
- **Audience & culture**: Strong reach across tier-2 to tier-5 cities as well as nationwide practical/craft/agriculture/local-life/entertainment communities. Audiences value straightforwardness, authenticity, and real human warmth over polished corporate gloss.
- **Distribution levers**: (1) **Cover + title click-through** on dual-column discovery cards (`发现` tab) alongside **3-second retention & completion** on full-screen `精选`; (2) **Long-tail follower loyalty** (`关注` feed ensures steady baseline views for consistent series); (3) **Comment rapport & live-stream synergy**.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Title `<= 30` chars, combined text `<= 1000` chars (`recommendations.maxTopicCount: 4`); `9:16` (`1080x1920`) video up to 30 min (browser up to 4GB; OpenAPI `apiOverrides` caps at `video` mode and `100MB`); browser also supports `image_text` up to 12 images.
- **Style spectrum**: Real-life skill demos, local food/craft/business diaries, practical tutorials, humorous storytelling, honest reviews, and Q&A series responding directly to follower comments.
- **Packaging**: Provide a clear, readable cover frame (since dual-column browse matters on Kuaishou) and keep vertical subtitles inside `x: 60–930`, `y: 210–1500` (`../video-production/references/video-and-script-guide.md`).

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared Creator Studio / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py` (pass `--channel api` for OpenAPI `100MB` cap). Default path: `https://cp.kuaishou.com/` (video + photo-slide + custom cover). Optional OpenAPI: `scripts/client.py` (`KUAISHOU_ACCESS_TOKEN`). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Avoid third-party platform watermarks, off-platform QR/contact diversion, misleading price/efficacy claims, and unsafe stunts. Disclose paid promotions via 磁力聚星 / official shopping tags.
- **Rate cap**: Enforce `<= 6/hour`, `<= 40/day` (90–180s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `completionRate`, `followerReturnViewShare`, `commentRate`, `profileVisitRate`, and `liveRoomConversion`.
