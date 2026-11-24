---
name: platform-facebook
description: "Neutral Facebook Page platform advisor covering community/group discussion dynamics, Reels + photo-album + long-caption formats, Meta Business Suite vs Graph API delivery, compliance guardrails, and share/reach analytics."
---

# Facebook Page Platform Expert Guide

Facebook combines **local & interest-based communities (Pages + Groups)** with **algorithmic discovery** (Reels, shareable visual posts, and discussion-sparking stories) across a broad, global, multi-generational audience.

## 1. Audience, Mindset & Distribution Mechanics
- **Audience breadth**: Skews broader and older globally than TikTok/Threads, with strong engagement in local services, family/parenting, hobbies, community news, education, small business, and niche interest Groups.
- **Distribution levers**: **Shares to personal feeds/Messenger/Groups** and **genuine comment threads** drive organic Page reach. Native Reels tap into non-follower discovery, while photo albums and candid stories perform well with existing followers and Groups.
- **Link trade-off**: External link preview posts often see lower organic reach than native photo/video/text posts; consider native visual storytelling with the link placed naturally in the caption or first comment when optimizing for reach vs. direct click-through.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Text up to `63,206` chars (keep opening hook crisp before "See more"); up to 10 images (`<= 10MB` each); native video (`MP4/MOV/AVI`, `<= 1GB`, `<= 60 min`; `9:16` for Reels, `1:1`/`4:5`/`16:9` for Feed); inline hashtags supported (`recommendations.maxTopicCount: 5`).
- **Style spectrum**: Community discussions & Q&As, photo stories & event recaps, practical tips & carousels (`../shortform-social/scripts/card_deck.py`), short vertical Reels (`../video-production/SKILL.md`), and local/brand announcements.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py`. Default path: Meta Business Suite (`https://business.facebook.com/`, supports scheduling, Reels, cross-posting with Instagram, and inbox management). Optional OpenAPI: `scripts/client.py` (`FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Avoid explicit engagement-bait ("Like if you agree, Share if you love X"), misleading health/financial claims, and undisclosed branded partnerships (use Meta Branded Content tags when paid).
- **Rate cap**: Enforce `<= 12/hour`, `<= 60/day` (30–60s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `shareRate`, `meaningfulCommentCount`, `video3sRetention`, `reachToFollowerRatio`, and `linkClickThroughRate`.
