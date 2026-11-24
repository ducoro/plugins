# Engagement Inbox & Benchmark Radar Board

## What This Board Is
Displays two views sharing one per-platform daily rate-limit budget from `engagement/action-log.jsonl`:
1. **Inbound**: triaged comments on your own posts (`engagement/inbox.json`) across 4 intent tiers (`high_intent`, `feedback`, `general`, `spam`).
2. **Benchmark Radar**: human-approved benchmark accounts (`engagement/benchmark-accounts.json`) and drafted outbound value-add replies / quote-posts (`engagement/outbound-queue.json`).

## How to Add or Update Content
Update `engagement/inbox.json`, `engagement/benchmark-accounts.json`, `engagement/outbound-queue.json`, or append to `engagement/action-log.jsonl`, then run:
```sh
python3 scripts/build_boards.py <workspace>/content-ops --board engagement-inbox-board --board-dir <this-board-dir>
```
Content identity conventions:
- Queue containers: `data-card="triage-queue"`, `data-card="benchmark-accounts"`, `data-card="outbound-queue"`.
- Items: `data-mark-item="comment-<commentId>"`, `data-mark-item="bench-<watchId>"`, `data-mark-item="outbound-<outboundId>"`.
- Rate-limit meters: `data-mark-item="cap-<platform>"`.
- Export frame for `ducoro-cli render check` / `render shot`: `[data-export-frame="engagement-summary"]`.

## Declared View Commands
- `switchMode` (`mode`: `inbound | outbound`): `ducoro-cli board command switchMode --space <space-id> --board <board> --arg mode=outbound`
- `selectTier` (`tier`: `all | high_intent | feedback | general | spam`): `ducoro-cli board command selectTier --space <space-id> --board <board> --arg tier=high_intent`
- `filterPlatform` (`platform`): `ducoro-cli board command filterPlatform --space <space-id> --board <board> --arg platform=x-twitter`
- `focusComment` (`commentId`): `ducoro-cli board command focusComment --space <space-id> --board <board> --arg commentId=cmt-001`
- `focusOutbound` (`outboundId`): `ducoro-cli board command focusOutbound --space <space-id> --board <board> --arg outboundId=out-001`

## Runtime Ownership
- `runtime/board-sdk-bridge.js`, `runtime/board-ui.css`, and `assets/data.json`.

## Human Controls
- **Mode tabs, Tier tabs & Platform filter** persist via `ducoro.storage`.
- **Stage Approval / Stage Reply / Stage Outbound Action**: populates the host Composer via `ducoro.composer.draft` so the human approves/edits before anything activates or posts.
- **Save as Topic Signal**: drafts a prompt to recycle an inbound comment or benchmark post into `inbox/` and `topics/topics.json`.

## Excluded Behavior
- Never activates benchmark accounts or posts social replies/quotes directly from browser buttons.
