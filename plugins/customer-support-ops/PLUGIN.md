## Domain

Continuous customer support and product-feedback operations as a durable, file-backed loop—ingesting real tickets and reviews, enforcing deterministic P0/security/refund escalation and SLA rules, detecting root-cause spikes, and guarding outbound replies against leaks or duplicates.

## Activation & Boundaries

Activate for triaging user feedback, tickets, app reviews, SLA monitoring, drafting guarded customer replies, or tracking recurring issue spikes. Stay inactive for content publishing (`content-operations`), competitor intelligence (`market-intel`), financial bookkeeping (`business-finance-ops`), sales CRM, and recruiting workflows.

## Operating Loop

1. **Locate or bootstrap workspace**: Check `ducoro-cli local-folder list --json` and `ducoro-cli space resources get <space-id> --json`. Reuse `customer-support-ops`; if absent, ask the human before initializing `~/.ducoro/workspaces/customer-support-ops` via `playbooks/support-loop.md`.
2. **Ingest real feedback**: Check Ducoro Core Connectors (`ducoro-cli mcp catalog list --json`) first, then use `scripts/ingest_feedback.py` for GitHub Issues, `.eml`/`.mbox` mail archives, or CSV/JSONL ticket exports (`playbooks/channels-and-ingestion.md`).
3. **Run deterministic triage, guards & boards**: Evaluate risks, SLAs, and spikes via `scripts/triage_gate.py`, enforce approval hash pinning, leak/promise checks, and idempotency via `scripts/reply_guard.py`, and project boards via `scripts/build_boards.py`.
4. **Orchestrate natively**: Schedule sweeps with `ducoro-cli task create`, escalate P0/refund/legal items to Inbox, and relay verified bugs via `ducoro-cli space send`.

## Needs a Yes

Require explicit human confirmation before:
- Initializing and registering a new global `customer-support-ops` Local Folder.
- Sending any reply on P0, security/privacy, refund/billing, legal, or escalated tickets.
- Making roadmap, SLA, or refund commitments, or sending redacted defect reports via `ducoro-cli feedback send`.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

- `playbooks/support-loop.md`: Bootstrap, single-writer rules, SLA loop, and cross-Space handoffs.
- `playbooks/methodology-voc-and-deflection.md`: De-escalation replies, 6-part engineering escalations, anti-false-consensus VoC, and KB deflection.
- `playbooks/channels-and-ingestion.md`: Real sources (Connectors, GitHub Issues, `.eml`/`.mbox`, CSV/JSONL, official desks).
- `playbooks/reply-safety-and-boards.md`: Hash-pinned reply guard and interactive Board SDK views.
- `references/workspace-schema.md`: Workspace file contracts and SLA policy schema.
