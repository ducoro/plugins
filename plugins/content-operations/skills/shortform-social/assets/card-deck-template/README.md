# Social Visual Card Deck

## Purpose
Exact-pixel visual card deck for multi-platform publishing (Xiaohongshu / Instagram / WeChat `newspic` `3:4` carousels, WeChat Official Account `2.35:1` + `1:1` cover pairs, and `16:9` video thumbnails).

## Content Identity Conventions
Every exportable frame declares stable HTML identities so humans can click any slide or block in Preview and ask for targeted edits without ambiguity:
- Frame container: `data-ducoro-export-frame="<id>"`, `data-card="<id>"`, `data-card-title="<readable name>"`
- Editable sub-targets: `data-mark-item="<id>-<part>"`, `data-mark-label="<readable label>"`
- Concrete example: `data-card="card-01"` with `data-mark-item="card-01-title"` ("Cover headline") and `data-mark-item="card-01-visual"` ("Cover visual slot").
- Preview chrome (`.studio-bar`) is marked `data-mark-ignore` and automatically hidden under `html[data-ducoro-render="shot"]`.

## Board Commands
- `focus-frame` (`frame`: string) — scrolls the named export frame into view.
- `preview-style` (`style`: `paper-studio|grid-spec|darkroom-frame`, `theme`: preset id) — temporarily previews another style/palette without modifying files.

Example CLI invocation:
```sh
ducoro-cli board command focus-frame --board boards/<board-id> --arg frame=card-01 --space <space-id> --json
```

## Verification & Export Workflow
1. Run offline structural audit:
   `python3 <skill-dir>/scripts/card_deck.py audit <board-dir> --json`
2. Run live browser layout & font check:
   `ducoro-cli board check --space <space-id> --board boards/<board-id> --json`
3. Export exact PNGs or ZIP:
   `ducoro-cli board shot --space <space-id> --board boards/<board-id> --query frame=card-01 --json`
   `ducoro-cli board shot --space <space-id> --board boards/<board-id> --query pack=all --json`

## Boundaries
- Authored copy, layout choices, and chosen `data-style`/`data-theme` live in `index.html` (edited by the Agent via file tools).
- The top preview bar only switches transient preview state and never mutates saved files.
- No external CDNs, remote fonts, or inline WYSIWYG editors.
