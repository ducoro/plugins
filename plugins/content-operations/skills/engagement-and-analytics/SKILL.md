---
name: engagement-and-analytics
description: Triage comments across four intent tiers, enforce anti-spam rate limits, collect 24h/72h/7d/30d metric snapshots, run cross-platform attribution retrospectives, and feed findings back into the topic pool. Use after publishing to handle comments, track performance, or run weekly retros.
---

# Engagement Triage, Analytics & Retrospective Loop

Publishing is the midpoint, not the finish line. Close the loop by turning comments into conversions or future topics, and turning snapshots into next-week strategy adjustments.

## Workflow

### Part A — Engagement Triage & Safe Execution
1. **Pull recent comments** on active works (especially during the first 1–2 hours after publishing) via the target `platform-<name>` API client or browser workflow.
2. **Classify every comment** into the 4 tiers defined in `references/comment-triage.md` (`high_intent`, `feedback`, `general`, `spam`) and write to `engagement/inbox.json` (`{"version": 1, "comments": [...]}`).
3. **Check rate limits before acting** (`references/rate-limit-safety.md`):
   - Count today's executed actions in `engagement/action-log.jsonl` (`executedAt` ISO-8601 UTC).
   - Stop immediately on daily/hourly ceiling or any HTTP `429`/risk-control prompt.
   - Append every executed action (`actionId`, `executedAt`, `platform`, `accountId`, `targetId`, `actionType`, `result`, `error`) to `engagement/action-log.jsonl`.

### Part B — Analytics Snapshots & Weekly Retro
1. **Check due capture windows and aggregate metrics**:
   ```sh
   python3 scripts/aggregate_metrics.py <workspace>/content-ops --days 14
   ```
   Inspect `dueSnapshots` for published works that have crossed **T+24h**, **T+72h**, **T+7d**, or **T+30d** (important for search-compounding platforms like Pinterest/YouTube/Bilibili) and are missing snapshots.
2. **Capture work & account snapshots** into `analytics/snapshots.jsonl`:
   - Work snapshots: `views`, `likes`, `comments`, `shares`, `saves` plus `platformMetrics` (percentages as `0–100` floats, ratios as decimals, durations in `*Sec`).
   - Account snapshots (`window: "account"`): follower delta, profile visits, page follows—tracked in `accountSnapshots` by both `aggregate_metrics.py` and `build_boards.py`.
3. **Write weekly retrospective** (`analytics/retros/YYYY-Www.md`) using `references/retro-attribution.md` (`topWorks`, `bottomWorks`, `crossPlatformTopics` from `aggregate_metrics.py`). Place next-cycle checkboxes strictly under `## Next-Cycle Actions` (parsed into `analytics-retro-board`).
4. **Feed back into `inbox/` and `topics/topics.json`**:
   - Promote recurring comments and retro actions into `inbox/` signals for `../topic-research/SKILL.md` (set `cooldownOverrideReason` if intentionally doubling down within 14 days).
   - Rebuild `engagement-inbox-board` and `analytics-retro-board` via `../content-ops-loop/scripts/build_boards.py`.

## Done When

- Open comments are triaged in `engagement/inbox.json` with zero rate-limit violations and complete `action-log.jsonl` records.
- Due `24h`/`72h`/`7d`/`30d` snapshots are appended to `analytics/snapshots.jsonl`.
- Weekly retros end with `## Next-Cycle Actions` recycled into the next topic cycle.
