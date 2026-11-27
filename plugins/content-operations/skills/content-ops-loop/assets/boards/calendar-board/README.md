# Content Calendar & Schedule Board

## What This Board Is
Visualizes scheduled multi-platform slots from `calendar.json`, verified publish URLs from `publish-log.jsonl`, and upcoming seasonal anchors for content operators and reviewers.

## How to Add or Update Content
Do not edit DOM inline. Update `calendar.json` or `publish-log.jsonl` in the active data directory, then run:
```sh
python3 scripts/build_boards.py <data-dir> --board calendar-board --board-dir <this-board-dir>
```
Content identity conventions:
- Day cards: `data-card="day-YYYY-MM-DD"` (example: `data-card="day-2026-01-16"`).
- Schedule slots: `data-mark-item="slot-<slotId>"` (example: `data-mark-item="slot-slot-20260116-x-01"`).
- Export frame for `ducoro-cli render check` / `render shot`: `[data-export-frame="calendar-overview"]`.

## Declared View Commands
- `setView` (`mode`: `"month"` or `"week"`): `ducoro-cli board command setView --space <space-id> --board <board> --arg mode=week`
- `goToDate` (`date`: `YYYY-MM-DD`): `ducoro-cli board command goToDate --space <space-id> --board <board> --arg date=2026-01-16`
- `filterPlatform` (`platform`: platform slug or `"all"`): `ducoro-cli board command filterPlatform --space <space-id> --board <board> --arg platform=xiaohongshu`
- `focusSlot` (`slotId`: exact slot ID): `ducoro-cli board command focusSlot --space <space-id> --board <board> --arg slotId=slot-20260116-x-01`

## Runtime Ownership
- `runtime/board-sdk-bridge.js`: progressive `window.ducoro` integration (display theme/locale sync, cast resolution, link state, `storage` view persistence, `commands`, single-owner `revalidate`).
- `runtime/board-ui.css`: shared `shadcn/ui` semantic tokens and board layout primitives.
- `assets/data.json`: generated read-only snapshot refreshed by `build_boards.py`.

## Human Controls
- **View / Platform / Status selectors**: local view filters persisted to `ducoro.storage` when connected.
- **Draft Gate 2 Approval**: stages a complete approval message in the host Composer (`ducoro.composer.draft`); nothing sends until the human presses Send.
- **Draft Reschedule Note**: stages a reschedule request in the host Composer.

## Excluded Behavior
- Never publishes directly from browser buttons or modifies `calendar.json` directly from client JS.
