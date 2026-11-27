# Business Finance Ops Data Schema

This directory layout works inside the human's existing finance folder, a single Space's `files/` directory, or an optional cross-Space Local Folder (`<data-dir>`). Space Boards live separately under `<space-work-root>/boards/<board-id>/` and receive one-way projections via `scripts/build_boards.py`.

```text
<data-dir>/
├── accounts.json              # Base currency, current cash balances, thresholds, optional costClassMap
├── budgets.json               # Monthly category budgets in base currency (exact decimal strings)
├── category-rules.json        # Deterministic regex rules (inflow & outflow) + optional costClassMap
├── fx-cache.json              # Cached ECB and manual FX rates keyed by <BASE>:<YYYY-MM-DD|latest>
├── ledger.jsonl               # Append-only exact Decimal transaction ledger (txHash deduplicated)
├── finance-report.json        # Latest code-computed P&L, thresholds, flux, budgets, anomalies, and runway
├── raw-statements/            # Unmodified bank/Stripe/Alipay/WeChat/OFX exports & staged JSON files
├── invoices/                  # Local PDF/image invoices linked by file reference
└── reports/                   # Human-readable weekly/monthly executive summaries
```

## 1. Configuration Files

### `accounts.json`

```json
{
  "schemaVersion": "business-finance-accounts/1",
  "updatedAt": "2026-11-24T09:00:00Z",
  "baseCurrency": "USD",
  "cashBalances": {
    "USD": "48250.00",
    "CNY": "35000.00"
  },
  "thresholds": {
    "duplicateWindowHours": 72,
    "vendorHikePct": "20",
    "budgetWarnPct": "80",
    "minRunwayMonths": "6",
    "fluxMinAbs": "100",
    "fluxMinPct": "15"
  },
  "costClassMap": {}
}
```

- `baseCurrency`: 3-letter ISO-4217 reporting currency (`USD`, `CNY`, `EUR`, etc.).
- `cashBalances`: Map of `<CCY>` -> exact positive/non-negative decimal string representing verified ending cash balances across accounts.
- `thresholds`:
  - `duplicateWindowHours`: Time window in hours for `duplicate_charge` detection (default `72`).
  - `vendorHikePct`: Minimum percentage increase above historical median to trigger `vendor_price_hike` (default `"20"`).
  - `budgetWarnPct`: Budget utilization % triggering `budget_warning` (default `"80"`; `>= 100` triggers `budget_exceeded`).
  - `minRunwayMonths`: Runway threshold in months checked against **both** `base` and `recurringOnly` scenarios (default `"6"`).
  - `fluxMinAbs`: Minimum absolute MoM category spend delta in base currency for material flux (default `"100"`).
  - `fluxMinPct`: Minimum percentage MoM change for material flux when prior spend > 0 (default `"15"`).
- `costClassMap` (optional): Map of `<category-slug>` -> `recurring_revenue | one_time_revenue | cogs | fixed_opex | variable_opex` for business-model overrides.

### `budgets.json`

```json
{
  "schemaVersion": "business-finance-budgets/1",
  "updatedAt": "2026-11-24T09:00:00Z",
  "baseCurrency": "USD",
  "monthlyBudgets": {
    "cloud_infra": "1500.00",
    "software_saas": "800.00",
    "marketing": "2000.00"
  }
}
```

- `monthlyBudgets`: Map of `<category-slug>` -> exact decimal string monthly cap in `baseCurrency`.

### `category-rules.json`

```json
{
  "schemaVersion": "business-finance-category-rules/1",
  "rules": [
    {
      "pattern": "aws|cloudflare|aliyun",
      "category": "cloud_infra",
      "direction": "outflow"
    },
    {
      "pattern": "\\b(?:grant|setup fee|one-time|asset sale)\\b",
      "category": "one_time_revenue",
      "direction": "inflow",
      "costClass": "one_time_revenue"
    }
  ],
  "costClassMap": {
    "inventory": "cogs",
    "shipping": "cogs"
  }
}
```

- `rules[]`: Evaluated top-to-bottom on `"{merchant} {description}"` (case-insensitive regex):
  - `pattern` (required): Python regular expression.
  - `category` (required): Target budget/ledger category slug.
  - `direction` (optional): `"inflow"`, `"outflow"`, or `"any"` (omitted matches both directions).
  - `costClass` (optional): Explicit managerial class assigned onto ingested rows when matched.
- `costClassMap` (optional): Category-to-`costClass` overrides applied by `anomaly_and_runway.py` (takes precedence over `accounts.json` `costClassMap`, below per-row `costClass`).

