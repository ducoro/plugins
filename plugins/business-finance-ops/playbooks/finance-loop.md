# Finance Operating Loop

## 1. Authority Precedence

Resolve any conflict in accounting rules, categorization, reporting cadence, or escalation policy using this strict hierarchy:

**Human live instructions > Bot `PROFILE.md` > existing accounting conventions in `<data-dir>` > plugin defaults.**

## 2. Directory Resolution (Workspace Is Fallback-Only)

Inspect the current Space and registered folders before touching any files:

```sh
ducoro-cli space info <space-id> --json
ducoro-cli space resources get <space-id> --json
ducoro-cli local-folder list --json
```

Choose `<data-dir>` in this priority order:
1. **Existing folder first**: If the human already maintains a finance/accounting folder (or this Space already mounts one), operate directly inside it—never create a parallel workspace.
2. **Single-Space default**: If bookkeeping lives inside one Space without cross-Space file sharing, place data inside this Space's own `files/` (located via `ducoro-cli space info <space-id> --json`, e.g., `<space-work-root>/files/finance`). Run `python3 scripts/init_workspace.py <data-dir> --base-currency USD` only on first initialization; `init_workspace.py` creates only ledger/config files and never writes a `boards/` folder into `<data-dir>`.
3. **Cross-Space fallback only**: Only when multiple Spaces must exchange the same ledger files and no existing folder fits, ask the human before creating a directory scoped to the business entity (e.g., `~/.ducoro/workspaces/<entity-finance-slug>`, never inside `~/.ducoro/local-folders/`) and registering it as a global Local Folder:
   ```sh
   python3 scripts/init_workspace.py ~/.ducoro/workspaces/<entity-finance-slug> --base-currency USD
   ducoro-cli local-folder register <entity-finance-slug> <resolved-absolute-path> \
     --name "<Entity Finance>" --desc "Shared Decimal financial ledger, FX cache, budgets, and anomaly audits"
   ducoro-cli local-folder inspect <entity-finance-slug>
   ```
   Multiple Bots supporting the same entity share that one directory—never create one workspace per Bot, and never merge unrelated entities into one slug. Outside Ducoro, pass the chosen `<data-dir>` path explicitly to each script.

## 3. Exact-Arithmetic & Fail-Closed Iron Rules

- **Never compute totals, net cash flow, FX conversions, margins, MoM variance, or runway in LLM prose.** Every reported number must come verbatim from `scripts/ledger_engine.py`, `scripts/fx_rates.py`, and `scripts/anomaly_and_runway.py`, which use `decimal.Decimal` end-to-end.
- **Fail-closed on ledger corruption**: If `ledger.jsonl` contains any malformed JSON line or record missing `txHash`, both `ledger_engine.py` and `anomaly_and_runway.py` immediately fail closed with a structured JSON error on stderr pointing to the exact `<file>:<line>`—never silently skip lines. See `references/workspace-schema.md` for recovery steps.
- Every ledger row preserves `sourceFile` and `sourceLine` (plus `externalId` when present) so any reported number traces back to the exact bank, payment, or connector source line.

## 4. Concurrency-Safe Single-Writer Ownership

| Role / Space | Exclusive Write Ownership |
|---|---|
| Ingestion Space (single writer) | `raw-statements/*`, `ledger.jsonl` (append-only via `ledger_engine.py`), `fx-cache.json` (via `fx_rates.py`) |
| Audit & Reporting Space | `finance-report.json`, `reports/*.md` |
| Lead / Policy | `budgets.json`, `accounts.json`, `category-rules.json` |

### Safe Parallel Multi-Account Ingestion (`job dispatch` + Serial Merge)

Both `ledger_engine.py` and `fx_rates.py` guard file mutations with `fcntl.flock` and atomic writes, **and** multi-source collection should still keep `ledger.jsonl` strictly single-writer:

1. Check seated Agents first:
   ```sh
   ducoro-cli space participant list <space-id> --json
   ```
2. Dispatch parallel worker jobs to fetch Connector payloads or pre-parse raw statements into **isolated staging files** using `--stage-out` (never writing directly to `ledger.jsonl` or `fx-cache.json` from parallel workers):
   ```sh
   ducoro-cli job dispatch --space <space-id> --agent <agent-id> --name "stage-stripe" \
     "Run python3 scripts/ledger_engine.py <data-dir> --file <raw-stripe.csv> --format stripe --stage-out <data-dir>/raw-statements/staged-stripe.json"
   ducoro-cli job status <job-id> --json
   ducoro-cli job log <job-id>
   ```
