# Workspace Schema

The file-backed `content-ops/` directory is the single source of truth across sessions and split workspaces.

## Directory Layout

```text
content-ops/
├── brand-profile.md          # Positioning, audience, tone, persona, non-negotiable facts, standing approvals
├── style/                    # Optional voice, corpus, exemplar & custom theme state
│   ├── style-profile.json    # Publication voice, persona, default theme, taboo words (init via build_playbook.py)
│   ├── corpus/               # Historical user-authored articles (.md/.txt) for cold-start playbook extraction
│   ├── lessons.json          # Recorded AI-draft vs human-final edit patterns with occurrence counts
│   ├── style-playbook.md     # Promoted standing rules (occurrences >= 2 or human-confirmed) + advisory candidates
│   ├── exemplars.json        # Structural & pacing fingerprints extracted from admired reference articles
│   └── themes/*.json         # Custom WeChat themes learned via learn_theme.py (loaded automatically via --workspace)
├── accounts.json             # Account registry (no secrets—env var names only)
├── inbox/                    # Raw source signals (YYYY-MM-DD-<slug>.md)
├── topics/
│   ├── topics.json           # Scored topic pool and lifecycle state
│   └── briefs/<topic-id>.md  # Approved topic briefs (after Gate 1)
├── drafts/
│   ├── plans.json            # Campaign / series folders (Plan grouping)
│   └── <draft-id>/
│       ├── meta.json         # Status, topicId, planId, per-platform variant state & spec checks
│       ├── master.md         # Fact-checked canonical narrative and claims with sources
│       ├── variants/         # Native per-platform drafts (<platform>.md or <platform>.json)
│       └── assets/           # Local images, covers, videos, captions
├── calendar.json             # Scheduled slots across all platforms
├── publish-log.jsonl         # Append-only ledger of real publish attempts and live URLs
├── engagement/
│   ├── inbox.json            # Triaged comment items (high_intent, feedback, general, spam)
│   └── action-log.jsonl      # Append-only executed engagement actions (for rate limits & audit)
├── analytics/
│   ├── snapshots.jsonl       # Append-only 24h/72h/7d work & account metric snapshots
│   └── retros/YYYY-Www.md    # Weekly attribution retrospectives and next-cycle actions
└── boards/                   # Self-contained board folders copied from assets/boards/
    ├── calendar-board/
    ├── pipeline-board/
    ├── publish-ledger-board/
    ├── engagement-inbox-board/
    └── analytics-retro-board/
```

## Core JSON Contracts

### `accounts.json`
```json
{
  "version": 1,
  "accounts": [
    {
      "accountId": "acct-x-main",
      "platform": "x-twitter",
      "handle": "@example",
      "displayName": "Example Official",
      "authType": "oauth2",
      "status": "active",
      "followers": 12400,
      "envKeys": ["X_ACCESS_TOKEN"],
      "lastVerifiedAt": "2026-01-15T08:00:00Z",
      "notes": "Primary English product voice"
    },
    {
      "accountId": "acct-xhs-main",
      "platform": "xiaohongshu",
      "handle": "example_xhs",
      "displayName": "Example XHS",
      "authType": "browser_session",
      "status": "manual_browser",
      "followers": 8200,
      "envKeys": [],
      "lastVerifiedAt": "2026-01-15T08:00:00Z",
      "notes": "Creator Studio browser draft + human confirm"
    }
  ]
}
```
Allowed `authType`: `oauth2`, `browser_session`, `oauth2_or_browser`.
Allowed `status`: `active`, `expiring`, `expired`, `manual_browser`, `paused`.
Browser-only accounts use `"authType": "browser_session"`, `"status": "manual_browser"`, and `"envKeys": []`.

### `topics/topics.json`
```json
{
  "version": 1,
  "topics": [
    {
      "topicId": "top-20260115-01",
      "planId": "plan-launch",
      "title": "Why file-backed content loops outlast one-off prompts",
      "sourceType": "internal_fact",
      "sourceRefs": ["inbox/2026-01-15-release-notes.md"],
      "targetPlatforms": ["x-twitter", "xiaohongshu", "douyin"],
      "scores": {
        "audiencePain": 5,
        "evidenceStrength": 5,
        "timeliness": 4,
        "brandFit": 5
      },
      "weightedScore": 4.8,
      "status": "shortlisted",
      "approvalRef": null,
      "archiveReason": null,
      "cooldownKey": "content-loop-architecture",
      "createdAt": "2026-01-15T09:00:00Z",
      "updatedAt": "2026-01-15T09:00:00Z"
    }
  ]
}
```
Allowed `status`: `candidate`, `shortlisted`, `approved`, `produced`, `archived`.
Allowed `sourceType`: `internal_fact`, `platform_trend`, `comment_feedback`, `seasonal_evergreen`, `cross_platform_repurpose`.

