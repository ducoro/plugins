## Domain

Continuous business bookkeeping, multi-currency reconciliation, subscription anomaly auditing, and cash-runway monitoring using exact `Decimal` arithmetic, ECB/manual FX rates, `sourceFile:sourceLine` traceability, and deterministic risk checks. Operates directly in the human's existing finance folder or current Space `files/`, using a shared directory only for cross-Space exchange.

## Activation & Boundaries

Activate for statement/connector ingestion, reconciliation, duplicate/hike audits, budgets, managerial P&L and flux diagnostics, runway stress tests, or financial closes. Stay strictly within bookkeeping and diagnostics with no autonomous money movement. Precedence: Human live instructions > Bot `PROFILE.md` > existing accounting conventions > plugin defaults.

## Operating Loop

1. **Resolve directory (no forced workspace)**: Run `ducoro-cli space info <space-id> --json`, `ducoro-cli space resources get <space-id> --json`, and `ducoro-cli local-folder list --json`. Prefer the human's existing folder, then this Space's `files/`; propose a shared global Local Folder only as an entity-scoped cross-Space fallback—never per Bot.
2. **Ducoro infrastructure shortcuts**:
   - **Connectors**: `ducoro-cli mcp catalog list --json`, `ducoro-cli mcp catalog status|tools <slug> --json`, `ducoro-cli mcp catalog call <slug> <tool> --args-file <path|-> --json`.
   - **Schedules & Inbox**: Get `<human-id>` via `ducoro-cli identity get --json`. Cadence: `ducoro-cli task create --space <id> --cron "0 9 * * 5" --timezone <IANA-tz> --title "..." --instruction "..."`. Immediate alert: `ducoro-cli task create --space <id> --manual --human <human-id> --ask confirm --request-summary "..." --instruction "..." --json` then `ducoro-cli task fire <task-id> --space <id> --json`.
   - **Parallel staging & audit**: `ducoro-cli space participant list <space-id> --json`, `ducoro-cli job dispatch --space <id> --agent <agent-id> --name "<name>" "<prompt>"`, `ducoro-cli job status|log <job-id>`. Parallel jobs only fetch or `--stage-out` into isolated files; the owning Space merges serially as single writer into `ledger.jsonl` and `fx-cache.json`.
   - **Boards & relay**: `ducoro-cli board list|new|link`, `ducoro-cli render check|shot --file <board>/index.html --json`, `ducoro-cli space mail send <recipient> --subject "..." --body "..."`.
3. **Exact pipeline & verification**: Never compute totals, FX, margins, or runway mentally. Run `scripts/ledger_engine.py`, `scripts/fx_rates.py`, `scripts/anomaly_and_runway.py`, and `scripts/build_boards.py`. Before closes or high-severity alerts, reconcile ending cash, eliminate inter-account transfers, and dispatch an isolated read-only audit against `sourceFile:sourceLine` originals and rendered boards.

## Needs a Yes

Require explicit human confirmation before:
- Money transfers, payments, refunds, subscription cancellations, or tax/regulatory filings.
- Changing budget/anomaly thresholds, registering a cross-Space Local Folder fallback, or sending redacted defects via `ducoro-cli feedback send`.
- Always defer to stricter rules in the human's live instructions or Bot `PROFILE.md`.

## Resources & Tools

- `playbooks/finance-loop.md`: Directory priority, precedence, parallel staging, close reconciliation, read-only audit, and CLI orchestration.
- `playbooks/methodology-cfo-diagnostics.md`: Configurable cost classes, gross margin, MoM flux, runway scenarios, and optional lenses.
- `playbooks/statements-and-fx.md`: CLI guide for `scripts/ledger_engine.py` (Stripe/Alipay/WeChat/OFX/CSV/connector) and `scripts/fx_rates.py` (ECB + manual).
- `playbooks/anomalies-and-boards.md`: Risk detectors (`base`/`recurringOnly` `low_runway`, duplicates, hikes, budgets) and Board projection/checks.
- `references/workspace-schema.md`: Config/ledger/connector schemas and reversal/corruption recovery.
