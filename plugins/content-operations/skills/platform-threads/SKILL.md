---
name: platform-threads
description: "Neutral Threads platform advisor covering conversational public-reply discovery, Instagram social-graph crossover, 500-char posts and linked chains, single topic-tag mechanics, browser/API delivery, and engagement guardrails."
---

# Threads Platform Expert Guide

Threads is Meta's **conversational text-first social stream** tightly linked to the Instagram social graph, favoring approachable dialogue, quick visual shares, and lively reply threads.

## 1. Audience, Mindset & Distribution Mechanics
- **Culture & tone**: Warmer, more casual and community-driven than hyper-newsy feeds; readers respond strongly to open questions, relatable everyday observations, visual photo carousels, and genuine back-and-forth replies.
- **Distribution levers**: **Reply velocity & conversation length** are the dominant algorithmic signals, alongside **repost/quote** cascades and cross-surfacing inside Instagram's feed.
- **Topic tag (`1` native tag)**: Threads supports a **single native topic tag** per post (not hashtag blocks)—use one clean, specific topic tag that matches an active community conversation.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: `<= 500` chars per post; chain sequential replies with `\n---\n` or `meta.threads[]`; up to **10 images** (`jpg/jpeg/png`, `<= 8MB` each) or 1 video (`<= 5 min`, `<= 1GB`); max **1** native topic tag.
- **Style spectrum**: Open-ended discussion prompts, casual behind-the-scenes snapshots, short photo carousels, quick visual tips (`../shortform-social/scripts/card_deck.py`), humorous observations, and bite-sized multi-post stories.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py`. Default path: `https://www.threads.net/` (supports drafts, polls, scheduling, multi-post chains). Optional OpenAPI: `scripts/client.py` (`THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`; media URLs via `ducoro-cli media upload <path> --json`). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Avoid rage-bait spam, mass automated replies, or cross-posting unadapted link dumps without conversational context.
- **Rate cap**: Enforce `<= 12/hour`, `<= 60/day` (30–60s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `replyToViewRatio`, `conversationDepth`, `repostQuoteCount`, and `followerConversionRate`.
