# Content Calendar & Schedule Board

## What This Board Is
Visualizes scheduled multi-platform slots from `calendar.json`, verified publish URLs from `publish-log.jsonl`, and upcoming seasonal anchors for content operators and reviewers.

## How to Add or Update Content
Do not edit DOM inline. Update `content-ops/calendar.json` or `content-ops/publish-log.jsonl`, then run:
```sh
python3 scripts/build_boards.py <workspace>/content-ops --board calendar-board --board-dir <this-board-dir>
```
Content identity conventions:
- Day cards: `data-card="day-YYYY-MM-DD"` (example: `data-card="day-2026-01-16"`).
- Schedule slots: `data-mark-item="slot-<slotId>"` (example: `data-mark-item="slot-slot-20260116-x-01"`).
- Export frame for `board check` / `board shot`: `[data-ducoro-export-frame="calendar-overview"]`.

## Declared View Commands
- `setView` (`mode`: `"month"` or `"week"`): `board command setView --space <space-id> --board <board> --arg mode=week`
- `goToDate` (`date`: `YYYY-MM-DD`): `board command goToDate --space <space-id> --board <board> --arg date=2026-01-16`
- `filterPlatform` (`platform`: platform slug or `"all"`): `board command filterPlatform --space <space-id> --board <board> --arg platform=xiaohongshu`
- `focusSlot` (`slotId`: exact slot ID): `board command focusSlot --space <space-id> --board <board> --arg slotId=slot-20260116-x-01`

## Runtime Ownership
- `runtime/board-sdk-bridge.js`: progressive `window.ducoro` integration (cast resolution, link state, `storage` view persistence, `commands`, single-owner `revalidate`).
- `assets/data.json`: generated read-only snapshot refreshed by `build_boards.py`.

## Human Controls
- **View / Platform / Status selectors**: local view filters persisted to `ducoro.storage` when connected.
- **Draft Gate 2 Approval**: stages a complete approval message in the host Composer (`ducoro.composer.draft`); nothing sends until the human presses Send.
- **Draft Reschedule Note**: stages a reschedule request in the host Composer.

## Excluded Behavior
- Never publishes directly from browser buttons or modifies `calendar.json` directly from client JS.
