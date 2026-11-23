# Four-Dimension Scoring Rubric & Topic Brief Contract

## Scoring Rubric (1–5 per dimension)

`weightedScore = audiencePain * 0.35 + evidenceStrength * 0.30 + timeliness * 0.15 + brandFit * 0.20`

| Score | `audiencePain` (35%) | `evidenceStrength` (30%) | `timeliness` (15%) | `brandFit` (20%) |
| --- | --- | --- | --- | --- |
| **5** | Active, expensive pain users search/ask about weekly | First-hand data, demo, or verifiable artifact ready | Live trend window or shipping this week | Directly reinforces core positioning |
| **4** | Clear recurring frustration | Solid case study or multiple credible sources | Relevant this month or upcoming holiday | Strong thematic alignment |
| **3** | Useful nice-to-know | Partial proof; 1–2 facts need verification | Evergreen, no urgency | Adjacent topic |
| **2** | Vague or over-saturated advice | Mostly opinion, weak proof | Stale trend | Tangential |
| **1** | Unrelated to target reader | Speculative / unverified | Missed window | Off-brand or violates `brand-profile.md` |

### Decision Thresholds
- **`>= 3.80` → `shortlisted`**: surface at Approval Gate 1.
- **`3.00 – 3.79` → `candidate`**: keep in backlog; revisit when stronger proof or a timely trigger appears.
- **`< 3.00` → `archived`**: drop with a one-line reason so the same weak idea is not re-pitched.
- **Hard veto**: if `evidenceStrength <= 2` or `brandFit <= 2`, cap status at `candidate` regardless of total score until proof or framing is fixed.

## Cooldown, Portfolio Mix & Demand-Window Rules
- **Recommended 10-topic batch mix**: **5–6 live trend topics** (`fetch_hotspots_cn.py` / `web_search`), **2–3 high-frequency demand topics** (platform-specific density such as `../platform-wechat-official/scripts/search_wechat_articles.py` when targeting WeChat), and **2–3 evergreen topics** (`seo_keywords_cn.py` + `brand-profile.md` pillars). Reallocate shares if a feed is unavailable.
- **High-frequency demand window & 3-part teardown**:
  - Each high-frequency candidate must note: **Demand Core** (what reader tension it solves), **Form Logic** (title/structure pattern), and **Supply Gap** (missing depth, outdated examples, or wrong audience).
  - **Rising window (1–3 days)**: following the same demand angle with your own verified evidence is valid.
  - **Saturated window (multi-day flood)**: require a clear differentiated angle (counter-evidence, deeper teardown, or narrower audience); copycat angles cap `audiencePain` / `timeliness` at `2`.
- **Graduated cooldown & retro feedback**:
  - Assign every topic a normalized `cooldownKey` (kebab-case theme slug). Within **7 days**: strong conflict (skip or require explicit sequel/counter-argument override); **7–30 days**: light conflict (narrow angle required); **>30 days**: clear.
  - Only apply historical framework/title weighting from `analytics/snapshots.jsonl` once **>= 5 published works** have recorded metrics so small samples never distort topic selection.

## Approved Topic Brief Template (`topics/briefs/<topic-id>.md`)

```markdown
# Topic Brief: <Title>

- **Topic ID**: <topic-id>
- **Approved By / Ref**: <approval reference>
- **Primary Audience**: <specific role and context>
- **Core Single Claim**: <one sentence the reader must remember>
- **Lead Platform**: <primary platform slug>
- **Secondary Platforms**: <comma-separated platform slugs>

## Verified Evidence
- [Fact 1] — Source: `<inbox/... or URL>`
- [Fact 2] — Source: `<inbox/... or URL>`

## Open Gaps / Boundaries
- What must NOT be claimed or exaggerated.
- Any remaining fact or visual asset required before Gate 2.

## Planned Formats by Platform
- `<platform-a>`: <format, hook angle, CTA>
- `<platform-b>`: <format, hook angle, CTA>
```
