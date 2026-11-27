# Customer Support Operating Loop

## 1. Directory Resolution (Workspace Is Fallback-Only)

```sh
ducoro-cli space resources get <space-id> --json
ducoro-cli local-folder list --json
```
Follow this strict priority based on the human's actual setup:
1. **Existing folder first**: If the human already keeps a support/feedback folder (or this Space already mounts one), use it directly—never create a second workspace.
2. **Single-Space default**: If triage runs inside one Space without cross-Space file sharing, store files directly inside this Space's own `files/` (for example `files/support-ops/`). Run `python3 scripts/init_workspace.py <data-dir>` only when initializing the directory schema for the first time.
3. **Cross-Space fallback only**: Only when multiple Spaces must share the same files and no existing folder exists yet, ask the human before creating a shared directory scoped to that product/team (e.g., `~/.ducoro/workspaces/<product-support-slug>`, never inside `~/.ducoro/local-folders/`) and registering it as a global Local Folder:
   ```sh
   python3 scripts/init_workspace.py ~/.ducoro/workspaces/<product-support-slug>
   ducoro-cli local-folder register <product-support-slug> <resolved-absolute-path> \
     --name "<Product Support Ops>" --desc "Shared customer tickets, SLA tracking, root causes, and guarded reply logs"
   ducoro-cli local-folder inspect <product-support-slug>
   ```
   Multiple Bots working on the same product share that one directory—never create one workspace per Bot, and never merge unrelated products into one hardcoded slug.
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
   - Hand off confirmed P0 bugs to engineering Spaces via `ducoro-cli space mail send`; relay recurring user pain-point spikes to downstream product or editorial Spaces via `ducoro-cli space mail send`.

## 4. Defect Reporting

If a bundled script or upstream feed schema breaks, show the human a redacted summary first, then submit via:
```sh
ducoro-cli feedback send "[plugin:customer-support-ops@<version>] [module:<module>] [location:<step>] <redacted details>"
# Read <version> from <plugin-root>/plugin.json
```
