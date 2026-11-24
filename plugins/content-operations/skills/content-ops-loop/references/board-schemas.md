# Board Data Schemas

`scripts/build_boards.py` aggregates `content-ops/` files into `assets/data.json` for each of the 5 boards. By default, routine updates write **only `assets/data.json`** (preserving in-place `ducoro.board.revalidate` without full reload); pass `--embed-inline` when exporting a standalone offline HTML snapshot.

## Common Envelope

```json
{
  "schemaVersion": 1,
  "board": "calendar-board",
  "generatedAt": "2026-01-16T08:00:00Z",
  "timezone": "Asia/Shanghai",
  "platforms": ["xiaohongshu", "douyin", "x-twitter"],
  "summary": {}
}
```

## Per-Board Payload Contracts

1. **`calendar-board`**
   - `summary`: `{ totalSlots, awaitingApproval, approved, published, failed }`
   - `slots`: entries from `calendar.json` enriched with `publicUrl`, `workId`, and `lastError` from `publish-log.jsonl`.
   - `festivals`: seasonal anchors `{ id, date, name, region, leadDays }`.
2. **`pipeline-board`**
   - `summary`: `{ inboxCount, candidateTopics, approvedItems, draftsReady, specAlertCount }`
   - `plans`: list from `drafts/plans.json`.
   - `columns`: `{ intake, approved, ready, archive }` combining `topics.json` and `drafts/*/meta.json` with per-platform `specAlerts`.
3. **`publish-ledger-board`**
   - `summary`: `{ totalAccounts, healthyAccounts, attentionAccounts, totalPublished, totalFailed }`
   - `accounts`: sanitized accounts from `accounts.json` (no raw secrets).
   - `records`: reverse-chronological entries from `publish-log.jsonl`.
4. **`engagement-inbox-board`**
   - `summary`: `{ openTotal, highIntent, feedback, general, spam, awaitingApproval, activeBenchmarks, proposedBenchmarks, outboundOpen, outboundAwaitingApproval }`
   - `rateLimits`: per-platform `{ platform, usedToday, dailyCap }` computed from `engagement/action-log.jsonl` (`executedAt`, covering both inbound and outbound actions).
   - `comments`: items from `engagement/inbox.json`.
   - `benchmarkAccounts`: human-approved / proposed benchmark accounts from `engagement/benchmark-accounts.json`.
   - `outboundQueue`: drafted outbound replies and quote-posts from `engagement/outbound-queue.json`.
5. **`analytics-retro-board`**
   - `summary`: `{ totalWorks, totalViews, totalLikes, totalComments, totalShares, totalSaves, avgEngagementRate }`
   - `trend` & `trendByPlatform`: per-platform deduplicated daily series `{ date, views, interactions, engagementRate }`.
   - `crossPlatform`: same-`topicId` comparison across 2+ platforms.
   - `works`: latest snapshot per `workId`, including `platformMetrics`.
   - `accountSnapshots`: latest `window: "account"` snapshots per account.
   - `retro`: `{ file, title, actions }` parsed strictly from the `## Next-Cycle Actions` section of the latest `analytics/retros/*.md`.
