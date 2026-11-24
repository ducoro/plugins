---
name: platform-linkedin
description: "Neutral LinkedIn platform advisor covering professional network + knowledge-graph distribution, PDF Document Carousels, dwell time and substantive comment weights, link placement trade-offs, browser/API delivery, and engagement guardrails."
---

# LinkedIn Platform Expert Guide

LinkedIn is a **professional identity and knowledge-sharing network** where posts spread first to 1st-degree connections and then extend into 2nd/3rd-degree feeds based on **dwell time** and **substantive discussion**.

## 1. Audience, Mindset & Distribution Mechanics
- **Who is here**: Professionals, founders, operators, recruiters, engineers, designers, marketers, and B2B buyers reading during workdays (mobile commute + desktop breaks).
- **Distribution levers**:
  - **"See more" expansion & dwell time**: Only the first ~2–3 lines (~210 chars) appear above the fold. Clean opening lines earn expansion; **PDF Document Carousels (`mode: "document"`)** generate the highest average dwell time as readers swipe slide by slide.
  - **Meaningful comments & author replies**: Multi-sentence comments from relevant peers outperform passive likes; timely author replies extend feed lifespan across 24–72 hours.
  - **Outbound link trade-off**: External URLs in the post body can trim initial reach; weigh direct convenience against placing the link in the first comment or editing it in after initial momentum.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Body `<= 3000` chars; `text`, `image_text` (up to 9 images), `video` (`MP4 <= 10 min`, `<= 200MB`), and **`document`** (1 PDF carousel `<= 100MB`, `1080x1350` `4:5` or `1080x1080` slides exported via headless Chrome print-to-PDF from `../shortform-social/scripts/card_deck.py`); inline hashtags supported (`recommendations.maxTopicCount: 5`).
- **Style spectrum**: Practitioner case studies, industry analysis, career/leadership reflections, visual PDF frameworks, company/product milestones, hiring stories, and candid lessons learned. Avoid cringe engagement-bait ("Agree? Comment YES!").

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared browser / OpenAPI / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Validate via `check_media_specs.py` (supports `document` PDF validation). Default path: `https://www.linkedin.com/feed/` (native scheduling, PDF carousel upload, polls, Newsletters/Articles). Optional OpenAPI: `scripts/client.py` (`LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN`). Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`) before publishing.

## 4. Platform Red Lines & Engagement
- **Compliance**: Avoid engagement-pod manipulation, automated connection-request spam, and undisclosed sponsored endorsements; protect client/employer confidentiality.
- **Rate cap**: Enforce `<= 6/hour`, `<= 40/day` (90–180s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `dwellExpandRate`, `substantiveCommentCount`, `repostWithThoughtsCount`, `profileViews`, and `inboundDmOrLeadCount`.
