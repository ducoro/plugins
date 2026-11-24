---
name: platform-xiaohongshu
description: "Neutral Xiaohongshu (RedNote) platform advisor covering user mindset, dual-column cover CTR, CES engagement and search distribution, diverse note/carousel/Live Photo formats, compliance red lines, browser Creator Studio delivery, and save/search analytics."
---

# Xiaohongshu (RedNote) Platform Expert Guide

Xiaohongshu is a **visual discovery + lifestyle search engine**. Users browse a mobile **two-column waterfall feed** looking for authentic human perspective ("活人感") and actively search for real experiences before making decisions. Always defer to the mounted agent's own context (profile, memory, private skills, workspace state) for voice, goals, and targets.

## 1. Audience, Mindset & Distribution Mechanics
- **Who is here & why**: High-intent planners and visual browsers across lifestyle, travel, food, beauty, home, parenting, fitness, career, education, photography, and tools. They compare real experiences and save posts for later action.
- **Traffic entries**: (1) **Discovery waterfall** (decided in <1 second by cover image + title at half-screen width); (2) **Search (`搜索`)** (evergreen compounding traffic driven by exact keywords in title, slide text, body, and bottom tags); (3) **Profile & collections** (cohesive visual identity converts single-note readers into followers).
- **Distribution levers (CES weighting)**: Comments, saves (`收藏`), shares, and dwell/swipe-through carry substantially higher weight than passive likes. Early velocity in the first 1–2 hours after publishing unlocks larger traffic pools.
- **Signals worth watching**: Search dropdown autocomplete, "大家都在搜", and low-follower posts with high save counts (proven topic-demand fit).

## 2. Formats & Content Spectrum (Starter Patterns, Not One Style)
- **Specs (`references/specs.json`)**: Title `<= 20` chars; body `<= 1000` chars; up to **18 images** (`3:4` `1080x1440` preferred, `1:1` / `4:5` / `9:16` supported; `recommendations.maxTopicCount: 5`); video up to 60 min.
- **Visual modes**:
  - **Real photography & lifestyle essays** (food, travel, OOTD, home, city walks, vlogs) — natural light, honest framing, minimal or no overlay text.
  - **Structured visual cards & carousels** (checklists, route maps, comparisons, book notes, teardowns) — build via `../shortform-social/scripts/card_deck.py` (`xhs-carousel`) or custom HTML; ensure cover text stays readable at two-column thumbnail width.
  - **Live Photo (`实况图`) motion cards** — moving footage + crisp overlay packaged into `.pvt` via `../shortform-social/scripts/live_photo.py` (see `../shortform-social/references/live-photo-guide.md`).
  - **Short vertical video** (`9:16`) — pair with `../video-production/SKILL.md`.
- **Copy craft**: Front-load the search keyword in the 20-char title; write like a real person sharing a lived observation or trade-off rather than brochure copy; end with a genuine question if inviting discussion.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser Creator Studio + Gate 2 flow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: No general public posting OpenAPI—stage drafts in `https://creator.xiaohongshu.com/`, validate first with `../content-ops-loop/scripts/check_media_specs.py`, pause at Gate 2 (`validate_workspace.py --verify-slot <slotId>`), and read back `xiaohongshu.com/explore/<id>`.

## 4. Platform Red Lines & Engagement
- **Off-platform diversion (`引流`)**: Raw WeChat IDs, phone numbers, QR codes, external links, or homophones ("加V/绿泡泡/主页微") in notes or comments trigger severe throttling or mutes. Use official creator shop/service links or compliant flows.
- **Claims & commercial disclosure**: Avoid absolute Advertising Law superlatives ("第一/绝对/100%有效"), unverified medical/financial claims, and undisclosed sponsorships (declare via 蒲公英 / commercial tools when paid).
- **Rate cap**: Enforce `<= 6/hour`, `<= 40/day` (90–180s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `coverCtr`, `saveToLikeRatio` (strong utility signal when `>= 0.5`), `searchImpressionShare`, and `highIntentCommentCount`.
