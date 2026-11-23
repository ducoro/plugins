# Engagement Inbox & Lead Triage Board

## What This Board Is
Displays triaged comments from `engagement/inbox.json` across 4 intent tiers (`high_intent`, `feedback`, `general`, `spam`) alongside daily per-platform rate-limit usage from `engagement/action-log.jsonl`.

## How to Add or Update Content
Update `engagement/inbox.json` or append to `engagement/action-log.jsonl`, then run:
```sh
python3 scripts/build_boards.py <workspace>/content-ops --board engagement-inbox-board --board-dir <this-board-dir>
```
Content identity conventions:
- Queue container: `data-card="triage-queue"` (stable across tab filter changes).
- Comment items: `data-mark-item="comment-<commentId>"`.
- Rate-limit meters: `data-mark-item="cap-<platform>"`.
- Export frame: `[data-ducoro-export-frame="engagement-summary"]`.

## Declared View Commands
- `selectTier` (`tier`: `all | high_intent | feedback | general | spam`): `board command selectTier --space <space-id> --board <board> --arg tier=high_intent`
- `filterPlatform` (`platform`): `board command filterPlatform --space <space-id> --board <board> --arg platform=xiaohongshu`
- `focusComment` (`commentId`): `board command focusComment --space <space-id> --board <board> --arg commentId=cmt-001`

## Runtime Ownership
- `runtime/board-sdk-bridge.js` and `assets/data.json`.

## Human Controls
- **Tier tabs & Platform filter** persist via `ducoro.storage`.
- **Stage Reply for Confirmation**: populates the host Composer via `ducoro.composer.draft` so the human approves/edits before sending.
- **Stage as Next Topic Signal**: drafts a prompt to recycle a comment into `inbox/` and `topics/topics.json`.

## Excluded Behavior
- Never posts social replies directly from browser buttons.
