---
name: platform-x-twitter
description: "Neutral X (Twitter) advisor covering For You/Following mechanics, benchmark-account radar & outbound replies/quotes, profile funnel, single posts/threads/firstReply/Premium long posts/Articles, 1200x675 cards, browser/API delivery, and rate caps."
---

# X (Twitter) Platform Expert Guide

X is a **real-time public town square and interest graph** where speed, sharp perspective, conversation, and bookmarkable utility drive reach. Always defer to the mounted agent's own context (profile, memory, private skills, Space consensus, `brand-profile.md`) for voice, goals, and concrete targets—never hardcode personas or benchmark handles.

## 1. Distribution & Conversion Mechanics
- **Two feeds**: **Following** (chronological core) and **For You** (algorithmic expansion across interest graphs).
- **Primary levers**:
  - **Early conversation depth (first 30–60 min)**: Author back-and-forth replies carry heavy weight.
  - **Bookmarks & quote-posts**: Bookmarks signal silent utility; quote-posts bridge into adjacent audiences.
  - **Native media & link trade-off**: Use native images, `1200×675` cards (`../shortform-social/scripts/card_deck.py scaffold <dir> --preset x-card`), concise video, or threads. Root outbound links often reduce `For You` reach—place links in `options.firstReply` (validated by `check_media_specs.py`) or publish Premium long posts / X Articles.
- **Profile funnel (`Post → Profile → Bio + Pinned Post → Follow`)**: Review `profileClickRate` alongside whether Bio and pinned post match current positioning.

## 2. Benchmark Radar & Outbound Engagement
- High-signal replies/quote-posts under active niche peers drive early discovery.
- **Human-approved targets only (`engagement/benchmark-accounts.json`)**: If context lacks targets, propose candidates as `"status": "proposed"` for human confirmation (`"active"` requires `approvedBy`, enforced by `validate_workspace.py`). Poll via browser, X MCP connector, or `scripts/client.py user-tweets`.
- Stage drafted replies/quotes in `engagement/outbound-queue.json` (reviewed on `engagement-inbox-board` **Benchmark Radar** tab); inbound and outbound share one budget in `engagement_guard.py`.

## 3. Formats & Delivery (`references/specs.json`, `references/protocol.md`)
- **Specs**: `<= 280` weighted chars (`t.co` = 23; CJK/emoji = 2); `<= 4` images (`<= 5MB`, GIF `<= 15MB`) or 1 video (`<= 140s` standard); never mix image+video. Threads split by `\n---\n` or `meta.threads[]`; follow-up link/CTA in `options.firstReply`; Premium long posts set `options.long_post: true`. For **X Articles**, set `mode: "article"` with a non-empty `title`, **5:2** top banner (`2000×800` recommended), and up to 25 inline images (`https://x.com/compose/articles`; see `references/protocol.md`). Use 0–2 topical tags at most.
- **Channels**: Follow `../content-ops-loop/references/channel-access-matrix.md` (Connectors → optional `scripts/client.py` for posts/threads/engagement → universal Browser / Computer Use fallback for `https://x.com/compose/post`, X Articles, and feeds). Run `check_media_specs.py` and `validate_workspace.py --verify-slot <slotId>` before publishing.

## 4. Red Lines & North-Star Metrics (`platformMetrics`)
- Avoid repetitive automated replies, follow/unfollow churn, or link blasts. Enforce shared cap `<= 15/hour`, `<= 80/day` (30–60s spacing) via `engagement_guard.py`.
- Track `bookmarkRate`, `replyDepth`, `profileClickRate`, `repostQuoteRatio`, and `engagementRate`.
