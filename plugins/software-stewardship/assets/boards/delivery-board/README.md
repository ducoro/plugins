# Delivery & Gate Board

Displays real Git blast radius, objective diff gate blockers, open PRs and CI runs, fresh command execution evidence, and drift-proof `head_sha + diff_hash` approval locks projected from Space-local stewardship state.

## Semantic Location IDs

- Summary cards: `data-card="delivery-kpis"` (`kpi-changed`, `kpi-blockers`, `kpi-ci`, `kpi-evidence`)
- Active items table: `data-card="delivery-items"`, rows `data-card="item-<id>"` (e.g., `item-blocker-hardcoded_secret_assign-src/config.ts`, `item-pr-42`)
- Approval locks table: `data-card="approval-locks"`, rows `data-card="approval-<action>"` (e.g., `approval-release`)

## Declared Commands

Invoke via `ducoro-cli board command <name> --board boards/<id> --space <space-id> [--arg key=value] --json`:
- `filterKind` (`--arg kind=all|blocker|sensitive_path|pull_request|ci_run`): filters the active items table.
- `focusItem` (`--arg id=<item-id>`): highlights and scrolls to a specific item row.
- `resetFilters` (no `--arg`): resets kind filter and row focus.

## Interactive Controls & Boundaries

- **Stage Gate Check / Review buttons**: stage a Composer draft (`ducoro.composer.draft`) for the human to review and send; disabled in standalone, read-only, or `shot` capture mode.
- **No inline editing**: persistent repo changes and approvals are executed only through conversation and `scripts/change_gate.py`, then projected one-way into `assets/data.json`.
