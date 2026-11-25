# Finance Overview & Runway Board

Displays exact `Decimal` monthly inflow/outflow, cash runway, budget utilization bars, and source-traced ledger rows.

## Location IDs
- Summary KPIs: `data-card="finance-kpis"` (`kpi-inflow`, `kpi-outflow`, `kpi-net`, `kpi-runway`)
- Budgets: `data-card="budget-<category>"`, `data-mark-item="budget-<category>"`
- Ledger rows: `data-card="tx-<txHash>"`, `data-mark-item="tx-<txHash>"`

## Agent Commands (`ducoro-cli board command`)
- `filterCategory` (`{ "category": "<slug|all>" }`)
- `focusTx` (`{ "txHash": "<txHash>" }`)
- `resetFilters` (`{}`)
