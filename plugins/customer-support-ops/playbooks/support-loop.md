# Customer Support Operating Loop

## 1. Workspace Discovery & Bootstrap

```sh
ducoro-cli local-folder list --json
ducoro-cli space resources get <space-id> --json
```
If slug `customer-support-ops` exists, reuse it. Otherwise ask the human before initializing `~/.ducoro/workspaces/customer-support-ops` (never inside `~/.ducoro/local-folders/`):
```sh
python3 scripts/init_workspace.py ~/.ducoro/workspaces/customer-support-ops
ducoro-cli local-folder register customer-support-ops ~/.ducoro/workspaces/customer-support-ops \
  --name "Customer Support Ops" --desc "Shared customer tickets, SLA tracking, root causes, and guarded reply logs"
ducoro-cli local-folder inspect customer-support-ops
```
Outside Ducoro, fall back to `CUSTOMER_SUPPORT_OPS_ROOT`.

## 2. Single-Writer Ownership

| Space Role | Exclusive Write Ownership |
|---|---|
| Ingestion & Triage Space | `tickets/tickets.json`, `issues/root-causes.json`, `sla-report.json` |
| Reply & Execution Space | `outbound-queue.json`, `reply-log.jsonl` (append-only) |
| Lead / Policy | `sla-policy.json`, `kb/*.md` |

## 3. Durable Loop & Native Orchestration

1. **Ingest** new tickets/reviews/emails (see `playbooks/channels-and-ingestion.md`).
2. **Triage & detect spikes**:
   ```sh
   python3 scripts/triage_gate.py <workspace> --write-report
   ```
   - Any ticket flagged `requiresHumanApproval: true` (P0 outage, security/privacy, billing/refund, legal threat, 1-star escalation, or SLA breach) must be escalated to the human via `--human <human-id> --ask confirm --request-summary "..."` into Inbox.
3. **Stage, lock, and send replies** via `scripts/reply_guard.py` (see `playbooks/reply-safety-and-boards.md`).
4. **Refresh boards**:
   ```sh
   python3 scripts/build_boards.py <workspace> --board triage-sla-board --board-dir <space-work-root>/boards/<id>
   ```
5. **Schedule & relay**:
   - Periodic triage: `ducoro-cli task create --space <id> --cron "0 */2 * * *" --timezone <IANA-tz> --title "Support Triage Sweep" --instruction "..."`
   - Hand off confirmed P0 bugs to engineering via `ducoro-cli space send`; relay recurring user pain-point spikes to `content-operations` via `ducoro-cli space send`.

## 4. Defect Reporting

If a bundled script or upstream feed schema breaks, show the human a redacted summary first, then submit via:
```sh
ducoro-cli feedback send "[plugin:customer-support-ops@1.0.0] [module:<module>] [location:<step>] <redacted details>"
```
