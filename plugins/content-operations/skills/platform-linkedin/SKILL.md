---
name: platform-linkedin
description: "Neutral LinkedIn advisor covering professional-graph distribution, PDF Document Carousels, benchmark-account radar & substantive outbound comments, options.firstReply link placement, profile funnel, browser/API delivery, and rate caps."
---

# LinkedIn Platform Expert Guide

LinkedIn is a **professional identity and knowledge-sharing network** where posts spread first to 1st-degree connections and then extend into 2nd/3rd-degree feeds based on **dwell time** and **substantive discussion**. Always defer to the mounted agent's own context (profile, memory, private skills, Space consensus, `brand-profile.md`) for voice, goals, and concrete targets—never hardcode personas or benchmark accounts.

## 1. Distribution & Conversion Mechanics
- **Dwell time & "See more" expansion**: Only the first ~2–3 lines (~210 chars) show above the fold. **PDF Document Carousels (`mode: "document"`)** drive top dwell time slide by slide.
- **Substantive comments & author replies**: Multi-sentence comments from relevant peers outperform passive likes; timely author replies extend feed lifespan across 24–72 hours.
- **Outbound link trade-off**: External URLs in the post body often trim initial reach; place links in `options.firstReply` (validated by `check_media_specs.py`) and attach via `scripts/client.py post-with-first-reply --variant <variants/linkedin.md>` or browser first comment.
- **Profile funnel (`Post → Profile → Headline + Featured → Follow/Lead`)**: Track `profileViews` and `inboundDmOrLeadCount` alongside whether headline and Featured items match current positioning.

## 2. Benchmark Radar & Outbound Engagement
- Thoughtful, substantive comments on relevant peer/decision-maker posts are a major organic reach lever on LinkedIn.
- **Human-approved targets only (`engagement/benchmark-accounts.json`)**: Propose candidate accounts as `"status": "proposed"` for human confirmation (`"active"` requires `approvedBy`, enforced by `validate_workspace.py`). Stage drafted outbound comments in `engagement/outbound-queue.json` (reviewed on `engagement-inbox-board` **Benchmark Radar** tab); inbound and outbound share one rate-limit budget via `engagement_guard.py`.

## 3. Formats & Delivery (`references/specs.json`, `references/protocol.md`)
- **Specs**: Body `<= 3000` chars; `text`, `image_text` (up to 9 images), `video` (`MP4 <= 10 min`, `<= 200MB`), and **`document`** (1 PDF carousel `<= 100MB`, `1080x1350` `4:5` via `../shortform-social/scripts/card_deck.py scaffold <dir> --preset linkedin-pdf` + `ducoro-cli render pdf`). Put follow-up links/CTAs in `options.firstReply`. Avoid engagement-bait ("Agree? Comment YES!").
- **Channels**: Default `https://www.linkedin.com/feed/` (supports scheduling, PDF carousels, polls, Newsletters/Articles). Optional OpenAPI: `scripts/client.py` (`LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN`; `post-with-first-reply --variant` publishes and attaches the first comment with partial-failure resume). Run `check_media_specs.py` and `validate_workspace.py --verify-slot <slotId>` before publishing.

## 4. Red Lines & North-Star Metrics (`platformMetrics`)
- Avoid engagement pods, automated connection spam, and undisclosed endorsements; protect client/employer confidentiality. Enforce shared cap `<= 6/hour`, `<= 40/day` (90–180s spacing) via `engagement_guard.py`.
- Track `dwellExpandRate`, `substantiveCommentCount`, `repostWithThoughtsCount`, `profileViews`, and `inboundDmOrLeadCount`. Check an active Ducoro `linkedin` Connector (`ducoro-cli mcp catalog status linkedin` / `tools linkedin`) first for publishing, comments, and Organization Page statistics; fall back to `scripts/client.py org-analytics` / `post-analytics --workspace <content-ops>` or LinkedIn browser analytics as needed.
