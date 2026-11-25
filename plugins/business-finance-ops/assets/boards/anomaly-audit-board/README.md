# Anomaly & Subscription Audit Board

Displays deterministic duplicate charges, recurring vendor price hikes, budget breaches, and cash-runway alerts.

## Location IDs
- Summary KPIs: `data-card="audit-kpis"` (`kpi-alerts`, `kpi-high`, `kpi-dups`, `kpi-hikes`)
- Alert rows: `data-card="alert-<alertId>"`, `data-mark-item="alert-<alertId>"`

## Agent Commands (`ducoro-cli board command`)
- `filterSeverity` (`{ "severity": "all|high|medium" }`)
- `filterType` (`{ "type": "<type|all>" }`)
- `focusAlert` (`{ "alertId": "<alertId>" }`)
- `resetFilters` (`{}`)