### `drafts/plans.json`
```json
{
  "version": 1,
  "plans": [
    {
      "planId": "plan-launch",
      "name": "Product Launch Series",
      "description": "Feature deep dives and demos",
      "targetPlatforms": ["x-twitter", "xiaohongshu", "youtube"]
    }
  ]
}
```

### `drafts/<draft-id>/meta.json`
```json
{
  "draftId": "drf-20260115-01",
  "topicId": "top-20260115-01",
  "planId": "plan-launch",
  "title": "File-backed content loop walkthrough",
  "status": "ready",
  "variants": {
    "x-twitter": {
      "file": "variants/x-twitter.md",
      "mode": "image_text",
      "specStatus": "pass",
      "publishState": "scheduled",
      "variantHash": "9f86d081884c7d65",
      "issues": []
    }
  },
  "updatedAt": "2026-01-15T12:00:00Z"
}
```
Allowed draft-level `status`: `drafting`, `in_review`, `ready`, `scheduled`, `published`, `needs_update`, `archived`.
Allowed per-variant `publishState`: `unscheduled`, `scheduled`, `draft_saved`, `published`, `failed`.
**`variantHash` rule**: first 16 lowercase hex chars of `sha256` over the UTF-8 bytes of `variants/<platform>.md` (computed automatically by `check_media_specs.py --update-meta`).

### `calendar.json`
```json
{
  "version": 1,
  "timezone": "Asia/Shanghai",
  "slots": [
    {
      "slotId": "slot-20260116-x-01",
      "date": "2026-01-16",
      "time": "12:00",
      "platform": "x-twitter",
      "accountId": "acct-x-main",
      "draftId": "drf-20260115-01",
      "title": "File-backed content loop walkthrough",
      "status": "awaiting_approval",
      "approvalRef": null,
      "approvedVariantHash": null,
      "notes": ""
    }
  ]
}
```
Allowed `status`: `planned`, `awaiting_approval`, `approved`, `published`, `failed`, `cancelled`.
When Gate 2 is approved, record `approvalRef` (e.g., `"human:2026-01-16-msg-42"` or `"standing:daily-noon-x"`) and pin `approvedVariantHash` from `meta.json`; publishers must abort if the current file hash differs.

### `publish-log.jsonl` (one JSON object per line)
Required keys: `publishId`, `slotId`, `draftId`, `platform`, `accountId`, `status` (`published` | `draft_saved` | `failed`), `publishedAt` (ISO-8601 UTC), `publicUrl` (required when `published`; `null` otherwise), `workId` (string or `null`), `variantHash` (16-char sha256 prefix), `error` (string or `null`).

### `engagement/inbox.json`
Top-level wrapper: `{"version": 1, "comments": [ ... ]}`.
Each comment item: `commentId`, `platform`, `accountId`, `workId`, `workTitle`, `author`, `text`, `createdAt`, `tier` (`high_intent` | `feedback` | `general` | `spam`), `status` (`open` | `drafted` | `replied` | `escalated` | `ignored`), `draftReply`, `requiresApproval` (bool), `topicCandidate` (bool).

### `engagement/action-log.jsonl` (one JSON object per line)
Required keys (append-only, used for idempotency and daily rate-limit caps):
```json
{"actionId":"act-20260116-01","executedAt":"2026-01-16T04:15:00Z","platform":"x-twitter","accountId":"acct-x-main","targetId":"cmt-99","actionType":"reply","result":"ok","error":null}
```
Allowed `actionType`: `reply`, `like`, `unlike`, `repost`, `bookmark`, `quote`, `follow`, `delete_comment`, `hide_reply`. `executedAt` MUST be ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`).

### `analytics/snapshots.jsonl` (one JSON object per line)
Required keys: `snapshotId`, `capturedAt`, `window` (`24h` | `72h` | `7d` | `30d` | `account`), `platform`, `accountId`, `workId`, `topicId`, `title`, `metrics` (`views`, `likes`, `comments`, `shares`, `saves`), `platformMetrics` (object of platform-native numeric metrics).
**Unit convention for `platformMetrics`**:
- Percentage rates (`coverCtr`, `threeSecRetention`, `completionRate`, `bookmarkRate`, `impressionCtr`, `openRate`, `outboundClickRate`, `saveRate`, `shareRate`): store as **percent floats** (`0`–`100`, e.g., `8.5` for `8.5%`).
- Ratios (`saveToLikeRatio`, `coinToViewRatio`, `favoriteToViewRatio`): store as **decimal ratios** (e.g., `0.79`).
- Durations (`avgWatchTimeSec`, `avgViewDurationSec`): store in **seconds**.
