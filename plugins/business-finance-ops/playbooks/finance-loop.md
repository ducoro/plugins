# Finance Operating Loop

## 1. Directory Resolution (Workspace Is Fallback-Only)

```sh
ducoro-cli space resources get <space-id> --json
ducoro-cli local-folder list --json
```
Follow this strict priority based on the human's actual setup:
1. **Existing folder first**: If the human already keeps a finance/accounting folder (or this Space already mounts one), use it directly—never create a second workspace.
2. **Single-Space default**: If bookkeeping runs inside one Space without cross-Space file sharing, store files directly inside this Space's own `files/` (for example `files/finance/`). Run `python3 scripts/init_workspace.py <data-dir> --base-currency USD` only when initializing the ledger schema for the first time.
3. **Cross-Space fallback only**: Only when multiple Spaces must share the same ledger files and no existing folder exists yet, ask the human before creating a shared directory scoped to that business entity (e.g., `~/.ducoro/workspaces/<entity-finance-slug>`, never inside `~/.ducoro/local-folders/`) and registering it as a global Local Folder:
   ```sh
   python3 scripts/init_workspace.py ~/.ducoro/workspaces/<entity-finance-slug> --base-currency USD
   ducoro-cli local-folder register <entity-finance-slug> <resolved-absolute-path> \
     --name "<Entity Finance>" --desc "Shared Decimal financial ledger, FX cache, budgets, and anomaly audits"
   ducoro-cli local-folder inspect <entity-finance-slug>
   ```
   Multiple Bots working on the same entity share that one directory—never create one workspace per Bot, and never merge unrelated companies/entities into one hardcoded slug.
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
  ducoro-cli feedback send "[plugin:business-finance-ops@1.1.1] [module:<module>] [location:<step>] <redacted details>"
  ```
