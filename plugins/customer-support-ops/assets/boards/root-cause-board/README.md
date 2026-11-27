# Root-Cause & Pain-Point Spikes Board

## What This Board Is

Interactive Voice-of-Customer (VoC) Board for the principal, support Lead, and product owners to review clustered customer issues, real 7-day vs prior-7-day volume trends, anti-false-consensus unique customer counts, and verbatim ticket citations.

## How to Add Content

Do not hand-edit cluster cards inside `index.html`. Update `issues/root-causes.json` and ticket `rootCauseId` assignments in `<data-dir>`, run `scripts/triage_gate.py <data-dir> --write-report`, and project one-way into `assets/data.json`:

```sh
python3 scripts/build_boards.py <data-dir> --board root-cause-board --board-dir <space-work-root>/boards/<board-id>
```

Each cluster card rendered from `assets/data.json` carries stable location identities derived from its `rootCauseId`:

- Summary KPI card: `data-card="rc-kpis"` with `data-mark-item="kpi-clusters"`, `kpi-spikes`, `kpi-linked`
- Cluster grid container: `data-card="issues-matrix"`
- Individual cluster card example (`rootCauseId: "macos-sync-hang"`):
  `data-card="issue-macos-sync-hang"` and `data-mark-item="issue-macos-sync-hang"`

## What It Can Be Told to Do

All declared commands modify transient view state only and validate arguments synchronously:

- `filterSpikes` (`spikesOnly`: `true|false`):
  ```sh
  ducoro-cli board command filterSpikes --board boards/<id> --space <space-id> --arg spikesOnly=true --json
  ```
- `focusIssue` (`rootCauseId`: exact root-cause slug):
  ```sh
  ducoro-cli board command focusIssue --board boards/<id> --space <space-id> --arg rootCauseId=macos-sync-hang --json
  ```
- `resetFilters` (no arguments):
  ```sh
  ducoro-cli board command resetFilters --board boards/<id> --space <space-id> --json
  ```

## Runtime Ownership

- `index.html`: Page layout, cluster card renderer, and Board command wiring.
- `assets/board-sdk-bridge.js`: Progressive-enhancement bridge (`window.ducoro` connection, `onDisplayChange`, `commands`, `storage`, and `revalidate` handler).
- `assets/board-ui.css`: Shared `shadcn/ui` semantic design tokens and component primitives.
- `assets/data.json`: One-way projected root-cause and spike snapshot written by `scripts/build_boards.py`.

## Excluded Behavior

- No inline cluster editing or ticket reclassification inside the Board DOM.
- No direct `composer.action` auto-sending or automatic cross-Space mail dispatch from page controls.
- No synthetic or fabricated 7-day trend counts for steady clusters (all trends derive from real `clusterMetrics` or ticket timestamps).
- Commands never call `composer.draft`, `action`, `mention`, or `use`.

## Human Controls

- **Spikes only checkbox**: Filters visible cards to active spiking clusters locally and persists the preference via `ducoro.storage` when connected.
- **Draft Product Brief** (header button, SDK-only): Stages a weekly product review summary prompt in the Space Composer for human review before sending.
- **Draft Engineering Escalation** (card button, SDK-only, `data-mark-ignore`): Stages a prompt referencing that exact `rootCauseId` in the Space Composer for human review before sending.
