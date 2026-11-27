# Anomaly & Subscription Audit Board

Displays deterministic duplicate charges, recurring vendor price hikes, monthly budget breaches (`>= budgetWarnPct` / `>= 100%`), and cash-runway alerts (`base` or `recurringOnly` below `minRunwayMonths`) with raw statement traceability.

## Data Contract (`assets/data.json`)

Projected one-way from `<data-dir>/finance-report.json` via `scripts/build_boards.py`:
- `generatedAt`, `month`, `baseCurrency`
- `summary`: `totalAlerts`, `highCount`, `duplicateCount`, `hikeCount`
- `anomalies`: array of deterministic alerts with `alertId`, `type`, `severity`, `merchant`, `amount`, `currency`, `summary`, optional `triggeredScenarios`, and `evidence[]` (`txHash`, `sourceFile`, `sourceLine`)

## Location IDs

- Summary KPIs: `data-card="audit-kpis"` (`kpi-alerts`, `kpi-high`, `kpi-dups`, `kpi-hikes`)
- Audit table: `data-card="anomaly-table"`
- Alert rows: `data-card="alert-<alertId>"`, `data-mark-item="alert-<alertId>"`

## Agent Commands

List open-board commands and invoke them through `ducoro-cli`:

```sh
ducoro-cli board commands --space <space-id> --json
ducoro-cli board command filterSeverity --board boards/<id> --space <space-id> --arg severity=high --json
ducoro-cli board command filterType --board boards/<id> --space <space-id> --arg type=duplicate_charge --json
ducoro-cli board command focusAlert --board boards/<id> --space <space-id> --arg alertId=<alertId> --json
ducoro-cli board command resetFilters --board boards/<id> --space <space-id> --json
```

## Projection & Verification

```sh
python3 scripts/build_boards.py <data-dir> --board anomaly-audit-board --board-dir <space-work-root>/boards/<id> --overwrite-templates
ducoro-cli render check --file <space-work-root>/boards/<id>/index.html --json
ducoro-cli render shot --file <space-work-root>/boards/<id>/index.html --frame main --out <out.png> --json
```

Updates after initial setup omit `--overwrite-templates` so only `assets/data.json` refreshes in place via `ducoro.board.revalidate`.
