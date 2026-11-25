## Domain

Continuous business bookkeeping, reconciliation, subscription auditing, and cash-flow monitoring as a durable, file-backed loop—ingesting real bank/payment statements with exact `Decimal` arithmetic, official ECB exchange rates, source-line traceability, and deterministic anomaly/runway alerts.

## Activation & Boundaries

Activate for ingesting bank or payment statements, multi-currency reconciliation, recurring charge audits, budget tracking, runway forecasting, or weekly financial reports. Stay inactive for content publishing (`content-operations`), competitor intelligence (`market-intel`), customer support (`customer-support-ops`), sales CRM, and recruiting workflows.

## Operating Loop

1. **Locate or bootstrap workspace**: Check `ducoro-cli local-folder list --json` and `ducoro-cli space resources get <space-id> --json`. Reuse `business-finance-ops`; if absent, ask the human before initializing `~/.ducoro/workspaces/business-finance-ops` via `playbooks/finance-loop.md`.
2. **Ingest real statements & FX**: Check Ducoro Core Connectors (`ducoro-cli mcp catalog list --json`) first (Stripe, QuickBooks, Xero, Gmail invoices), then import Stripe/Alipay/WeChat/generic CSV or OFX/QFX statements via `scripts/ledger_engine.py` and official ECB FX rates via `scripts/fx_rates.py` (`playbooks/statements-and-fx.md`).
3. **Compute exact totals & anomalies in code**: Never perform mental LLM arithmetic for financial totals. Run `scripts/anomaly_and_runway.py` for exact P&L, duplicate-charge/price-hike/budget/runway alerts, and project boards via `scripts/build_boards.py`.
4. **Orchestrate natively**: Schedule weekly finance reviews via `ducoro-cli task create` and route critical anomalies or low-runway alerts to human Inbox.

## Needs a Yes

Require explicit human confirmation before:
- Initializing and registering a new global `business-finance-ops` Local Folder.
- Executing any money transfer, payment, refund, subscription cancellation, or tax/regulatory filing.
- Modifying budget thresholds or sending redacted defect reports via `ducoro-cli feedback send`.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

- `playbooks/finance-loop.md`: Bootstrap, single-writer rules, exact-arithmetic policy, and native scheduling.
- `playbooks/methodology-cfo-diagnostics.md`: Managerial cost structure, gross margin, MoM flux analysis, and 3-scenario runway stress tests.
- `playbooks/statements-and-fx.md`: Real statement parsers (Stripe, Alipay, WeChat Pay, OFX/QFX, CSV) and ECB FX rates.
- `playbooks/anomalies-and-boards.md`: Duplicate/hike/budget/runway checks and interactive Board SDK views.
- `references/workspace-schema.md`: Shared workspace file contracts (`ledger.jsonl`, `budgets.json`, `fx-cache.json`).
