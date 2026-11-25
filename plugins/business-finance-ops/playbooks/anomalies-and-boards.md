# Deterministic Anomaly Detection & Interactive Boards

## 1. Running Exact P&L, Budget, Anomaly & Runway Analysis

```sh
python3 scripts/anomaly_and_runway.py ~/.ducoro/workspaces/business-finance-ops \
  --month 2026-11 \
  --write-report
```
Detects four deterministic risk classes:
1. **Duplicate charges** (`duplicate_charge`): Same merchant, exact same `Decimal` amount and currency within `duplicateWindowHours` (default 72h).
2. **Recurring vendor price hike** (`vendor_price_hike`): Latest charge exceeds the vendor's historical median by at least `vendorHikePct` (default 20%).
3. **Budget breaches** (`budget_warning` >= 80%, `budget_exceeded` >= 100%) against `budgets.json`.
4. **Low cash runway** (`low_runway`): `cashBalance / monthlyNetBurn < minRunwayMonths`.

## 2. Two Bundled shadcn/ui Boards

| Board | Purpose | Agent Commands |
|---|---|---|
| `finance-overview-board` | Exact base-currency P&L, cash runway, category budget bars, and source-traced ledger table | `filterCategory`, `focusTx`, `resetFilters` |
| `anomaly-audit-board` | Actionable duplicate charges, vendor price hikes, budget breaches, and runway alerts | `filterSeverity`, `filterType`, `focusAlert`, `resetFilters` |

Project via `scripts/build_boards.py <workspace> --board <name> --board-dir <space-work-root>/boards/<id>` (use `--overwrite-templates` on initial creation).
