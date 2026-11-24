---
name: platform-instagram
description: "Neutral Instagram platform advisor covering Reels non-follower discovery vs Carousel/Feed retention and DM-send amplification, Stories intimacy, browser (up to 20 PNG/JPG) vs Graph API (10 JPG) channel splits, and compliance guardrails."
---

# Instagram Platform Expert Guide

Instagram operates as **four distinct surfaces under one profile**: **Reels** (non-follower reach), **Feed Carousels & Photos** (saves, dwell, and DM sends), **Stories** (daily follower intimacy), and **Grid/Profile** (visual portfolio that converts visitors into followers).

## 1. Audience, Mindset & Distribution Mechanics
- **Distribution levers (confirmed by Instagram's ranking guidance)**:
  - **Watch time / swipe depth** (completing a Reel or swiping through a multi-slide Carousel; Instagram even re-serves slide 2 to users who scrolled past slide 1).
  - **Sends per reach (DM shares)** — strongest signal for unconnected/non-follower discovery ("I have to send this to a friend").
  - **Likes & saves per reach** — utility and aesthetic resonance.
- **Originality weighting**: Reposted aggregator clips and third-party watermarked videos (e.g., TikTok logo) are actively downranked in Reels recommendations.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Caption `<= 2200` chars (first ~125 chars visible before "more"); hashtags `<= 30` hard cap (`recommendations.maxTopicCount: 5` clean topical tags).
  - **Browser / App (default)**: up to **20 images** (`jpg/jpeg/png/webp`), Feed ratio `0.8` (`4:5` `1080x1350` maximizes screen height) to `1.91` (`1.91:1`); Reels & Stories `9:16` (`1080x1920`, exempt from Feed ratio when `options.media_type` is `REELS` or `STORIES`).
  - **Graph API (`--channel api`)**: `apiOverrides` enforces **JPEG-only** (`jpg/jpeg`) and **max 10 images** per carousel, fetched from public HTTPS URLs (`ducoro-cli media upload <path> --json`).
- **Style spectrum**: Editorial/lifestyle photography, `4:5` visual carousels (`../shortform-social/scripts/card_deck.py --preset ig-carousel`), aesthetic photo dumps, Reels storytelling/tutorials/B-roll, and casual Stories behind-the-scenes.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Run `check_media_specs.py` (pass `--channel api` when using Graph API). Default path: `https://www.instagram.com/` or Meta Business Suite (`business.facebook.com`). Optional OpenAPI: `scripts/client.py` (`INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_IG_USER_ID`, Professional account required). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Tag paid partnerships transparently; avoid engagement-bait loops ("comment X 10 times"), third-party video watermarks, and automated DM/follow bursts.
- **Rate cap**: Enforce `<= 10/hour`, `<= 50/day` (45–90s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `sendsPerReach` (DM shares), `saveRate`, `avgWatchSec`, `nonFollowerReachPct`, and `profileVisitToFollowRate`.
