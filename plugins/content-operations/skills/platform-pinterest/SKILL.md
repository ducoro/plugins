---
name: platform-pinterest
description: "Neutral Pinterest platform advisor covering visual search-engine compounding (weeks to months), 2:3 vertical Pin design, keyword-rich board/title/description SEO, outbound click intent, browser vs API (board_id) delivery, and long-horizon analytics."
---

# Pinterest Platform Expert Guide

Pinterest is a **visual discovery and planning search engine**, not a real-time social feed. Users arrive with future-oriented intent (designing, shopping, cooking, traveling, learning, building) and actively save Pins to themed Boards for later action. Always defer to the mounted agent's own context (profile, memory, private skills, workspace state) for voice, goals, and targets.

## 1. Audience, Mindset & Distribution Mechanics
- **Compounding time horizon**: Unlike ephemeral feeds that peak in 24 hours, a well-indexed Pin often gains momentum over **2–12 weeks** and keeps driving outbound clicks for months or years—always track **T+30d** snapshots.
- **Visual + keyword indexing**: Pinterest ranks Pins by matching **Board context**, **Pin title & description keywords**, **image visual recognition (Pinterest Lens)**, and **save-to-impression rate + outbound click rate**.
- **Fresh Pin principle**: New visual assets (`2:3` layouts, fresh photography, updated infographics) consistently earn fresh distribution, whereas endlessly re-pinning identical images stalls.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Title `<= 100` chars; description `<= 800` chars; 1 primary image (`<= 20MB`, **`2:3` `1000x1500`** recommended; `recommendations.coverAspectRatio: 0.5–1.0`) or 1 vertical video (`<= 5 min`); no native hashtag field (weave natural search terms into title + description instead).
- **Style spectrum**: High-craft photography (interior, fashion, food, travel, DIY), step-by-step infographics & visual checklists (`../shortform-social/scripts/card_deck.py`), moodboards, product lookbooks, and short visual how-to clips. Keep overlay text concise and legible at masonry-grid width.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py` (pass `--channel api` for OpenAPI, which enforces `apiOverrides.requiredOptions: ["board_id"]`; browser mode lets you pick a Board interactively). Default path: `https://www.pinterest.com/pin-creation-tool/`. Optional OpenAPI: `scripts/client.py` (`PINTEREST_ACCESS_TOKEN`; public HTTPS image URL via `ducoro-cli media upload <path> --json`). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Destination links must load cleanly and match the Pin's promise (broken redirects, cloaked affiliate links, or misleading clickbait get domain-throttled); respect copyright and creator attribution.
- **Rate cap**: Enforce `<= 10/hour`, `<= 50/day` (45–90s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `saveRate`, `outboundClickRate`, `pinClickRate`, and `30dCompoundingImpressions`.
