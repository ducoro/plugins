## Domain

Continuous customer support and product-feedback operations—ingesting real tickets and reviews, enforcing monotonic P0/security/refund/SLA rules, tracking real 7-day root-cause spikes, and guarding outbound replies against leaks, tampering, or duplicates. Uses the human's existing folder or current Space `files/`, scaling to a shared directory only when multiple Spaces must relay files.

## Activation & Boundaries

Activate for triaging tickets, customer feedback, app reviews, SLA monitoring, guarded replies, or recurring issue spikes. Keep scope strictly within customer support and product-feedback operations. Precedence: **Human live instructions > Bot `PROFILE.md` > local `sla-policy.json` > plugin defaults**.

## Operating Loop

1. **Resolve `<data-dir>` (no forced workspace)**: Inspect `ducoro-cli space info <space-id> --json`, `ducoro-cli space resources get <space-id> --json`, and `ducoro-cli local-folder list --json`. Prefer the human's folder, then this Space's `files/`. Propose a shared Local Folder only for cross-Space sharing—scoped per product, never per Bot.
2. **Use Ducoro platform facilities directly**:
   - **Connectors & fallback**: `ducoro-cli mcp catalog list|status|tools|call` first; fall back to `ingest_feedback.py` or Computer Use / Browser for gated desks & communities (report blocked coverage when locked).
   - **Sweeps & Inbox approvals**: Get `<human-id>` via `ducoro-cli identity get --json`. Schedule sweeps via `ducoro-cli task create --space <id> --cron "0 */2 * * *" --timezone <IANA-tz> --title "Support Triage Sweep" --instruction "..."`. Route high-risk approvals via `--manual --human <human-id> --ask confirm --request-summary "..."` + `ducoro-cli task fire <task-id> --space <id> --json`.
   - **Parallel triage & review**: `ducoro-cli space participant list <space-id> --json`, `ducoro-cli job dispatch --space <id> --agent <agent-id> --name "<name>" "<prompt>"`, `ducoro-cli job status|log <job-id>`.
   - **Boards & relay**: `ducoro-cli board list|new|link`, `ducoro-cli render check --file <board>/index.html --json`, `ducoro-cli space mail send <recipient> --subject "..." --body "..."`.
3. **Run deterministic guards**: Ingest via Connectors or `scripts/ingest_feedback.py` (`playbooks/channels-and-ingestion.md`). Run `scripts/triage_gate.py <data-dir> --write-report` (monotonic escalation, `reply-log.jsonl`-derived status, real `clusterMetrics`). Audit high-risk replies and escalations in an isolated read-only job, enforce hash-pinned approval and follow-up rules via `scripts/reply_guard.py`, and project boards via `scripts/build_boards.py`.

## Needs a Yes

Require explicit human confirmation before:
- Sending replies on P0/P1, security/privacy, refund/billing, legal, VIP, 1-star, SLA-breached, or escalated tickets, or mass mentions (`@everyone`/broadcasts); clean routine P2/P3 drafts stage as `ready_to_send` unless stricter rules require approval.
- Making roadmap, SLA, refund, or legal commitments, or sending redacted defects for this plugin via `ducoro-cli feedback send`.
- Registering a new global Local Folder as a cross-Space sharing fallback.
- Always defer to stricter rules in higher-precedence instructions, Bot `PROFILE.md`, or `sla-policy.json`.

## Resources & Tools

- `playbooks/support-loop.md`: Precedence, directory resolution, single-writer rules, CLI loop, and defect reporting exclusions.
- `playbooks/methodology-voc-and-deflection.md`: Reply boundaries, 6-element escalations, isolated VoC review, and KB deflection.
- `playbooks/channels-and-ingestion.md`: Connectors, GitHub Issues (`--state`/`--limit`), `.eml`/`.mbox`, CSV/JSONL, and desks.
- `playbooks/reply-safety-and-boards.md`: Hash-pinned reply guard, cooldown unlocking, timeout/tamper recovery, isolated review, and Boards.
- `references/workspace-schema.md`: Data layout, `sla-policy.json`, `issues/root-causes.json`, and ticket/report schemas.
