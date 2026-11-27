# Business Finance Ops

Deterministic `Decimal` bookkeeping, multi-currency statement reconciliation, subscription anomaly auditing, and cash-flow runway tracking for Ducoro.

## What It Solves

- **Real statement & connector parsers (`scripts/ledger_engine.py`)**: Zero-dependency parsers for Stripe Balance CSV (including fee refunds), Alipay CSV (GB18030/UTF-8), WeChat Pay CSV, standard bank OFX/QFX files, custom-mapped generic CSVs, and normalized Connector JSON (`--format connector`). Uses exact `decimal.Decimal` arithmetic, `--timezone` handling for naive timestamps, inflow/outflow `category-rules.json` classification, `txHash` deduplication, `sourceFile:sourceLine` traceability, fail-closed `ledger.jsonl` validation, file-locked writes, and `--stage-out` parallel staging.
- **Official keyless FX & manual overrides (`scripts/fx_rates.py`)**: Fetches latest or transaction-date exchange rates from the public European Central Bank feed (`api.frankfurter.dev`) and supports `--set-rate` manual entries for non-ECB currencies, stored with locked atomic writes in `fx-cache.json`.
- **Deterministic anomaly & runway engine (`scripts/anomaly_and_runway.py`)**: Detects duplicate charges, recurring vendor price hikes, budget threshold breaches, and low cash runway across both `base` and `recurringOnly` scenarios—with configurable `costClassMap` overrides for non-SaaS businesses and zero LLM mental math.
- **Interactive shadcn/ui Boards (`scripts/build_boards.py`)**: Projects `finance-overview-board` and `anomaly-audit-board` one-way from the active `<data-dir>` into Space Boards with host theme/locale sync and live revalidation.

## License

Apache License 2.0. See [LICENSE](LICENSE).