### `fx-cache.json`

```json
{
  "schemaVersion": "business-finance-fx/1",
  "updatedAt": "2026-11-24T09:00:00Z",
  "snapshots": {
    "USD:2026-11-24": {
      "base": "USD",
      "date": "2026-11-24",
      "source": "ecb-frankfurter",
      "fetchedAt": "2026-11-24T09:00:00Z",
      "rates": {
        "USD": "1",
        "CNY": "7.24",
        "EUR": "0.95",
        "TWD": "32.50"
      }
    },
    "USD:latest": { "...": "..." }
  }
}
```

- Every rate is stored as an exact decimal string representing `1 <base> = <rate> <foreign>`.
- `source`: `"ecb-frankfurter"` (fetched via `fx_rates.py`) or `"manual"` (recorded via `fx_rates.py --set-rate`).

## 2. Ledger Record (`ledger.jsonl`)

Append-only JSON Lines file. Every numeric amount is an exact decimal string (`"129.50"`), never floating point:

- `txHash`: Deterministic 16-char SHA-256 deduplication fingerprint.
- `externalId`: Upstream transaction ID / FITID (empty string when absent).
- `date`: Accounting date `YYYY-MM-DD` (in UTC or the `--timezone` specified at ingestion).
- `timestamp`: ISO-8601 timestamp with explicit timezone (`Z` or `+/-HH:MM`).
- `direction`: `"inflow"` | `"outflow"`.
- `amount`: Exact positive decimal string in original currency.
- `currency`: 3-letter ISO-4217 code (`USD`, `CNY`, `EUR`, etc.).
- `merchant`: Normalized counterparty name.
- `description`: Line-item description or memo from the original statement.
- `category`: Category slug (e.g. `revenue`, `one_time_revenue`, `cloud_infra`, `payment_fees`).
- `costClass` (optional on disk; always resolved in `finance-report.json`): `"recurring_revenue"` | `"one_time_revenue"` | `"cogs"` | `"fixed_opex"` | `"variable_opex"`.
- `sourceFormat`: `"stripe"` | `"alipay"` | `"wechat"` | `"ofx"` | `"csv"` | `"connector"`.
- `sourceFile`: Basename of original statement or connector file.
- `sourceLine`: 1-based line, block, or record index in the original source.

## 3. Connector JSON Input (`--format connector`)

`scripts/ledger_engine.py --format connector` accepts either a JSON array `[...]` or an object containing a list under `transactions`, `items`, `data`, or `records`:

```json
{
  "transactions": [
    {
      "id": "mer_20261118_01",
      "timestamp": "2026-11-18T14:22:00Z",
      "amount": "-240.00",
      "currency": "USD",
      "merchant": "Cloudflare",
      "description": "Workers Pro + R2 usage",
      "category": "cloud_infra",
      "costClass": "cogs"
    }
  ]
}
```

- `amount` may be signed (positive = `inflow`, negative = `outflow`) or paired with explicit `direction: "inflow" | "outflow"`.
- `id`/`externalId`/`transactionId`, `timestamp`/`date`/`createdAt`/`created`, `merchant`/`counterparty`/`name`/`vendor`, and `description`/`memo` aliases are accepted.

## 4. Reversal & Corruption Recovery

- **Misclassified or erroneous business entries (append-only audit trail)**: Never silently rewrite historical lines to hide mistakes. To reverse an erroneous entry while preserving full auditability, append a reversing connector JSON entry with opposite `direction`, identical `amount` and `currency`, `externalId: "<orig-id>:reversal"`, and `description: "Reversal of <orig-txHash>: <reason>"`, then append the corrected entry and re-run `anomaly_and_runway.py`.
- **Corrupted `ledger.jsonl` line (fail-closed recovery)**: Both `ledger_engine.py` and `anomaly_and_runway.py` immediately abort with `CORRUPTED_LEDGER_LINE` (`file` and `line` in structured JSON stderr) if any non-empty line is truncated, invalid JSON, or missing `txHash`. Recovery procedure:
  1. Copy `ledger.jsonl` to a timestamped backup inside `raw-statements/` before editing.
  2. Inspect the reported `<file>:<line>` and verify it against the original statement at `sourceFile:sourceLine`.
  3. Repair the malformed line (or remove the partial interrupted write and re-ingest the original statement file—`txHash` deduplication prevents duplicates).
  4. Re-run `python3 scripts/anomaly_and_runway.py <data-dir> --write-report` and confirm cash balance reconciliation passes.
