# Battlecards & Interactive Boards

## 1. Two Bundled shadcn/ui Boards

| Board | Purpose | Commands Exposed to Agent |
|---|---|---|
| `radar-board` | Chronological stream of verified material changes, severity, and clickable evidence URLs | `filterEntity`, `filterSeverity`, `focusEvent`, `resetFilters` |
| `battlecard-board` | Side-by-side entity comparison matrix (pricing, latest release, hiring velocity, differentiators) | `focusEntity`, `filterCategory`, `resetFilters` |

## 2. Provisioning & One-Way Projection

Business truth lives in the chosen data directory (the human's existing folder, this Space's `files/`, or an optional cross-Space Local Folder). Each Ducoro Space board keeps its own isolated `assets/data.json` projected one-way from `<data-dir>`:

```sh
# First-time setup in a Space board created via `ducoro-cli board new --title "Market Intel Radar"`
python3 scripts/build_boards.py <data-dir> \
  --board radar-board \
  --board-dir <space-work-root>/boards/<board-id> \
  --overwrite-templates

# Routine data refresh (updates only assets/data.json for flicker-free revalidate)
python3 scripts/build_boards.py <data-dir> \
  --board radar-board \
  --board-dir <space-work-root>/boards/<board-id>
```

## 3. Verification Before Presenting

Run headless render checks before sharing snapshots:
```sh
ducoro-cli render check --file <board-dir>/index.html --json
ducoro-cli render shot --file <board-dir>/index.html --frame main --out /tmp/radar.png --json
```
