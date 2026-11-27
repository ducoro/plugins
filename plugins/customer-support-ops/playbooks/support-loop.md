# Customer Support Operating Loop

## 1. Authority & Rule Precedence

Always resolve policy conflicts in this exact order:

`Human live instructions > Bot PROFILE.md > local sla-policy.json > plugin defaults`

- Routine P2/P3 tickets with no risk flags, no SLA breach, and no commitment language stage as `ready_to_send` by default.
- High-risk tickets (P0/P1, security/privacy, billing/refund, legal/regulatory, VIP, 1-star review, SLA breach, or any ticket with explicit `riskFlags` / `escalationReasons`) always require explicit human confirmation (`requiresHumanApproval: true`).
- If the local `sla-policy.json` sets `"requireApprovalForRoutine": true`, or if the Bot's `PROFILE.md` or human instructions require approval for all outbound replies, every draft enters `awaiting_approval`.

## 2. Directory Resolution (Workspace Is Fallback-Only)

```sh
ducoro-cli space info <space-id> --json
ducoro-cli space resources get <space-id> --json
ducoro-cli local-folder list --json
```

Choose `<data-dir>` in strict priority order:

1. **Existing folder first**: If the human already maintains a support/feedback folder (or this Space already mounts one), pass that directory directly as `<data-dir>`—never create a shadow directory.
2. **Single-Space default**: If support runs within one Space without cross-Space file sharing, store files inside this Space's own `files/` (located via `ducoro-cli space info <space-id> --json`, e.g., `<space-work-root>/files/support-ops`). Run `python3 scripts/init_workspace.py <data-dir>` only on first initialization (it creates `tickets/`, `issues/`, `kb/`, and JSON schemas without creating `boards/` inside `<data-dir>`).
3. **Cross-Space fallback only**: Only when multiple Spaces must share the same support files and no folder exists yet, ask the human before creating a shared directory scoped to that product/team (e.g., `~/.ducoro/workspaces/<product-support-slug>`, never inside `~/.ducoro/local-folders/`) and registering it:
   ```sh
   python3 scripts/init_workspace.py ~/.ducoro/workspaces/<product-support-slug>
   ducoro-cli local-folder register <product-support-slug> <resolved-absolute-path> \
     --name "<Product Support Ops>" --desc "Shared customer tickets, SLA tracking, root causes, and guarded reply logs"
   ducoro-cli local-folder inspect <product-support-slug>
   ```
   Multiple Bots working on the same product share that single `<data-dir>`—never create one directory per Bot.

## 3. Single-Writer Ownership

| Role | Exclusive Write Ownership |
|---|---|
| Ingestion & Triage | `tickets/tickets.json`, `issues/root-causes.json`, `sla-report.json` |
| Reply & Execution (`reply_guard.py`) | `outbound-queue.json`, `reply-log.jsonl` (append-only) |
| Lead / Policy | `sla-policy.json`, `kb/*.md` |

- `reply_guard.py` never writes `tickets/tickets.json`. Both `triage_gate.py` and `build_boards.py` derive current replied state directly from `reply-log.jsonl` compared against `lastInboundAt` / `createdAt`.
- Boards live under the displaying Space's own `boards/<board-id>/`, never inside `<data-dir>`.

## 4. Durable Loop & Native Ducoro Orchestration

1. **Ingest** real tickets/reviews/emails (see `playbooks/channels-and-ingestion.md`).
2. **Run deterministic triage & real cluster metrics**:
   ```sh
   python3 scripts/triage_gate.py <data-dir> --write-report
   ```
   - `triage_gate.py` is strictly monotonic: it never downgrades a human- or model-assigned `priority`, never clears `requiresHumanApproval: true`, and preserves existing `escalationReasons`.
   - If `sla-policy.json` is absent, it gracefully falls back to built-in default thresholds.
3. **Route immediate high-risk escalations into Inbox**:
   ```sh
   ducoro-cli identity get --json
   ducoro-cli task create --space <space-id> --manual \
     --title "Approve P0/Escalated Support Reply" \
     --instruction "Review staged draft <draft-id> for <ticket-id> and confirm send or edits." \
     --human <human-id> --ask confirm \
     --request-summary "P0/escalated reply awaiting approval for <ticket-id>"
   ducoro-cli task fire <task-id> --space <space-id> --json
   ```
4. **Parallel backlog triage & isolated read-only review**:
   ```sh
   ducoro-cli space participant list <space-id> --json
   ducoro-cli job dispatch --space <space-id> --agent <agent-id> \
     --name "triage-batch" "Classify unclustered tickets in <data-dir> and write proposed rootCauseId tags."
   ducoro-cli job status <job-id> --json
   ducoro-cli job log <job-id>
   ```
5. **Stage, review, lock, and send replies** via `scripts/reply_guard.py` (see `playbooks/reply-safety-and-boards.md`).
6. **Manage & refresh Boards**:
   ```sh
   ducoro-cli board list --space <space-id> --json
   ducoro-cli board new --space <space-id> --title "Support Triage & SLA Queue" --json
   ducoro-cli board link --space <space-id> --board boards/<board-id> --json
   python3 scripts/build_boards.py <data-dir> --board triage-sla-board --board-dir <space-work-root>/boards/<board-id> --overwrite-templates
   ```
7. **Schedule recurring sweeps & cross-Space handoffs**:
   - Periodic sweep (lands in Plan):
     ```sh
     ducoro-cli task create --space <space-id> --cron "0 */2 * * *" --timezone <IANA-tz> \
       --title "Support Triage Sweep" \
       --instruction "Ingest new tickets into <data-dir>, run triage_gate.py --write-report, refresh boards, and escalate any P0/SLA breach."
     ```
   - Cross-Space handoff (confirmed P0 bugs to engineering or verified pain-point spikes to product/editorial Spaces):
     ```sh
     ducoro-cli space mail send <recipient> \
       --subject "Escalation: <rootCauseId> (<uniqueCustomers> customers affected)" \
       --body "<6-element engineering or VoC handoff package>"
     ```

## 5. Plugin Defect Reporting (`ducoro-cli feedback send`)

Use `ducoro-cli feedback send` **only** when a bundled script, board template, or plugin contract inside `customer-support-ops` itself is broken:

- **Do NOT use `feedback send` for**: ordinary customer tickets, product bugs belonging to the user's own app, third-party helpdesk outages, or missing local credentials/tokens.
- Always show the human a redacted summary first and obtain explicit confirmation before sending:
  ```sh
  ducoro-cli feedback send "[plugin:customer-support-ops@<version>] [module:<module>] [location:<step>] <redacted details>"
  # Read <version> from <plugin-root>/plugin.json
  ```
