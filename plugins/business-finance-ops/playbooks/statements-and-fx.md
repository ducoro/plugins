# Real Statement Sources & Official FX Conversion

Never fabricate bank transactions or guess exchange rates.

## Priority 1: Ducoro Core Connectors

Check connected accounting, payment, and inbox tools first:
```sh
ducoro-cli mcp catalog list --json
ducoro-cli mcp catalog status <slug> --json
ducoro-cli mcp catalog tools <slug> --json
```
Typical Connectors: Stripe, QuickBooks, Xero, Mercury, Gmail (electronic invoices & cloud bills), Google Sheets.

## Priority 2: Real Bank & Payment Statement Parsers (`scripts/ledger_engine.py`)

Zero external dependencies; supports real exported files directly:

| Format (`--format`) | Real Export Handled | Key Parsing Behavior |
|---|---|---|
| `stripe` | Stripe Balance Transactions CSV | Exact `Amount`, `Fee`, `Net`, `Currency`, `Created (UTC)`, `id`; preserves fee trail |
| `alipay` | Alipay official bill CSV | Auto-detects `gb18030`/`utf-8-sig`, skips metadata preamble, imports only `收入`/`支出`, skips `不计收支` and closed orders |
| `wechat` | WeChat Pay official bill CSV | Skips 16-line UTF-8 BOM preamble, strips `¥`, imports `收入`/`支出`, preserves transaction ID |
| `ofx` | Standard bank OFX / QFX (Mercury, Chase, BoA, Wise, etc.) | Parses SGML and XML `<STMTTRN>` blocks with `<CURDEF>`, `<DTPOSTED>`, `<TRNAMT>`, `<FITID>`, `<NAME>`, `<MEMO>` |
| `csv` | Any generic bank CSV (with optional `--mapping <json>`) | Maps `date`, `amount`, `currency`, `merchant`, `description`, `id` columns |

All ingested transactions are deduplicated by deterministic `txHash` so importing overlapping monthly statements never double-counts a single cent.

## Priority 3: Official Keyless FX Rates (`scripts/fx_rates.py`)

Uses the European Central Bank public feed via Frankfurter (`https://api.frankfurter.dev/v1/latest` and historical `https://api.frankfurter.dev/v1/<YYYY-MM-DD>`), cached locally in `fx-cache.json`. Falls back to cached or user-entered rates when offline.
