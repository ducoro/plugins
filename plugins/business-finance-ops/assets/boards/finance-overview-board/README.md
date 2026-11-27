# Finance Overview & Runway Board

Displays exact `Decimal` monthly inflow/outflow, Gross Margin %, multi-scenario cash runway stress tests, MoM flux summary, category budget utilization bars, and source-traced ledger rows.

## Data Contract (`assets/data.json`)

Projected one-way from `<data-dir>/finance-report.json` via `scripts/build_boards.py`:
- `generatedAt`, `month`, `baseCurrency`
- `thresholds`: active threshold config including `minRunwayMonths` (drives runway highlight tone)
- `summary`: `inflowTotal`, `recurringInflow`, `oneTimeInflow`, `outflowTotal`, `grossMarginPct`, `netCashFlow`, `totalCashBalance`, `monthlyNetBurn`, `recurringNetBurn`, `runwayMonths`, `transactionCount`, `anomalyCount`, `highAnomalyCount`
- `scenarios`: `base`, `recurringOnly`, `downsideRev20`, optional `proposedExpansion`
- `fluxAnalysis`: category MoM variance list with `isMaterial`
- `budgets`: category budget progress items
- `transactions`: statement-traced ledger rows (`sourceFile:sourceLine`)

## Location IDs

- Summary KPIs: `data-card="finance-kpis"` (`kpi-inflow`, `kpi-outflow`, `kpi-net`, `kpi-margin`, `kpi-runway`)
- Runway scenarios: `data-card="runway-scenarios"`, cards `data-card="scenario-<key>"` / `data-mark-item="scenario-<key>"` (`base`, `recurringOnly`, `downsideRev20`, `proposedExpansion`)
- Budgets: `data-card="budget-<category>"`, `data-mark-item="budget-<category>"`
- Ledger rows: `data-card="tx-<txHash>"`, `data-mark-item="tx-<txHash>"`

## Agent Commands

List open-board commands and invoke them through `ducoro-cli`:

```sh
ducoro-cli board commands --space <space-id> --json
ducoro-cli board command filterCategory --board boards/<id> --space <space-id> --arg category=<slug|all> --json
ducoro-cli board command focusTx --board boards/<id> --space <space-id> --arg txHash=<txHash> --json
ducoro-cli board command resetFilters --board boards/<id> --space <space-id> --json
```

## Projection & Verification

```sh
python3 scripts/build_boards.py <data-dir> --board finance-overview-board --board-dir <space-work-root>/boards/<id> --overwrite-templates
ducoro-cli render check --file <space-work-root>/boards/<id>/index.html --json
ducoro-cli render shot --file <space-work-root>/boards/<id>/index.html --frame main --out <out.png> --json
```

Updates after initial setup omit `--overwrite-templates` so only `assets/data.json` refreshes in place via `ducoro.board.revalidate`.
