## Domain

Continuous business bookkeeping, reconciliation, subscription auditing, and cash-flow monitoring—ingesting real bank/payment statements with exact `Decimal` arithmetic, official ECB exchange rates, source-line traceability, and deterministic anomaly/runway alerts. Works directly in the human's existing finance folder or current Space `files/`, scaling to a shared directory only when multiple Spaces need to relay files.

## Activation & Boundaries

Activate for ingesting bank or payment statements, multi-currency reconciliation, recurring charge audits, budget tracking, runway forecasting, or weekly financial reports. Stay inactive for content publishing (`content-operations`), competitor intelligence (`market-intel`), customer support (`customer-support-ops`), sales CRM, and recruiting workflows.

## Operating Loop

1. **Resolve working directory (no forced workspace)**: Inspect `ducoro-cli space resources get <space-id> --json` and `ducoro-cli local-folder list --json`. Use the human's existing finance/accounting folder first; for single-Space bookkeeping, use this Space's own `files/` directly. Only propose a shared global Local Folder as a fallback when multiple Spaces must exchange files and no existing folder fits—scoped to the business entity, never duplicated per Bot.
2. **Use Ducoro platform shortcuts directly (skip manual hunting)**:
   - **Billing & accounting connectors**: `ducoro-cli mcp catalog list --json` -> `status <slug> --json` -> `tools <slug> --json` -> `call <slug> <tool> --args-file <path|-> --json` (Stripe, QuickBooks, Xero, Mercury, Gmail invoices).
   - **Weekly/monthly reconciliation cadence (auto-lands in Plan)**: `ducoro-cli task create --space <id> --cron "0 9 * * 5" --timezone <IANA-tz> --title "Weekly Finance Reconciliation" --instruction "..."`.
   - **Anomaly or low-runway alerts into Inbox**: pair `--human <human-id> --ask confirm --request-summary "..."` on `task create`.
   - **Parallel multi-account statement ingestion**: `ducoro-cli job dispatch --agent <agent-id> --name "ingest-<source>" "<prompt>"`.
   - **Interactive finance boards & snapshots**: `ducoro-cli board new --space <id> --title "..." --json` and `ducoro-cli render check|shot --file <board>/index.html --json`.
3. **Ingest statements & compute exact totals in code**: Never perform mental LLM arithmetic for financial totals. Ingest Stripe/Alipay/WeChat/OFX/CSV statements via `scripts/ledger_engine.py`, fetch official ECB FX rates via `scripts/fx_rates.py` (`playbooks/statements-and-fx.md`), run `scripts/anomaly_and_runway.py` for exact P&L, MoM flux, and runway stress tests, and refresh boards via `scripts/build_boards.py`.

## Needs a Yes

Require explicit human confirmation before:
- Executing any money transfer, payment, refund, subscription cancellation, or tax/regulatory filing.
- Modifying budget thresholds or sending redacted defect reports via `ducoro-cli feedback send`.
- Only if registering a new global Local Folder as a cross-Space sharing fallback.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

- `playbooks/finance-loop.md`: Directory resolution, optional cross-Space fallback, single-writer rules, exact-arithmetic policy, and native scheduling.
- `playbooks/methodology-cfo-diagnostics.md`: Managerial cost structure, gross margin, MoM flux analysis, and 3-scenario runway stress tests.
- `playbooks/statements-and-fx.md`: Real statement parsers (Stripe, Alipay, WeChat Pay, OFX/QFX, CSV) and ECB FX rates.
- `playbooks/anomalies-and-boards.md`: Duplicate/hike/budget/runway checks and interactive Board SDK views.
- `references/workspace-schema.md`: Data layout (`ledger.jsonl`, `budgets.json`, `fx-cache.json`).
