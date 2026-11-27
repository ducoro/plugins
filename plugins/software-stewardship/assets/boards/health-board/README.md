# Repository Health & Supply Chain Board

Displays live OSV.dev vulnerability findings, copyleft license alerts, oversized source files, 30-day Git churn hotspots, extra worktree counts, and 30-day revert rate projected from Space-local stewardship state.

## Semantic Location IDs

- Summary cards: `data-card="health-kpis"` (`kpi-vulns`, `kpi-licenses`, `kpi-hotspots`, `kpi-revert`)
- Alerts table: `data-card="health-alerts"`, rows `data-card="alert-<id>"` (e.g., `alert-cve-GHSA-xxxx-lodash`)
- Hotspots table: `data-card="churn-hotspots"`, rows `data-card="hotspot-<path>"` (e.g., `hotspot-src/server.ts`)

## Declared Commands

Invoke via `ducoro-cli board command <name> --board boards/<id> --space <space-id> [--arg key=value] --json`:
- `filterSeverity` (`--arg severity=all|high|medium`): filters supply-chain, license, file-size, and shotgun-commit signals.
- `focusAlert` (`--arg id=<alert-id>`): highlights and scrolls to a specific alert row.
- `resetFilters` (no `--arg`): resets filter and row focus.

## Interactive Controls & Boundaries

- **Stage Health Sweep / Discuss buttons**: stage a Composer draft (`ducoro.composer.draft`) for the human to review and send; hidden/disabled in standalone, read-only, or `shot` mode.
- **Read-only projection**: data is written exclusively by `scripts/build_boards.py` into `assets/data.json`.
