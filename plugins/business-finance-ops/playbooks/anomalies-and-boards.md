# Deterministic Anomaly Detection & Interactive Boards

## 1. Running Exact P&L, Budget, Anomaly & Runway Analysis

```sh
python3 scripts/anomaly_and_runway.py <data-dir> \
  --month 2026-11 \
  --write-report
```

Optional what-if expansion stress test (adds proposed monthly burn in base currency to `recurringOnly` burn):
```sh
python3 scripts/anomaly_and_runway.py <data-dir> \
  --month 2026-11 \
  --scenario-extra-burn 5000 \
  --write-report
```

The script reads `accounts.json`, `budgets.json`, `category-rules.json` (including optional `costClassMap`), `fx-cache.json`, and `ledger.jsonl` (fail-closed on any corrupted line, reporting `<file>:<line>` in structured JSON stderr with non-zero exit).

### Four Deterministic Risk Classes

1. **Duplicate charges (`duplicate_charge`, severity `high`)**: Outflows with identical normalized merchant, exact `Decimal` amount, and currency within `thresholds.duplicateWindowHours` (default `72` hours). Includes `evidence[]` with both `txHash` and `sourceFile:sourceLine`.
2. **Recurring vendor price hike (`vendor_price_hike`, severity `medium`)**: Latest outflow to a merchant (with at least 2 prior historical charges) exceeds historical median in base currency by at least `thresholds.vendorHikePct` (default `20%`).
3. **Budget breaches (`budget_warning` >= `thresholds.budgetWarnPct`, `budget_exceeded` >= `100%`)**: Evaluated per category in base currency against `budgets.json`.
4. **Low cash runway (`low_runway`, severity `high`)**: Evaluates **both** `scenarios.base.runwayMonths` and `scenarios.recurringOnly.runwayMonths` against `thresholds.minRunwayMonths` (default `6`). If **either** scenario falls below `minRunwayMonths`, the alert triggers and lists `triggeredScenarios` (e.g., `["recurringOnly"]` when one-time windfalls mask structural burn). Effective thresholds are written into `finance-report.json` under `thresholds` so boards never hardcode thresholds.

## 2. Two Bundled shadcn/ui Boards

| Board | Purpose | Agent Commands |
|---|---|---|
| `finance-overview-board` | Exact base-currency P&L, Gross Margin %, multi-scenario cash runway (`minRunwayMonths` from report), MoM flux summary, category budget bars, and source-traced ledger table | `filterCategory`, `focusTx`, `resetFilters` |
| `anomaly-audit-board` | Actionable duplicate charges, vendor price hikes, budget breaches, and `base`/`recurringOnly` runway alerts with raw statement trace | `filterSeverity`, `filterType`, `focusAlert`, `resetFilters` |

## 3. Full Space Board Lifecycle & Verification

1. **Locate Space work root and check existing Boards**:
   ```sh
   ducoro-cli space info <space-id> --json
   ducoro-cli board list --space <space-id> --json
   ```
2. **Create Board shell on first setup**:
   ```sh
   ducoro-cli board new --space <space-id> --title "Finance Overview & Runway" --json
   ducoro-cli board new --space <space-id> --title "Anomaly & Subscription Audit" --json
   ```
3. **Project one-way from `<data-dir>` into each Space Board**:
   - Initial setup (copies HTML/CSS/JS/README + `assets/data.json`):
     ```sh
     python3 scripts/build_boards.py <data-dir> \
       --board finance-overview-board \
       --board-dir <space-work-root>/boards/<overview-board-id> \
       --overwrite-templates
     python3 scripts/build_boards.py <data-dir> \
       --board anomaly-audit-board \
       --board-dir <space-work-root>/boards/<audit-board-id> \
       --overwrite-templates
     ```
   - Subsequent data refreshes (omit `--overwrite-templates` so only `assets/data.json` updates atomically in place and `ducoro.board.revalidate` hot-refreshes the open board):
     ```sh
     python3 scripts/build_boards.py <data-dir> \
       --board finance-overview-board \
       --board-dir <space-work-root>/boards/<overview-board-id>
     ```
   - Local offline preview only (never used as Space production layout): `python3 scripts/build_boards.py <data-dir> --all --boards-root <preview-dir> --overwrite-templates`.
4. **Resolve Board links and drive open Board views via CLI**:
   ```sh
   ducoro-cli board link --space <space-id> --board boards/<overview-board-id> --json
   ducoro-cli board commands --space <space-id> --json
   ducoro-cli board command filterCategory --board boards/<overview-board-id> --space <space-id> --arg category=cloud_infra --json
   ducoro-cli board command focusAlert --board boards/<audit-board-id> --space <space-id> --arg alertId=<alert-id> --json
   ```
5. **Verify layout & visual truth before reporting**:
   ```sh
   ducoro-cli render check --file <space-work-root>/boards/<overview-board-id>/index.html --json
   ducoro-cli render shot --file <space-work-root>/boards/<overview-board-id>/index.html --frame main --out <space-work-root>/files/finance-overview.png --json
   ducoro-cli render check --file <space-work-root>/boards/<audit-board-id>/index.html --json
   ducoro-cli render shot --file <space-work-root>/boards/<audit-board-id>/index.html --frame main --out <space-work-root>/files/anomaly-audit.png --json
   ```

## 4. High-Risk Alert Escalation & Independent Audit

Before escalating a `high`-severity alert to the human:
1. Dispatch a read-only audit job (`ducoro-cli space participant list <space-id> --json`, `ducoro-cli job dispatch --space <space-id> --agent <agent-id> --name "verify-alert" "..."`, `ducoro-cli job status <job-id> --json`, `ducoro-cli job log <job-id>`) to verify the cited `sourceFile:sourceLine` lines in `raw-statements/` and confirm no inter-account transfer or timing artifact caused a false positive.
2. Route verified high-severity alerts to Inbox immediately:
   ```sh
   ducoro-cli identity get --json
   ducoro-cli task create --space <space-id> --manual \
     --title "High-Severity Finance Alert" \
     --instruction "Present verified alert details, raw statement trace, and recommended next steps." \
     --human <human-id> --ask confirm \
     --request-summary "Review verified duplicate charge, budget breach, or low-runway alert" --json
   ducoro-cli task fire <task-id> --space <space-id> --json
   ```
3. Notify downstream stakeholder Spaces when needed via `ducoro-cli space mail send <recipient> --subject "..." --body "..."`.
