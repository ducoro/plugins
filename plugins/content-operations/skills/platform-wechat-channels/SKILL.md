---
name: platform-wechat-channels
description: "Neutral WeChat Channels (视频号) platform advisor covering social-graph recommendation (friend likes & chat shares), mature/general-audience mindset, Official Account cross-linking, browser Creator Studio delivery, and compliance guardrails."
---

# WeChat Channels (视频号) Platform Expert Guide

WeChat Channels combines **social-graph amplification inside WeChat** (friend likes, Moments shares, group-chat forwards) with **algorithmic discovery**.

## 1. Audience, Mindset & Distribution Mechanics
- **Audience profile**: Broadest age and demographic span across WeChat's 1B+ user base, skewing slightly older, higher purchasing power, and more trust-oriented than youth-heavy feeds.
- **Unique distribution engine**: A single **heart (`推荐/点赞`)** or **forward to a WeChat group / Moments** exposes your video directly to the viewer's real-life social network ("X 位朋友赞过"). Content that makes the sharer look thoughtful, helpful, or tasteful outperforms edgy shock bait.
- **Ecosystem leverage**: Native links to **WeChat Official Account articles**, **WeChat Store / mini-programs**, and **Live Rooms (`直播预约`)** let Channels act as the discovery top-of-funnel for private-domain trust.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Short title (`短标题`) `<= 16` chars (shown prominently on feed cards and forwards); description `<= 1000` chars; `9:16` (`1080x1920`) or `16:9` (`1920x1080`) video up to 60 min (`<= 1GB`), or `image_text` up to 9 images.
- **Style spectrum**: Calm expertise & practical advice, local/cultural stories, health/family/finance literacy, founder talks, behind-the-scenes craft, and crisp 1-minute summaries paired with an Official Account deep dive.
- **Safe zones & readability**: Slightly larger subtitle typography helps older mobile readers; keep key titles/captions inside `x: 60–930`, `y: 200–1520` on `1080x1920` (see `../video-production/references/video-and-script-guide.md`).

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser Creator Studio + Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: No general public posting OpenAPI—stage drafts in `https://channels.weixin.qq.com/` (supports custom `6:7` / `3:4` cover crop, `短标题`, Official Account article link, and scheduling). Validate via `check_media_specs.py` and verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Strict enforcement against medical miracle claims, guaranteed investment returns, unverified news rumors, and off-platform QR/contact diversion. Use WeChat's native Official Account link or WeCom service card instead.
- **Rate cap**: Enforce `<= 6/hour`, `<= 40/day` (90–180s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `shareRate` (group + Moments forwards), `friendLikeRatio`, `completionRate`, `avgWatchSec`, and `officialAccountClickThrough`.
