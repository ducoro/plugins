# Business Finance Ops

Deterministic `Decimal` bookkeeping, statement reconciliation, subscription anomaly auditing, and cash-flow runway tracking for Ducoro.

## What It Solves

- **Real statement parsers (`scripts/ledger_engine.py`)**: Zero-dependency parsers for Stripe Balance CSV, Alipay CSV (GB18030/UTF-8), WeChat Pay CSV, standard bank OFX/QFX files, and custom-mapped bank CSVs. Uses exact `decimal.Decimal` arithmetic, deterministic `txHash` deduplication, and `sourceFile:sourceLine` traceability.
- **Official keyless FX conversion (`scripts/fx_rates.py`)**: Fetches latest or exact transaction-date exchange rates from the public European Central Bank feed (`api.frankfurter.dev`) with local caching in `fx-cache.json`.
- **Deterministic anomaly & runway engine (`scripts/anomaly_and_runway.py`)**: Detects duplicate charges, recurring vendor price hikes, budget threshold breaches (>=80% / >=100%), and cash runway warnings in Python code—never via LLM mental math.
- **Interactive shadcn/ui Boards (`scripts/build_boards.py`)**: Projects `finance-overview-board` and `anomaly-audit-board` one-way from the workspace.

## License

Apache License 2.0. See [LICENSE](LICENSE).
