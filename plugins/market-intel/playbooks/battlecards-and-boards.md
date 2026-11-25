# Battlecards & Interactive Boards

## 1. Two Bundled shadcn/ui Boards

| Board | Purpose | Commands Exposed to Agent |
|---|---|---|
| `radar-board` | Chronological stream of verified material changes, severity, and clickable evidence URLs | `filterEntity`, `filterSeverity`, `focusEvent`, `resetFilters` |
| `battlecard-board` | Side-by-side entity comparison matrix (pricing, latest release, hiring velocity, differentiators) | `focusEntity`, `filterCategory`, `resetFilters` |

## 2. Provisioning & One-Way Projection

Business truth lives in the shared `market-intel` Local Folder. Each Ducoro Space board keeps its own isolated `assets/data.json` projected one-way from the workspace:

```sh
# First-time setup in a Space board created via `ducoro-cli board new --title "Market Intel Radar"`
python3 scripts/build_boards.py ~/.ducoro/workspaces/market-intel \
  --board radar-board \
  --board-dir <space-work-root>/boards/<board-id> \
  --overwrite-templates

# Routine data refresh (updates only assets/data.json for flicker-free revalidate)
python3 scripts/build_boards.py ~/.ducoro/workspaces/market-intel \
  --board radar-board \
  --board-dir <space-work-root>/boards/<board-id>
```

## 3. Verification Before Presenting

Run headless render checks before sharing snapshots:
```sh
ducoro-cli render check --file <board-dir>/index.html --json
ducoro-cli render shot --file <board-dir>/index.html --frame main --out /tmp/radar.png --json
```
