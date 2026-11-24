# Topic Scoring Rubric, Cooldown & Brief Contract

Neutral reference for prioritizing topics. Default weights are a starting baseline—override them via `score_topics.py --weights` and `--shortlist-min` to match the creator's strategy (for example, higher `timeliness` for news channels or higher `audiencePain` for evergreen tutorials).

## Default 4-Dimension Rubric (1–5 each)

`weightedScore = audiencePain * 0.35 + evidenceStrength * 0.30 + timeliness * 0.15 + brandFit * 0.20`

- **5**: Strong, concrete signal (urgent recurring audience question / primary evidence ready / live window / core brand pillar).
- **3**: Moderate signal (nice-to-know / partial proof / evergreen / adjacent topic).
- **1**: Weak or misaligned (unrelated / speculative / missed window / violates `brand-profile.md`).

### Thresholds & Cooldown
- Default `>= 3.80` -> `shortlisted` for Gate 1 review (`evidenceStrength <= 2` or `brandFit <= 2` caps at `candidate`).
- Candidates below shortlist stay in `candidate` backlog unless `--auto-archive-below` is explicitly passed.
- **Cooldown & fuzzy repeats**: `score_topics.py` checks `cooldownKey` against `--cooldown-days` (default 14 days; set `cooldownOverrideReason` for intentional sequels) and annotates fuzzy title overlap (`>= 0.6`) non-destructively via `repeatAnnotation`.
- **Portfolio balance**: Mix timely news, search/evergreen demand, and audience questions according to the channel's actual goals—there is no universal fixed ratio. Only weight historical winners from `analytics/snapshots.jsonl` once `>= 5` published works exist.

## Approved Topic Brief Template (`topics/briefs/<topic-id>.md`)

```markdown
# Topic Brief: <Title>

- **Topic ID**: <topic-id>
- **Approved By / Ref**: <approval reference>
- **Primary Audience**: <specific role and context>
- **Core Angle**: <one sentence the reader/viewer should remember>
- **Lead Platform**: <primary platform slug>
- **Secondary Platforms**: <comma-separated platform slugs>

## Verified Evidence
- [Fact 1] — Source: `<URL, local file, or citation>`
- [Fact 2] — Source: `<URL, local file, or citation>`

## Boundaries & Open Gaps
- What must NOT be claimed or exaggerated.
- Any missing asset or verification needed before Gate 2.

## Planned Formats by Platform
- `<platform>`: <format, entry hook, visual/media plan>
```
