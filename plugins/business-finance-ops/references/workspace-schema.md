# Business Finance Ops Workspace Schema

Default Local Folder path: `~/.ducoro/workspaces/business-finance-ops` (slug: `business-finance-ops`).

```text
business-finance-ops/
├── accounts.json              # Base currency, current cash balances by currency, anomaly thresholds
├── budgets.json               # Monthly category budgets in base currency (exact decimal strings)
├── category-rules.json        # Deterministic merchant regex -> category rules
├── fx-cache.json              # Cached ECB FX rates keyed by date + base currency
├── ledger.jsonl               # Append-only exact Decimal transaction ledger (txHash deduplicated)
├── finance-report.json        # Latest code-computed P&L, budgets, anomalies, and runway output
├── raw-statements/            # Unmodified bank/Stripe/Alipay/WeChat/OFX exports
├── invoices/                  # Local PDF/image invoices linked by file reference
└── reports/                   # Human-readable weekly/monthly executive summaries
```

## Ledger Record (`ledger.jsonl`)

Every numeric field is stored as an exact decimal string (`"129.50"`), never floating point:
- `txHash`: deterministic 16-char sha256 deduplication fingerprint
- `externalId`: upstream transaction ID / FITID (when present)
- `date`: `YYYY-MM-DD`
- `timestamp`: ISO-8601 UTC timestamp
- `direction`: `"inflow"` | `"outflow"`
- `amount`: exact positive decimal string in original currency
- `currency`: 3-letter ISO-4217 code (`USD`, `CNY`, `EUR`, etc.)
- `merchant`: normalized counterparty name
- `category`: budget category slug
- `sourceFormat`: `"stripe"` | `"alipay"` | `"wechat"` | `"ofx"` | `"csv"` | `"connector"`
- `sourceFile`: basename of original statement file
- `sourceLine`: 1-based line or block index in original statement
