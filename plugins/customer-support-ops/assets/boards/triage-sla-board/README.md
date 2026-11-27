# Support Triage & SLA Board

## What This Board Is

Interactive support queue Board for the principal and support Lead to inspect deduplicated customer tickets, deterministic risk escalations, SLA breaches, and approval-locked outbound reply draft states.

## How to Add Content

Do not hand-edit ticket rows inside `index.html`. Project fresh data one-way from the active support `<data-dir>` into `assets/data.json`:

```sh
python3 scripts/build_boards.py <data-dir> --board triage-sla-board --board-dir <space-work-root>/boards/<board-id>
```

Each row rendered from `assets/data.json` carries stable location identities derived from its `ticketId`:

- Summary KPI card: `data-card="triage-kpis"` with `data-mark-item="kpi-open"`, `kpi-escalations`, `kpi-sla`, `kpi-drafts`
- Queue table card: `data-card="ticket-table"`
- Individual ticket row example (`ticketId: "github_issues:acme/app#101"`):
  `data-card="ticket-github_issues:acme/app#101"` and `data-mark-item="ticket-github_issues:acme/app#101"`

## What It Can Be Told to Do

All declared commands modify transient view state only and validate arguments synchronously:

- `filterPriority` (`priority`: `all|P0|P1|P2|P3`):
  ```sh
  ducoro-cli board command filterPriority --board boards/<id> --space <space-id> --arg priority=P0 --json
  ```
- `filterEscalated` (`escalatedOnly`: `true|false`):
  ```sh
  ducoro-cli board command filterEscalated --board boards/<id> --space <space-id> --arg escalatedOnly=true --json
  ```
- `focusTicket` (`ticketId`: exact ticket ID):
  ```sh
  ducoro-cli board command focusTicket --board boards/<id> --space <space-id> --arg ticketId=github_issues:acme/app#101 --json
  ```
- `resetFilters` (no arguments):
  ```sh
  ducoro-cli board command resetFilters --board boards/<id> --space <space-id> --json
  ```

## Runtime Ownership

- `index.html`: Page layout, table renderer, and Board command wiring.
- `assets/board-sdk-bridge.js`: Progressive-enhancement bridge (`window.ducoro` connection, `onDisplayChange`, `commands`, `storage`, and `revalidate` handler).
- `assets/board-ui.css`: Shared `shadcn/ui` semantic design tokens and component primitives.
- `assets/data.json`: One-way projected support queue snapshot written by `scripts/build_boards.py`.

## Excluded Behavior

- No inline ticket or reply body editing inside the Board DOM.
- No direct `composer.action` auto-sending or direct external helpdesk reply transmission from page controls.
- No direct reads of arbitrary local filesystem paths outside the Board's own `assets/` folder.
- Commands never call `composer.draft`, `action`, `mention`, or `use`.

## Human Controls

- **Priority selector** (`All priorities` / `P0`–`P3`): Filters visible ticket rows locally and persists the view preference via `ducoro.storage` when connected.
- **Escalated only checkbox**: Restricts visible rows to tickets requiring human approval.
- **Draft Triage Prompt** (header button, SDK-only): Stages a triage prompt in the Space Composer for human review before sending.
- **Draft Reply Prompt** (row button, SDK-only, `data-mark-ignore`): Stages a prompt referencing that exact `ticketId` in the Space Composer for human review before sending.
