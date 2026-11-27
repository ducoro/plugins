# Analytics & Retrospective Board

## What This Board Is
Aggregates 24h/72h/7d/30d snapshots from `analytics/snapshots.jsonl` and the latest weekly retrospective from `analytics/retros/*.md`, showing cross-platform same-topic comparisons and platform-native metrics when filtered to a single platform.

## How to Add or Update Content
Append verified snapshots to `analytics/snapshots.jsonl` or update `analytics/retros/YYYY-Www.md` in the active data directory, then run:
```sh
python3 scripts/build_boards.py <data-dir> --board analytics-retro-board --board-dir <this-board-dir>
```
Content identity conventions:
- Sections: `data-card="kpi-summary"`, `platform-native-metrics`, `trend-chart`, `cross-platform`, `works-leaderboard`, `retro-actions`.
- Items: `data-mark-item="work-<workId>"`, `data-mark-item="cross-<topicId>"`, `data-mark-item="action-<id>"`.
- Export frame for `ducoro-cli render check` / `render shot`: `[data-export-frame="analytics-summary"]`.

## Declared View Commands
- `setRange` (`days`: `7 | 14 | 30`): `ducoro-cli board command setRange --space <space-id> --board <board> --arg days=7`
- `filterPlatform` (`platform`): `ducoro-cli board command filterPlatform --space <space-id> --board <board> --arg platform=xiaohongshu`
- `focusWork` (`workId`): `ducoro-cli board command focusWork --space <space-id> --board <board> --arg workId=wk-001`

## Runtime Ownership
- `runtime/board-sdk-bridge.js`, `runtime/board-ui.css`, and `assets/data.json`.

## Human Controls
- **7d / 14d / 30d** range buttons and **Platform filter** persist via `ducoro.storage`.
- **Stage as Next-Cycle Topic**: stages a prompt in the host Composer (`ducoro.composer.draft`) to recycle a retro action into `inbox/` and `topics/topics.json`.

## Excluded Behavior
- Pure SVG trend rendering with zero external charting CDN dependencies; never mutates snapshot logs from client JS.
