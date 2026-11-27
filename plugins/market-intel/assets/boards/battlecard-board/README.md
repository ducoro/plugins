# Competitor Battlecards Board

## What This Board Is

A side-by-side comparison matrix for founders, product leads, and sales teams comparing tracked entities across pricing, releases, hiring signals, strengths, gaps, discovery landmines, objection handlers, and source evidence. Projected one-way from `<data-dir>/battlecards/*.json`, `<data-dir>/entities/*/profile.json`, and `<data-dir>/events.jsonl`.

## How to Add or Update Content

Do not hand-edit card markup in `index.html`. Edit `<data-dir>/battlecards/<slug>.json` (or `<data-dir>/entities/<slug>/profile.json`) grounded in verified evidence, then project fresh data into this board:

```sh
python3 scripts/build_boards.py <data-dir> \
  --board battlecard-board \
  --board-dir <space-work-root>/boards/<board-id>
```

### Addressable Location IDs

Every KPI block and entity card carries stable semantic location attributes:

- Coverage KPIs: `data-card="bc-kpis"` with `data-mark-item="kpi-tracked"` and `data-mark-item="kpi-covered"`
- Matrix region: `data-card="battlecard-matrix"`
- Each entity card: `data-card="entity-<slug>"` and `data-mark-item="entity-<slug>"`
  - Example: `<article class="ui-card" data-card="entity-acme" data-card-title="Acme Corp" data-mark-item="entity-acme" data-mark-label="Acme Corp">`

## What It Can Be Told to Do (Agent Commands)

Inspect available commands on an open board with `ducoro-cli board commands --space <space-id>`, and invoke them with `ducoro-cli board command`:

- `filterCategory` — Filter cards by entity category or `all` (throws synchronously on unknown category or extra arguments):
  ```sh
  ducoro-cli board command filterCategory --board boards/<board-id> --space <space-id> --arg category=direct-competitor --json
  ```
- `focusEntity` — Highlight and scroll to a loaded entity battlecard by slug (throws synchronously if slug is unknown or missing):
  ```sh
  ducoro-cli board command focusEntity --board boards/<board-id> --space <space-id> --arg slug=acme --json
  ```
- `resetFilters` — Reset category filter and focus highlight:
  ```sh
  ducoro-cli board command resetFilters --board boards/<board-id> --space <space-id> --json
  ```

## Runtime Ownership

- `index.html`: Card grid layout, battlecard rendering (including strengths, gaps, landmines, objection handlers, and evidence links), and transient view command handlers.
- `assets/board-ui.css`: Shared shadcn/ui semantic tokens and light/dark component primitives.
- `assets/board-sdk-bridge.js`: Progressive-enhancement bridge for `window.ducoro` (`onDisplayChange`, `onLinkChange`, `onCastChange`, `storage`, `commands`, `revalidate`). Modifying `index.html`, `assets/board-sdk-bridge.js`, or `assets/board-ui.css` triggers `reload-required`; modifying `assets/data.json` applies in place.
- `assets/data.json`: One-way generated snapshot written exclusively by `scripts/build_boards.py`.

## Human Controls

- **Category dropdown**: Filters visible cards locally and persists the shared view preference via `ducoro.storage` when connected.
- **Refresh Battlecards**: Stages a full battlecard refresh draft in the Space Composer for human review and send.
- **Update Card**: Stages a targeted refresh draft for that entity slug in the Space Composer for human review and send.

## Excluded Behavior

- No inline text editing of battlecards inside the browser.
- Never writes directly to `<data-dir>` files and never sends Space messages automatically without explicit human confirmation.
- Read-only in standalone mode, share previews, and `data-ducoro-render="shot"` static renders.
