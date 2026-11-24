---
name: platform-threads
description: "Neutral Threads advisor covering conversational reply discovery, Instagram graph crossover, benchmark-account radar & outbound replies/quotes, 500-char posts and linked chains (post-thread), single topic tag, browser/API delivery, and rate caps."
---

# Threads Platform Expert Guide

Threads is Meta's **conversational text-first social stream** tightly linked to the Instagram social graph, favoring approachable dialogue, quick visual shares, and lively reply threads. Always defer to the mounted agent's own context (profile, memory, private skills, Space consensus, `brand-profile.md`) for voice, goals, and concrete targets—never hardcode personas or benchmark accounts.

## 1. Distribution & Conversation Mechanics
- **Culture & tone**: Warmer and more community-driven than hyper-newsy feeds; readers respond strongly to open questions, relatable observations, visual photo carousels, and genuine back-and-forth replies.
- **Primary levers**: **Reply velocity & conversation depth** dominate ranking alongside repost/quote cascades and cross-surfacing inside Instagram's feed.
- **Topic tag (`1` native tag)**: Threads supports a **single native `topic_tag`** per root post—pick one specific active community tag rather than hashtag blocks.

## 2. Benchmark Radar & Outbound Engagement
- Participating early with genuine, value-add replies or quote-posts in active niche conversations drives discovery far faster than posting in isolation.
- **Human-approved targets only (`engagement/benchmark-accounts.json`)**: Propose candidates as `"status": "proposed"` for human confirmation (`"active"` requires `approvedBy`, enforced by `validate_workspace.py`). Stage outbound replies/quotes in `engagement/outbound-queue.json` (reviewed on `engagement-inbox-board` **Benchmark Radar** tab); inbound and outbound share one budget via `engagement_guard.py`.

## 3. Formats & Delivery (`references/specs.json`, `references/protocol.md`)
- **Specs**: `<= 500` chars per post; split multi-post chains with `\n---\n` or `meta.threads[]`; optional follow-up CTA/link in `options.firstReply`; up to **10 images** (`jpg/jpeg/png`, `<= 8MB`) or 1 video (`<= 5 min`, `<= 1GB`); max **1** native topic tag.
- **Channels**: Default `https://www.threads.net/` (supports drafts, polls, scheduling, multi-post chains). Optional OpenAPI: `scripts/client.py` (`THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`; `post-thread --variant <variants/threads.md>` chains two-step container creation/publishing via `reply_to_id` with partial-failure resume; media URLs via `ducoro-cli media upload <path> --json`). Run `check_media_specs.py` and `validate_workspace.py --verify-slot <slotId>` before publishing.

## 4. Red Lines & North-Star Metrics (`platformMetrics`)
- Avoid rage-bait spam, mass automated replies, or unadapted link dumps. Enforce shared cap `<= 12/hour`, `<= 60/day` (30–60s spacing) via `engagement_guard.py`.
- Track `replyToViewRatio`, `conversationDepth`, `repostQuoteCount`, and `followerConversionRate`.
