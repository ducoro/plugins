---
name: platform-youtube
description: "Neutral YouTube platform advisor covering Browse/Suggested/Search discovery, thumbnail+title CTR paired with AVD and viewer satisfaction, Shorts (up to 180s) vs long-form packaging, studio/API delivery, and compliance guardrails."
---

# YouTube Platform Expert Guide

YouTube is the world's largest **long-form video library, recommendation engine, and visual search engine**—paired with a separate **Shorts (`<= 180s`)** discovery feed.

## 1. Audience, Mindset & Distribution Mechanics
- **Three core traffic sources (long-form)**: (1) **Browse (Home)** — biggest scale, driven by curiosity-gap `16:9` thumbnail + title CTR and high Average View Duration (AVD); (2) **Suggested (Up Next)** — rewards thematic session continuation; (3) **Search** — evergreen compounding views for tutorials, reviews, explanations, and reference content.
- **Shorts (`mode: "shorts"`, up to `180s`)**: Judged primarily on **Viewed vs. Swiped Away** in the first 2 seconds and **>100% loop/rewatch retention** for shorter clips.
- **Satisfaction beyond clicks**: Clickbait that causes a steep 0–30s drop kills Browse distribution; packaging must accurately match the opening 15 seconds.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Title `<= 100` chars (front-load key idea in first ~60 chars for mobile); description `<= 5000` chars (supports `00:00` chapter timestamps); tags total `<= 500` chars; long-form `16:9` (`1920x1080` or 4K) up to 12h / 256GB; Shorts `9:16` (`1080x1920`, `<= 180s`); custom thumbnail `1280x720` (`<= 2MB` JPG/PNG).
- **Style spectrum**: Video essays, tutorials & walkthroughs, vlogs & documentaries, podcasts & interviews, product reviews, educational explainers, entertainment/comedy, and vertical Shorts.
- **Packaging**: Pair thumbnail and title as complementary halves (don't repeat the exact same words on both); build `1280x720` thumbnails via `../shortform-social/scripts/card_deck.py --preset youtube-thumb` or real stills; verify `-14 LUFS`, `bt709`, and SRT captions with `../video-production/scripts/video_ops.py`.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared Studio / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py` (use `mode: "shorts"` to enforce the 180s Shorts limit). Default path: `https://studio.youtube.com/` (A/B thumbnail tests, end screens, cards, chapters, scheduling). Optional OpenAPI: `scripts/client.py` (`YOUTUBE_ACCESS_TOKEN`). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Set `madeForKids` accurately (COPPA), toggle **Altered or synthetic content** disclosure for realistic AI visuals/audio, declare paid promotions truthfully, and clear music/footage rights (Content ID).
- **Rate cap**: Enforce `<= 12/hour`, `<= 60/day` (30–60s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `thumbnailCtr`, `avgViewDurationSec`, `avgViewPct`, `viewedVsSwipedPct` (Shorts), and `returningViewers`.
