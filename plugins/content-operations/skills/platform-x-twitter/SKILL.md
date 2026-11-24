---
name: platform-x-twitter
description: "Neutral X (Twitter) platform advisor covering For You vs Following feed mechanics, author-reply and bookmark weights, single posts/threads/Premium long posts/Articles, link-placement trade-offs, browser/API delivery, and engagement guardrails."
---

# X (Twitter) Platform Expert Guide

X is a **real-time public town square and interest graph** where speed, sharp perspective, conversation, and bookmarkable utility drive reach.

## 1. Audience, Mindset & Distribution Mechanics
- **Two feeds**: **Following** (chronological core audience) and **For You** (algorithmic expansion into adjacent interest graphs).
- **Primary distribution levers**:
  - **Conversation depth (especially author replies)**: Replies—and specifically back-and-forth exchanges where the author replies back—carry heavy algorithmic weight.
  - **Bookmarks & reposts/quote-posts**: Bookmarks signal high perceived value even when readers stay silent; quote-posts bridge into new audiences.
  - **Media & dwell time**: Native images, concise videos, and clean multi-tweet threads keep users on-platform longer.
  - **External link trade-off**: Outbound URLs in the root post frequently receive lower feed distribution; placing links in the **first reply** (or publishing native X Articles / long posts for Premium accounts) typically preserves root reach.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Standard posts `<= 280` weighted chars (`t.co` URL = 23 chars; CJK/emoji = 2 weights); up to 4 images (`<= 5MB`, GIF `<= 15MB`) or 1 native video (`<= 140s` standard / longer for Premium). Multi-tweet threads separate posts with `\n---\n` or `meta.threads[]`. Premium long posts set `options.long_post: true` to bypass the 280-char check in `check_media_specs.py`.
- **Style spectrum (not one voice)**: Crisp single-sentence observations, breaking news synthesis, visual data/diagram cards (`../shortform-social/scripts/card_deck.py`), behind-the-scenes build logs, humorous takes, curated threads, and native X Articles.
- **Tags**: Native prose reads cleaner than hashtag stuffing; 0–2 topical tags at most (or none when keywords appear naturally in text).

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py`. Default path: `https://x.com/compose/post` (supports drafts, scheduling, Premium long posts, X Articles). Optional OpenAPI: `scripts/client.py` (`X_ACCESS_TOKEN`; note v2 API tier limits on posting/analytics). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Safety**: Avoid repetitive automated replies, mass follow/unfollow churn, or link-only spam blasts (triggers automated reach limits or locks).
- **Rate cap**: Enforce `<= 15/hour`, `<= 80/day` (30–60s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `bookmarkRate`, `replyDepth`, `profileClickRate`, `repostQuoteRatio`, and `engagementRate`.
