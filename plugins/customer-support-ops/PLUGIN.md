## Domain

Continuous customer support and product-feedback operations—ingesting real tickets and reviews, enforcing deterministic P0/security/refund escalation and SLA rules, detecting root-cause spikes, and guarding outbound replies against leaks or duplicates. Works directly in the human's existing support folder or current Space `files/`, scaling to a shared directory only when multiple Spaces need to relay files.

## Activation & Boundaries

Activate for triaging user feedback, tickets, app reviews, SLA monitoring, drafting guarded customer replies, or tracking recurring issue spikes. Stay inactive for content publishing (`content-operations`), competitor intelligence (`market-intel`), financial bookkeeping (`business-finance-ops`), sales CRM, and recruiting workflows.

## Operating Loop

1. **Resolve working directory (no forced workspace)**: Inspect `ducoro-cli space resources get <space-id> --json` and `ducoro-cli local-folder list --json`. Use the human's existing support folder first; for single-Space triage, use this Space's own `files/` directly. Only propose a shared global Local Folder as a fallback when multiple Spaces must exchange files and no existing folder fits—scoped to the product/team, never duplicated per Bot.
2. **Use Ducoro platform shortcuts directly (skip manual hunting)**:
   - **Helpdesk/inbox connectors**: `ducoro-cli mcp catalog list --json` -> `status <slug> --json` -> `tools <slug> --json` -> `call <slug> <tool> --args-file <path|-> --json`.
   - **Periodic triage sweeps (auto-lands in Plan)**: `ducoro-cli task create --space <id> --cron "0 */2 * * *" --timezone <IANA-tz> --title "Support Triage Sweep" --instruction "..."`.
   - **P0/security/refund/SLA escalation into Inbox**: pair `--human <human-id> --ask confirm --request-summary "..."` on `task create`.
   - **Parallel backlog triage**: `ducoro-cli job dispatch --agent <agent-id> --name "triage-<batch>" "<prompt>"`.
   - **Live boards & cross-Space relay**: `ducoro-cli board new --space <id> --title "..." --json`, `ducoro-cli render check|shot --file <board>/index.html --json`, and `ducoro-cli space send` to hand off verified bugs to engineering or recurring pain points to content Spaces.
3. **Ingest & enforce deterministic guards**: Prefer Connectors, then run `scripts/ingest_feedback.py` for GitHub Issues, `.eml`/`.mbox`, or CSV/JSONL exports (`playbooks/channels-and-ingestion.md`). Run `scripts/triage_gate.py` for risk/SLA/spike detection, enforce approval hash pinning and leak/idempotency checks via `scripts/reply_guard.py`, and refresh boards via `scripts/build_boards.py`.

## Needs a Yes

Require explicit human confirmation before:
- Sending any reply on P0, security/privacy, refund/billing, legal, or escalated tickets.
- Making roadmap, SLA, or refund commitments, or sending redacted defect reports via `ducoro-cli feedback send`.
- Only if registering a new global Local Folder as a cross-Space sharing fallback.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

- `playbooks/support-loop.md`: Directory resolution, optional cross-Space fallback, single-writer rules, SLA loop, and cross-Space handoffs.
- `playbooks/methodology-voc-and-deflection.md`: De-escalation replies, 6-part engineering escalations, anti-false-consensus VoC, and KB deflection.
- `playbooks/channels-and-ingestion.md`: Real sources (Connectors, GitHub Issues, `.eml`/`.mbox`, CSV/JSONL, official desks).
- `playbooks/reply-safety-and-boards.md`: Hash-pinned reply guard and interactive Board SDK views.
- `references/workspace-schema.md`: Data layout and SLA policy schema.
