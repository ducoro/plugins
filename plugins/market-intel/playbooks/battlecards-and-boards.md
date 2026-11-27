# Battlecards & Interactive Boards

## 1. Two Bundled shadcn/ui Boards

| Board | Purpose | Commands Exposed to Agent |
|---|---|---|
| `radar-board` | Chronological ledger of verified material changes (including `sector-radar` discovery events) with severity, confidence (`triangulated` vs `single_source`), source kinds, quotes, and clickable evidence links | `filterEntity`, `filterSeverity`, `focusEvent`, `resetFilters` |
| `battlecard-board` | Side-by-side competitor comparison matrix (pricing, releases, hiring signals, strengths, gaps, discovery landmines, objection handlers, evidence links); automatically excludes `sector-radar` entries | `focusEntity`, `filterCategory`, `resetFilters` |

## 2. Provisioning, Linking & One-Way Projection

Business truth lives in `<data-dir>` (the human's existing folder, this Space's `files/`, or an optional cross-Space Local Folder). `scripts/init_workspace.py` never creates `boards/` inside `<data-dir>`. Each Ducoro Space board lives under `<space-work-root>/boards/<board-id>` and receives a one-way projection into `assets/data.json`.

1. **Locate the Space work root and check existing boards**:
   ```sh
   ducoro-cli space info <space-id> --json
   ducoro-cli board list --space <space-id> --json
   ```
2. **Create a Space board if none exists (or link an existing board to another Space)**:
   ```sh
   ducoro-cli board new --space <space-id> --title "Market Intel Radar" --json
   ducoro-cli board new --space <space-id> --title "Competitor Battlecards" --json
   ducoro-cli board link --space <other-space-id> --board boards/<board-id> --json
   ```
3. **First-time template install & routine data refresh**:
   ```sh
   # First-time setup into a Space board created via `ducoro-cli board new`
   python3 scripts/build_boards.py <data-dir> \
     --board radar-board \
     --board-dir <space-work-root>/boards/<board-id> \
     --overwrite-templates

   # Routine data refresh (updates only assets/data.json for flicker-free revalidate)
   python3 scripts/build_boards.py <data-dir> \
     --board radar-board \
     --board-dir <space-work-root>/boards/<board-id>
   ```
   Repeat with `--board battlecard-board` for the battlecard matrix board.

## 3. Operating Open Boards via Agent Commands

Discover active commands and guide the human directly to a verified event or competitor card:

```sh
ducoro-cli board commands --space <space-id>
ducoro-cli board command filterSeverity --board boards/<radar-id> --space <space-id> --arg severity=high --json
ducoro-cli board command focusEvent --board boards/<radar-id> --space <space-id> --arg eventId=<event-id> --json
ducoro-cli board command focusEntity --board boards/<battlecard-id> --space <space-id> --arg slug=<entity-slug> --json
```

All board command handlers validate arguments synchronously and throw clear errors on unknown keys, invalid severities, unknown categories, or unloaded slugs/event IDs.

## 4. Verification Before Presenting

Run headless render checks before sharing board snapshots:

```sh
ducoro-cli render check --file <board-dir>/index.html --json
ducoro-cli render shot --file <board-dir>/index.html --frame main --out /tmp/radar.png --json
```
