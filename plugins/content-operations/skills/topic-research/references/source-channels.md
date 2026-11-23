# Five Topic Sourcing Channels

Treat sourcing as a repeatable intake pipeline, not brainstorming from a blank page.

## 1. Internal First-Party Facts (`internal_fact`)
Highest signal-to-noise ratio because competitors cannot copy your lived data.
- **Where to look**: recent changelogs, git commits/PRs, shipping demos, internal postmortems, customer onboarding friction, pricing/policy updates, real before/after benchmarks.
- **Extraction rule**: record the exact verified fact, date, and artifact link (screenshot, doc, or repo ref) before framing any marketing hook.

## 2. Platform Trends & Peer Benchmarks (`platform_trend`)
Captures existing audience demand and live vocabulary.
- **Where to look**: search autocomplete on the target platform, hot topic boards, high-save/high-comment peer posts from the past 7–30 days, and recurring debates in niche communities.
- **Peer teardown checklist** (never plagiarize; extract structure only):
  - What specific promise did the first 3 seconds or cover headline make?
  - Which comments disagreed, asked follow-ups, or said "saved for later"?
  - What missing angle or stronger proof can we bring from our own experience?

## 3. Comment & Support Feedback Loop (`comment_feedback`)
Turns yesterday's distribution into tomorrow's guaranteed-demand topics.
- **Where to look**: `engagement/inbox.json` items tagged `high_intent`, `feedback`, or `topicCandidate: true`.
- **Promotion trigger**: any question asked 2+ times, or any sharp objection/misconception that exposes a real gap in how the market understands our subject.

## 4. Seasonal & Evergreen Anchors (`seasonal_evergreen`)
Eliminates empty-calendar panic.
- Maintain 10–20 evergreen pillar questions (core buyer mistakes, step-by-step checklists, comparison frameworks) ready to fill quiet weeks.
- Check `references/festival-calendar.md` weekly and promote relevant seasonal topics 7–14 days before the anchor date.

## 5. Cross-Platform Repurposing (`cross_platform_repurpose`)
Multiplies ROI on proven ideas.
- Take any post in `analytics/snapshots.jsonl` that beat the account median engagement rate by 1.5x+ on Platform A and propose a native rebuild for Platform B.
- When adapting an external long-form video/article URL, capture metadata (title, key timestamps/claims, source link) into `inbox/` and transform the angle—never repost raw scraped content without permission or original synthesis.
