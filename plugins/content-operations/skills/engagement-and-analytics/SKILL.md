---
name: engagement-and-analytics
description: Triage comments across four intent tiers, enforce deterministic anti-spam rate caps and idempotency via engagement_guard.py, collect 24h/72h/7d/30d metric snapshots, run platform-native retrospectives, and feed findings back into topics.
---

# Engagement Triage, Analytics & Retrospective Loop

Publishing is the midpoint, not the finish line. Close the loop by turning audience comments into relationships or future topics, and turning real platform metrics into next-cycle adjustments.

## Workflow

### Part A — Engagement Triage & Deterministic Rate-Limit Guard
1. **Pull recent comments** on active works (early replies in the first 1–2 hours boost distribution on most feed platforms) via the target `platform-<name>` API client or browser workflow.
2. **Classify every comment** into the 4 tiers in `references/comment-triage.md` (`high_intent`, `feedback`, `general`, `spam`) and write to `engagement/inbox.json` (`{"version": 1, "comments": [...]}`).
3. **Enforce budget & idempotency in code (`scripts/engagement_guard.py`) before acting**:
   ```sh
   python3 scripts/engagement_guard.py check-budget <workspace> --platform <plat> --account-id <acct>
   python3 scripts/engagement_guard.py check-idempotent <workspace> --platform <plat> --account-id <acct> --target-id <id> --action-type reply
   ```
   - After executing (or failing), log atomically via:
     ```sh
     python3 scripts/engagement_guard.py record-action <workspace> --platform <plat> --account-id <acct> --target-id <id> --action-type reply --result ok --summary "..."
     ```
   - Caps match `references/rate-limit-safety.md`. Halt immediately on HTTP `429`, CAPTCHA, or risk-control prompt—never bypass anti-bot challenges.

### Part B — Analytics Snapshots & Platform-Native Retro
1. **Check due capture windows and aggregate metrics**:
   ```sh
   python3 scripts/aggregate_metrics.py <workspace>/content-ops --days 14
   ```
   Inspect `dueSnapshots` for published works crossing **T+24h**, **T+72h**, **T+7d**, or **T+30d** (essential for search-compounding platforms like Pinterest, YouTube, Bilibili, Xiaohongshu, and WeChat Search).
2. **Append work & account snapshots** into `analytics/snapshots.jsonl` (UTC ISO-8601 `capturedAt`, non-negative `metrics`, plus platform-native `platformMetrics`).
3. **Write weekly retrospective** (`analytics/retros/YYYY-Www.md`) using `references/retro-attribution.md` paired with each platform's own north-star metrics in `../platform-<name>/SKILL.md` (e.g., WeChat open/finish/share rates, XHS cover CTR & CES saves/comments, short-video 3s retention & completion rate, YouTube Browse/Suggested CTR & AVD, X bookmarks & author-thread replies). Place next-cycle checkboxes under `## Next-Cycle Actions`.
4. **Recycle insights** into `inbox/` and `topics/topics.json`, then rebuild boards via `../content-ops-loop/scripts/build_boards.py`.

## Done When
- Open comments are triaged in `engagement/inbox.json` with zero rate-limit/idempotency violations verified by `engagement_guard.py`.
- Due `24h`/`72h`/`7d`/`30d` snapshots are appended to `analytics/snapshots.jsonl`.
- Weekly retro ends with `## Next-Cycle Actions` fed into the next cycle.
