# Social Visual Card Deck

## Purpose
Exact-pixel HTML visual card deck for multi-platform publishing (Xiaohongshu / Instagram / WeChat `newspic` `3:4` or `4:5` carousels, LinkedIn PDF carousels, WeChat Official Account `2.35:1` + `1:1` cover pairs, and `16:9` video thumbnails). Renders directly from any local folder via `ducoro-cli render` without creating a Board; optionally opens cleanly inside a Ducoro Board when interactive click-to-comment review is desired.

## Content Identity & Export Conventions
Every exportable frame declares stable HTML attributes for deterministic rendering and optional Board review:
- Export frame container: `data-export-frame="<id>"`, `data-export-width="<px>"`, `data-export-height="<px>"`, plus optional Board location identities `data-card="<id>"`, `data-card-title="<readable name>"`
- Editable sub-targets: `data-mark-item="<id>-<part>"`, `data-mark-label="<readable label>"`
- Concrete example: `data-export-frame="card-01"` with `data-mark-item="card-01-title"` ("Cover headline") and `data-mark-item="card-01-visual"` ("Cover visual slot").
- Preview chrome (`.studio-bar`) is marked `data-mark-ignore`, excluded from `[data-export-frame]` bounds, hidden in `@media print`, and hidden under `html[data-ducoro-render="shot"]`.

## Optional Board Commands (When Opened in a Ducoro Board)
- `focus-frame` (`frame`: string) — scrolls the named export frame into view.
- `preview-style` (`style`: `paper-studio|grid-spec|darkroom-frame`, `theme`: preset id) — temporarily previews another style/palette without modifying files.

Example CLI invocation (only when hosted in an open Board):
```sh
ducoro-cli board command focus-frame --board boards/<board-id> --arg frame=card-01 --space <space-id> --json
```

## Verification & Export Workflow (Direct Local Folder — No Board Required)
1. Run offline structural & contrast audit:
   `python3 <skill-dir>/scripts/card_deck.py audit <deck-dir> --json`
2. Run live browser layout, asset & font check:
   `ducoro-cli render check --file <deck-dir>/index.html --json`
3. Export exact images or PDF directly into your draft assets folder:
   - All frames as individual PNGs (default):
     `ducoro-cli render shot --file <deck-dir>/index.html --all --out-dir <draft-dir>/assets --json`
   - JPEG export (for Instagram / Meta Graph APIs):
     `ducoro-cli render shot --file <deck-dir>/index.html --all --format jpeg --quality 92 --out-dir <draft-dir>/assets --json`
   - Single frame:
     `ducoro-cli render shot --file <deck-dir>/index.html --frame card-01 --out <draft-dir>/assets/card-01.png --json`
   - LinkedIn / multi-page PDF carousel:
     `ducoro-cli render pdf --file <deck-dir>/index.html --out <draft-dir>/assets/deck.pdf --json`

## Boundaries
- Authored copy, layout choices, and chosen `data-style`/`data-theme` live in `index.html` (edited by the Agent via file tools).
- The top preview bar only switches transient preview state and never mutates saved files.
- No external CDNs, remote fonts, or inline WYSIWYG editors.
