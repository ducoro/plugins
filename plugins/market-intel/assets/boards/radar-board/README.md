# Market Intel Radar Board

## What This Board Is

A chronological, evidence-backed change ledger for human decision-makers and analysts tracking competitors, target companies, or market sectors. It projects verified rows from `<data-dir>/events.jsonl` and `<data-dir>/watchlist.json` one-way into this board's `assets/data.json`.

## How to Add or Update Content

Do not hand-edit rendered rows in `index.html`. Update `<data-dir>/watchlist.json` and commit grounded claims via `scripts/evidence_gate.py --commit-events`, then project fresh data into this board:

```sh
python3 scripts/build_boards.py <data-dir> \
  --board radar-board \
  --board-dir <space-work-root>/boards/<board-id>
```

### Addressable Location IDs

Every KPI card and event row carries stable semantic location attributes:

- Summary block: `data-card="radar-kpis"` with items `data-mark-item="kpi-entities"`, `kpi-sources`, `kpi-events`, `kpi-high`
- Ledger section: `data-card="radar-events"`
- Each verified change row: `data-card="event-<eventId>"` and `data-mark-item="event-<eventId>"`
  - Example: `<tr data-card="event-9f2a1c04b8e7d312" data-card-title="Acme Corp: Pro Plan raised to $49/mo" data-mark-item="event-9f2a1c04b8e7d312" data-mark-label="Pro Plan raised to $49/mo">`

## What It Can Be Told to Do (Agent Commands)

Inspect available commands on an open board with `ducoro-cli board commands --space <space-id>`, and invoke them with `ducoro-cli board command`:

- `filterEntity` — Filter rows by entity slug or `all` (throws synchronously on unknown slug or extra arguments):
  ```sh
  ducoro-cli board command filterEntity --board boards/<board-id> --space <space-id> --arg entity=acme --json
  ```
- `filterSeverity` — Filter rows by `all`, `high`, `medium`, or `low` (throws synchronously on invalid value or extra arguments):
  ```sh
  ducoro-cli board command filterSeverity --board boards/<board-id> --space <space-id> --arg severity=high --json
  ```
- `focusEvent` — Highlight and scroll to a loaded `eventId` (throws synchronously if `eventId` is missing or not loaded):
  ```sh
  ducoro-cli board command focusEvent --board boards/<board-id> --space <space-id> --arg eventId=<event-id> --json
  ```
- `resetFilters` — Reset entity filter, severity filter, and focus highlight:
  ```sh
  ducoro-cli board command resetFilters --board boards/<board-id> --space <space-id> --json
  ```

## Runtime Ownership

- `index.html`: Page layout, table rendering (confidence, source kinds, quotes, evidence links), and transient view command handlers.
- `assets/board-ui.css`: Shared shadcn/ui semantic tokens and light/dark component primitives.
- `assets/board-sdk-bridge.js`: Progressive-enhancement bridge for `window.ducoro` (`onDisplayChange`, `onLinkChange`, `onCastChange`, `storage`, `commands`, `revalidate`). Modifying `index.html`, `assets/board-sdk-bridge.js`, or `assets/board-ui.css` triggers `reload-required`; modifying `assets/data.json` applies in place.
- `assets/data.json`: One-way generated snapshot written exclusively by `scripts/build_boards.py`.

## Human Controls

- **Entity / Severity dropdowns**: Adjust local table filters and persist shared view preferences via `ducoro.storage` when connected.
- **Stage Sweep**: Stages a sweep request draft in the Space Composer for human review and send (hidden/disabled outside embedded connected sessions).
- **Discuss**: Stages a draft referencing that specific `eventId` in the Space Composer for human review and send.

## Excluded Behavior

- No inline editing of events, quotes, or watchlists inside the browser.
- Never writes directly to `<data-dir>` files and never sends Space messages automatically without explicit human confirmation.
- Read-only in standalone mode, share previews, and `data-ducoro-render="shot"` static renders.
