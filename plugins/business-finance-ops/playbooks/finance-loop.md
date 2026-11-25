# Finance Operating Loop

## 1. Workspace Discovery & Bootstrap

```sh
ducoro-cli local-folder list --json
ducoro-cli space resources get <space-id> --json
```
Reuse slug `business-finance-ops` if registered. Otherwise ask the human before initializing `~/.ducoro/workspaces/business-finance-ops` (never inside `~/.ducoro/local-folders/`):
```sh
python3 scripts/init_workspace.py ~/.ducoro/workspaces/business-finance-ops --base-currency USD
ducoro-cli local-folder register business-finance-ops ~/.ducoro/workspaces/business-finance-ops \
  --name "Business Finance Ops" --desc "Shared Decimal financial ledger, FX cache, budgets, and anomaly audits"
ducoro-cli local-folder inspect business-finance-ops
```
Outside Ducoro, fall back to `BUSINESS_FINANCE_OPS_ROOT`.

## 2. Exact-Arithmetic Iron Rule

- **Never compute sums, net cash flow, FX conversions, margins, or runway in LLM prose.** Every reported number must come verbatim from `scripts/ledger_engine.py`, `scripts/fx_rates.py`, and `scripts/anomaly_and_runway.py`, which use `decimal.Decimal` end-to-end.
- Every ledger row preserves `sourceFile` and `sourceLine` (or upstream `externalId`) so any reported number traces back to the exact bank/payment statement line.

## 3. Single-Writer Ownership

| Space Role | Exclusive Write Ownership |
|---|---|
| Ingestion Space | `raw-statements/*`, `ledger.jsonl` (append-only via `ledger_engine.py`), `fx-cache.json` |
| Audit & Reporting Space | `finance-report.json`, `reports/*.md` |
| Lead / Policy | `budgets.json`, `accounts.json`, `category-rules.json` |

## 4. Native Orchestration & Defect Reporting

- Weekly review schedule: `ducoro-cli task create --space <id> --cron "0 9 * * 5" --timezone <IANA-tz> --title "Weekly Finance Reconciliation" --instruction "..."`
- Escalate duplicate charges, unexpected vendor price hikes, budget breaches, or low-runway warnings via `--human <human-id> --ask confirm --request-summary "..."` into Inbox.
- **No autonomous money movement**: Never initiate transfers, payments, refunds, or subscription cancellations without explicit human execution/approval.
- Report script or parser format regressions (redacted, after human approval) via:
  ```sh
  ducoro-cli feedback send "[plugin:business-finance-ops@1.0.0] [module:<module>] [location:<step>] <redacted details>"
  ```
