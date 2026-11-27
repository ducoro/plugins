# Real Statement Sources & Official FX Conversion

Never fabricate bank transactions or guess exchange rates.

## Priority 1: Ducoro Core Connectors

Check connected accounting, payment, and inbox tools first:
```sh
ducoro-cli mcp catalog list --json
ducoro-cli mcp catalog status <slug> --json
ducoro-cli mcp catalog tools <slug> --json
ducoro-cli mcp catalog call <slug> <tool> --args-file <args.json> --space <space-id> --json
```
Typical Connectors: Stripe, QuickBooks, Xero, Mercury, Gmail (electronic invoices and cloud bills), Google Sheets. Normalize fetched transactions into the Connector JSON schema (`references/workspace-schema.md`) and ingest with `--format connector`.

## Priority 2: Statement & Connector Ingestion (`scripts/ledger_engine.py`)

Zero external dependencies; handles real exported files and normalized Connector JSON directly with exact `Decimal` arithmetic, deterministic `txHash` deduplication, `fcntl.flock` write locking, and fail-closed `ledger.jsonl` validation.

### Full CLI Reference

```sh
python3 scripts/ledger_engine.py <data-dir> \
  --file <path-to-statement-or-json> \
  --format stripe|alipay|wechat|ofx|csv|connector \
  [--default-currency USD] \
  [--timezone UTC|Asia/Shanghai|+08:00] \
  [--mapping <column-mapping.json>] \
  [--stage-out <isolated-staged.json>]
```

| Format (`--format`) | Source Handled | Key Parsing Behavior |
|---|---|---|
| `stripe` | Stripe Balance Transactions CSV | Exact `Amount`, `Fee`, `Net`, `Currency`, `Created (UTC)`, `id`. Positive `Fee` logs an outflow (`payment_fees`); negative `Fee` (refunded fee) logs an inflow (`payment_fees`, `costClass: one_time_revenue`) so net balances stay exact. |
| `alipay` | Alipay official bill CSV | Auto-detects `gb18030`/`utf-8-sig`, skips metadata preamble, imports `收入`/`支出`, skips `不计收支` and closed/failed/fully-refunded orders. Pass `--timezone Asia/Shanghai` for local timestamps. |
| `wechat` | WeChat Pay official bill CSV | Skips UTF-8 BOM preamble, strips `¥`, imports `收入`/`支出`, preserves transaction ID. Pass `--timezone Asia/Shanghai` for local timestamps. |
| `ofx` | Standard bank OFX / QFX (Mercury, Chase, BoA, Wise, etc.) | Parses SGML and XML `<STMTTRN>` blocks (`<CURDEF>`, `<DTPOSTED>` including optional `[offset:TZ]`, `<TRNAMT>`, `<FITID>`, `<NAME>`, `<MEMO>`). |
| `csv` | Any generic bank or card CSV | Supports custom `--mapping <column-mapping.json>` and optional `category`/`costClass` columns. |
| `connector` | Normalized Connector JSON or `--stage-out` staging files | Reads top-level JSON array or object (`transactions`/`items`/`data`/`records`); preserves existing `sourceFormat`/`sourceFile`/`sourceLine` on staged files. |

### Key Options & Examples

1. **Local timezones for naive timestamps (`--timezone`)**:
   - Naive timestamps (no offset in source file) are tagged with `--timezone` instead of being forced to UTC, preserving local accounting dates:
     ```sh
     python3 scripts/ledger_engine.py <data-dir> \
       --file <data-dir>/raw-statements/alipay-2026-11.csv \
       --format alipay \
       --timezone Asia/Shanghai
     ```
2. **Custom column mapping JSON (`--mapping`)** for `--format csv`:
   Create a JSON file mapping standard field names to CSV headers (case-insensitive):
   ```json
   {
     "date": "Posted Date",
     "amount": "Signed Amount",
     "currency": "Currency Code",
     "merchant": "Counterparty Name",
     "description": "Memo",
     "id": "Reference ID",
     "category": "Category",
     "costClass": "Cost Class"
   }
   ```
   Then run:
   ```sh
   python3 scripts/ledger_engine.py <data-dir> \
     --file <data-dir>/raw-statements/bank-2026-11.csv \
     --format csv \
     --default-currency USD \
     --timezone America/New_York \
     --mapping <data-dir>/raw-statements/bank-mapping.json
   ```
3. **Connector JSON ingestion (`--format connector`)**:
   ```sh
   python3 scripts/ledger_engine.py <data-dir> \
     --file <data-dir>/raw-statements/mercury-connector.json \
     --format connector \
     --default-currency USD
   ```
4. **Parallel staging (`--stage-out`)**:
   Parallel `job dispatch` workers parse into isolated JSON files without touching `ledger.jsonl`, then the single-writer Ingestion Space merges each staged file via `--format connector`:
   ```sh
   python3 scripts/ledger_engine.py <data-dir> \
     --file <data-dir>/raw-statements/stripe-2026-11.csv \
     --format stripe \
     --stage-out <data-dir>/raw-statements/staged-stripe.json
   python3 scripts/ledger_engine.py <data-dir> \
     --file <data-dir>/raw-statements/staged-stripe.json \
     --format connector
   ```
5. **Inflow & outflow classification (`category-rules.json`)**:
   - Both `inflow` and `outflow` transactions are matched against `category-rules.json`. Rules may restrict `direction` (`inflow`, `outflow`, or `any`) and optionally set `costClass` (e.g., `one_time_revenue` for grants, setup fees, or asset sales). Unmatched inflows default to `revenue`; unmatched outflows default to `uncategorized`.

## Priority 3: Official Keyless FX & Manual Non-ECB Rates (`scripts/fx_rates.py`)

Uses the European Central Bank public feed via Frankfurter (`https://api.frankfurter.dev/v1/latest` and historical `https://api.frankfurter.dev/v1/<YYYY-MM-DD>`), written atomically under `fcntl.flock` to `fx-cache.json`.

### Fetch Official ECB Rates

```sh
python3 scripts/fx_rates.py <data-dir> \
  --base USD \
  --symbols CNY,EUR,GBP,JPY,HKD,SGD \
  --date latest
```
For exact historical transaction-date rates, pass `--date YYYY-MM-DD`.

### Record Manual Rates for Non-ECB Currencies (`--set-rate`)

For currencies not published by the ECB (such as `TWD`, `VND`, `AED`, `SAR`, `NGN`) or contractually fixed settlement rates, record exact `1 base = RATE foreign` quotes with `--set-rate` (repeatable or comma-separated):
```sh
python3 scripts/fx_rates.py <data-dir> \
  --base USD \
  --date 2026-11-24 \
  --set-rate TWD=32.50 \
  --set-rate VND=25400
```
Manual entries merge into the snapshot alongside ECB currencies without wiping existing ECB symbols. If a ledger transaction uses a currency absent from `fx-cache.json`, `anomaly_and_runway.py` fails closed rather than assuming `1:1`.
