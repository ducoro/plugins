---
name: topic-research
description: Source raw content signals from five channels, deduplicate against recent topics, score candidates on a 4-dimension rubric, and produce decision-ready topic briefs for Gate 1 approval. Use whenever finding topics, triaging ideas, or feeding retro insights back into the pool.
---

# Topic Research & Selection Engine

Turn noisy signals into high-conviction, evidence-backed topic briefs before spending production effort.

## References (Load as Needed)
- `references/source-channels.md` — 5 sourcing pipelines (`internal_fact`, `platform_trend`, `comment_feedback`, `seasonal_evergreen`, `cross_platform_repurpose`).
- `references/scoring-and-brief.md` — 4-dimension weighted rubric, veto thresholds, cooldown override contract, and brief template.
- `references/festival-calendar.md` — seasonal anchors and lead-day planning windows.

## Workflow

1. **Capture raw signals into `content-ops/inbox/`.**
   - Save each raw batch as `inbox/YYYY-MM-DD-<slug>.md` with source URL/origin, date, verbatim facts, and unverified gaps.
   - When recycling weekly retrospective findings into next cycle's pool, use `sourceType: "cross_platform_repurpose"` (for doubling down on winning formats) or `"internal_fact"` (for hook/packaging experiments), and set `cooldownOverrideReason` if intentionally revisiting a theme within 14 days.
2. **Decompose, merge, and score.**
   - Merge duplicate signals pointing to the same claim while preserving all source refs; assign a stable kebab-case `cooldownKey`.
   - Score `audiencePain`, `evidenceStrength`, `timeliness`, and `brandFit` (`1`–`5`) per `references/scoring-and-brief.md`, then run:
     ```sh
     python3 scripts/score_topics.py <workspace>/content-ops --cooldown-days 14
     ```
   - `score_topics.py` checks 14-day cooldown against `topics.json` (`approved`/`produced`), recent `publish-log.jsonl` publishes, and in-batch duplicate `cooldownKey`s, and records `archiveReason` when auto-archiving `< 3.0`.
3. **Pause at Approval Gate 1.**
   - Present shortlisted topics with: target audience & single core claim, verified evidence vs. gaps, planned format per target platform, score breakdown, and cooldown check result.
4. **Write approved Topic Briefs.**
   - Update approved items in `topics/topics.json` (`status: "approved"`, `approvalRef`) and create `topics/briefs/<topic-id>.md` using the brief template in `references/scoring-and-brief.md`.
   - Hand off to `../media-production/SKILL.md` and target `../platform-<name>/SKILL.md` skills, then refresh `pipeline-board`.

## Done When

- Raw signals are logged in `inbox/` with verifiable sources.
- `topics/topics.json` is scored and cooldown-checked via `score_topics.py`.
- Approved topics have complete briefs under `topics/briefs/<topic-id>.md` with zero unflagged fact gaps.
