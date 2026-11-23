---
name: platform-douyin
description: "Run Douyin end-to-end operations: hook-driven short video and carousel topic selection, 3-second retention scripting, strict spec validation, OpenAPI and browser-assisted publishing workflows, golden-hour comment engagement, and retention-led retrospectives."
---

# Douyin Operations Playbook

Douyin is an interest-graph recommendation engine. Traffic tiers unlock sequentially based on 3-second hook retention, full completion rate, shares, and comment velocity.

## 1. Topic Discovery (Platform-Native)
- **Trend & tension signals**: Douyin Hot Search, niche search autocomplete, high-share competitor videos, and polarizing practical questions from your own comment section.
- **Winning angles**: counter-intuitive findings, live 30–60s walkthroughs, clear "before vs. after" proofs, and crisp myth-busting.

## 2. Native Content & Script Structure
- **0–3s Visual + Verbal Hook**: lead with the outcome, contradiction, or stakes immediately. Zero preamble.
- **Pacing**: cut dead air; deliver a visual change or new point every 3–5 seconds; keep primary short videos in **30–90s** (hard max 900s).
- **Format**: `9:16` vertical (`1080x1920`) for video; keep captions and cover titles inside the central 70% safe zone (avoid right action rail and bottom description overlay).
- **Copy limits**: title `<= 30` chars (`short_title <= 12` chars when set), total text `<= 1000` chars, max **5** native topics; image carousel supports up to **12** images.

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate first with `../content-ops-loop/scripts/check_media_specs.py` against `references/specs.json`.
2. **Default zero-config path (Official Douyin Creator Studio)**: open `https://creator.douyin.com/creator-micro/content/upload` in the user's browser session (pause for login/QR or verification if prompted), upload local video or image carousel directly from `drafts/<id>/assets/`, fill title, cover frame (`cover_tsp`), tags, and privacy/download settings, save draft (`draft_saved`) at Gate 2, then publish after explicit human confirmation.
3. **Optional official Douyin OpenAPI path** (requires `DOUYIN_ACCESS_TOKEN` and `DOUYIN_OPEN_ID`): use `scripts/client.py [--dry-run] query-videos --item-ids ...` and `get-fans` (`--app-type web|miniapp`) for live readback and fan counts; OAuth token exchange and QR handoff endpoints are documented in `references/protocol.md` (require approved Douyin Open Platform scopes).
4. Read back the live URL (`https://www.douyin.com/video/<id>` or `/note/<id>`) into `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- **Golden first hour**: respond thoughtfully to the first 5–10 real comments to spark comment threads; pin one helpful summary comment when appropriate.
- **Compliance red lines**: avoid direct off-platform diversion phrasing, unverified financial/medical promises, or repetitive copy-paste comments.
- **Rate cap**: stay under **40 actions/day** (6–8/hour, 90–180s spacing on browser actions). Halt immediately on risk-control or CAPTCHA prompts.

## 5. North-Star Metrics (`platformMetrics`)
Track `threeSecRetention`, `completionRate`, `shareRate`, and `followerConversionRate` in `analytics/snapshots.jsonl`.