3. Once staging jobs settle, the owning Ingestion Space serially merges each staged JSON file into `ledger.jsonl` via `python3 scripts/ledger_engine.py <data-dir> --file <staged.json> --format connector` (preserving original `sourceFormat`, `sourceFile`, and `sourceLine`), then runs `fx_rates.py` and `anomaly_and_runway.py`.

## 5. Period-Close Reconciliation & Isolated Read-Only Verification

To verify that close numbers are self-consistent across independent dimensions—rather than trusting a single pass—run these three checks before delivering a period close or escalating a high-severity alert:

1. **Cash Balance Reconciliation (Ledger vs Real Statement Ending Balances)**:
   - Compare `openingCash + ledgerNetCashFlow (inflow - outflow)` against the real ending balances reported by bank/payment statements or Connectors in `accounts.json` (`cashBalances`).
   - If a variance remains, itemize the exact gap (in-transit payouts, unrecorded fees, pending authorizations, or FX revaluation differences). Never plug an unexplained variance to force zero.
2. **Inter-Account Transfer Elimination**:
   - Identify offsetting movements between owned accounts (e.g., Stripe payout settling into Mercury checking, Alipay balance/Yu'e Bao transfers, internal treasury sweeps).
   - Verify these internal transfers are excluded or explicitly neutralized so they never inflate `recurring_revenue` or double-count operating outflows.
3. **Isolated Read-Only Audit Environment (`job dispatch` + `render check|shot`)**:
   - Before publishing a monthly close or acting on a high-severity anomaly (`duplicate_charge`, `low_runway`, `budget_exceeded`), dispatch a fresh read-only review job to a seated Agent with zero authoring bias:
     ```sh
     ducoro-cli job dispatch --space <space-id> --agent <reviewer-agent-id> --name "audit-close-2026-11" \
       "Read-only audit: sample top inflows, top outflows, and all high-severity alerts in <data-dir>/finance-report.json; verify each against raw <sourceFile>:<sourceLine> originals and fx-cache.json rates; verify cash reconciliation and inter-account transfers; report any discrepancy."
     ducoro-cli job status <job-id> --json
     ducoro-cli job log <job-id>
     ```
   - Visually verify projected Boards with `ducoro-cli render check` and `ducoro-cli render shot` (see `playbooks/anomalies-and-boards.md`) so the rendered KPIs match `finance-report.json` verbatim.

## 6. Native Orchestration, Escalation & Cross-Space Relay

- **Discover human recipient ID** before creating human-routed tasks:
  ```sh
  ducoro-cli identity get --json
  ```
- **Recurring close cadence (lands in Plan)**:
  ```sh
  ducoro-cli task create --space <space-id> --cron "0 9 * * 5" --timezone <IANA-tz> \
    --title "Weekly Finance Reconciliation" \
    --instruction "Ingest new statements, refresh FX, run anomaly_and_runway.py, reconcile cash balances, and refresh finance boards." --json
  ```
- **Immediate Inbox escalation for high-risk alerts** (`duplicate_charge`, `vendor_price_hike`, `budget_exceeded`, `low_runway`):
  ```sh
  ducoro-cli task create --space <space-id> --manual \
    --title "Finance Alert Review" \
    --instruction "Present verified anomaly evidence with sourceFile:sourceLine and await human authorization." \
    --human <human-id> --ask confirm \
    --request-summary "Review high-severity finance anomaly and confirm next action" --json
  ducoro-cli task fire <task-id> --space <space-id> --json
  ```
- **Cross-Space executive or finance relay** (when notifying another Space Lead or seated Agent):
  ```sh
  ducoro-cli space mail send <recipient> --subject "Monthly Close Summary (2026-11)" --body "<verified summary with key metrics and open items>"
  ```
- **No autonomous money movement**: Never initiate transfers, payments, refunds, or subscription cancellations without explicit human execution/approval.
- **Redacted defect reports** (after human approval; read `<version>` from `<plugin-root>/plugin.json`):
  ```sh
  ducoro-cli feedback send "[plugin:business-finance-ops@<version>] [module:<module>] [location:<step>] <redacted details>"
  ```
