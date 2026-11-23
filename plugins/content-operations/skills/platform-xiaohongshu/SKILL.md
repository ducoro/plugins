---
name: platform-xiaohongshu
description: "Run Xiaohongshu (RedNote) end-to-end operations: search-driven topic discovery, high-save 3:4 carousel and note authoring, strict spec checks, browser-based draft staging with human publish confirmation, comment lead triage, and save-to-like retrospectives."
---

# Xiaohongshu (RedNote) Operations Playbook

Operate Xiaohongshu as a visual search-and-save engine rather than a broadcast feed. Distribution depends on cover click-through, saves, and comment depth.

## 1. Topic Discovery (Platform-Native)
- **Search intent first**: inspect Xiaohongshu search autocomplete, "related searches", and high-save posts with low follower counts (strong topic-market fit signal).
- **Winning angles**: concrete checklists, side-by-side comparisons, pitfall avoidance ("避坑/实测"), step-by-step SOPs, real setups, and before/after transformations.
- **Avoid**: generic corporate press releases, abstract essays without visual anchors, or unverifiable claims.

## 2. Native Content & Cover Structure
- **Cover (Card 1)**: `3:4` vertical (`1080x1440`) preferred. One crisp focal visual + bold 8–14 character headline promising a concrete takeaway. Readable at mobile two-column feed width.
- **Carousel (3–9 cards)**: one idea per slide; large clean typography; end with a summary checklist or save cue.
- **Title (`<= 20` chars)**: front-load the primary search keyword + concrete benefit/number.
- **Body (`<= 1000` chars)**: short scannable paragraphs, bullet points, natural conversational tone (first-person tested experience beats brochure copy), closing prompt inviting a specific comment question.
- **Topics (`<= 5` tags)**: mix 1 broad category tag + 2 mid-tail search tags + 2 niche intent tags.

## 3. Publishing & Verification (`references/protocol.md`)
- Xiaohongshu has **no general public posting OpenAPI** for standard accounts. Follow the tool-agnostic browser workflow in `references/protocol.md`:
  1. Validate copy and media with `../content-ops-loop/scripts/check_media_specs.py` against `references/specs.json`.
  2. Use whatever browser tool the host provides to fill title, body, tags, and media in Xiaohongshu Creator Studio (`creator.xiaohongshu.com`) and **save as private draft** (or hold before the final Publish click).
  3. Present a preview and Gate 2 checklist; publish only after explicit human confirmation (or let the human click final Publish).
  4. Read back the live note URL (`xiaohongshu.com/explore/<id>`) and append to `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- **Golden window**: reply to early comments within 1–2 hours; prioritize `high_intent` ("求教程/求链接/怎么用") and `feedback` comments.
- **Compliance red lines**: never post direct off-platform contact handles, QR codes, or aggressive diversion wording ("加微/私信领资料") that trigger shadowbans; avoid absolute superlatives ("第一/绝对/100%有效").
- **Rate cap**: stay under 30–40 actions/day and 6–8 actions/hour with 90–180s spacing. Stop immediately on any verification prompt.

## 5. North-Star Metrics (`platformMetrics`)
Track in `analytics/snapshots.jsonl`: `coverCtr`, `saveToLikeRatio` (strong utility signal when `>= 0.5`), `searchImpressionShare`, and `highIntentCommentCount`.
