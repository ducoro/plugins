# Topic Pool & Draft Pipeline Board

## What This Board Is
Displays the 4-stage content funnel from `topics/topics.json` and `drafts/*/meta.json`, including 4-dimension topic scores, campaign plans, and per-platform spec validation alerts.

## How to Add or Update Content
Edit `topics/topics.json`, `drafts/plans.json`, or `drafts/<draft-id>/meta.json`, then rebuild:
```sh
python3 scripts/build_boards.py <workspace>/content-ops --board pipeline-board --board-dir <this-board-dir>
```
Content identity conventions:
- Stage columns: `data-card="stage-intake"`, `stage-approved`, `stage-ready`, `stage-archive`.
- Cards: `data-mark-item="topic-<topicId>"` or `data-mark-item="draft-<draftId>"`.
- Export frame: `[data-ducoro-export-frame="pipeline-summary"]`.

## Declared View Commands
- `filterPlan` (`planId`): `board command filterPlan --space <space-id> --board <board> --arg planId=plan-launch`
- `filterPlatform` (`platform`): `board command filterPlatform --space <space-id> --board <board> --arg platform=douyin`
- `focusItem` (`itemId`): `board command focusItem --space <space-id> --board <board> --arg itemId=top-20260115-01`

## Runtime Ownership
- `runtime/board-sdk-bridge.js` and `assets/data.json`.

## Human Controls
- **Plan / Platform / Spec Alerts Only** filters persist via `ducoro.storage`.
- **Draft Gate 1 Approval**: stages a topic approval prompt in the host Composer (`ducoro.composer.draft`).
- **Draft Spec Fix Request**: stages a spec remediation prompt in the host Composer.

## Excluded Behavior
- No inline drag-and-drop mutation of JSON files from browser code.
