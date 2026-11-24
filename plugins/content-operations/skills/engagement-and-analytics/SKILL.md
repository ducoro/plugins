---
name: engagement-and-analytics
description: Triage comments across four intent tiers, enforce deterministic anti-spam rate caps and idempotency via engagement_guard.py, collect 24h/72h/7d/30d metric snapshots, run platform-native retrospectives, and feed findings back into topics.
---

# Engagement Triage, Analytics & Retrospective Loop

Publishing is the midpoint, not the finish line. Close the loop by turning audience comments into relationships or future topics, and turning real platform metrics into next-cycle adjustments.

## Workflow

### Part A — Engagement Triage & Deterministic Rate-Limit Guard
1. **Pull recent comments & benchmark activity (Connector-first)**: First check whether an active Ducoro Connector covers the platform (`ducoro-cli mcp catalog status <slug> --json` / `tools <slug> --json`) to fetch comments or post approved replies directly; otherwise fall back to the target `platform-<name>` `scripts/client.py` or official browser workflow. Early replies in the first 1–2 hours boost distribution on most feed platforms. For platforms where outbound conversation drives discovery (e.g., X/Twitter), optionally monitor **human-approved** targets in `engagement/benchmark-accounts.json` (`status: "active"`, `approvedBy` set) and stage value-add replies/quote-posts in `engagement/outbound-queue.json` (never silently activate benchmark accounts—stage `proposed` rows for human approval on `engagement-inbox-board`).
2. **Classify every inbound comment** into the 4 tiers in `references/comment-triage.md` (`high_intent`, `feedback`, `general`, `spam`) and write to `engagement/inbox.json` (`{"version": 1, "comments": [...]}`).
3. **Enforce shared budget & idempotency in code (`scripts/engagement_guard.py`) before any inbound OR outbound action**:
   ```sh
   python3 scripts/engagement_guard.py check-budget <workspace> --platform <plat> --account-id <acct>
   python3 scripts/engagement_guard.py check-idempotent <workspace> --platform <plat> --account-id <acct> --target-id <id> --action-type reply
   ```
   - After executing (or failing), log atomically via:
     ```sh
     python3 scripts/engagement_guard.py record-action <workspace> --platform <plat> --account-id <acct> --target-id <id> --action-type reply --result ok --summary "..."
     ```
   - Caps match `references/rate-limit-safety.md`. Halt immediately on HTTP `429`, CAPTCHA, or risk-control prompt—never bypass anti-bot challenges.

### Part B — Analytics Snapshots, Breakout Amplification & Platform-Native Retro
1. **Check due capture windows, breakout works, and top historical hooks**:
   ```sh
   python3 scripts/aggregate_metrics.py <workspace>/content-ops --days 14
   ```
   - Inspect `dueSnapshots` for published works crossing **T+24h**, **T+72h**, **T+7d**, or **T+30d** (essential for search-compounding platforms like Pinterest, YouTube, Bilibili, Xiaohongshu, and WeChat Search).
   - Inspect `breakoutCandidates` (recently published works outperforming platform median or custom thresholds in `engagement/breakout-rules.json`). To queue human-approved follow-up amplification (`reply` value-add plug or `repost` boost) idempotently into `engagement/outbound-queue.json` (surfaced on `engagement-inbox-board`), run:
     ```sh
     python3 scripts/aggregate_metrics.py <workspace>/content-ops --days 14 --stage-breakouts
     ```
     Never auto-publish breakout replies or reposts—draft copy using the mounted agent's context, obtain explicit human approval, and enforce `engagement_guard.py` budget & idempotency before execution.
   - Inspect `topHooks` (automatically extracted from this workspace's top-performing drafts) and share as creative inspiration before drafting new openings in `shortform-social` or `longform-writing`.
2. **Append work & account snapshots** into `analytics/snapshots.jsonl` (UTC ISO-8601 `capturedAt`, non-negative `metrics`, plus platform-native `platformMetrics`). Prefer an active Ducoro Connector tool if it returns the required metrics; otherwise pull via `platform-<name>/scripts/client.py` (e.g., YouTube `channel-analytics`/`video-analytics`, LinkedIn `org-analytics`/`post-analytics`) or record from official Studio dashboards.
3. **Write weekly retrospective** (`analytics/retros/YYYY-Www.md`) using `references/retro-attribution.md` paired with each platform's own north-star metrics in `../platform-<name>/SKILL.md` (e.g., WeChat open/finish/share rates, XHS cover CTR & CES saves/comments, short-video 3s retention & completion rate, YouTube Browse/Suggested CTR & AVD, X bookmarks & author-thread replies). Place next-cycle checkboxes under `## Next-Cycle Actions`.
4. **Recycle insights** into `inbox/` and `topics/topics.json`, then rebuild boards via `../content-ops-loop/scripts/build_boards.py`.

## Done When
- Open comments are triaged in `engagement/inbox.json` with zero rate-limit/idempotency violations verified by `engagement_guard.py`.
- Due `24h`/`72h`/`7d`/`30d` snapshots are appended to `analytics/snapshots.jsonl`.
- Weekly retro ends with `## Next-Cycle Actions` fed into the next cycle.
