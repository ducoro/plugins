# Customer Support Ops

Continuous customer feedback, ticket triage, SLA tracking, root-cause spike detection, and guarded outbound reply operations for Ducoro.

## What It Solves

- **Real multi-channel ingestion (`scripts/ingest_feedback.py`)**: Prioritizes Ducoro Core Connectors (Intercom, Zendesk, GitHub, Gmail, Linear, Slack) and bundles zero-dependency importers for GitHub Issues, `.eml`/`.mbox` email archives, and CSV/JSONL ticket exports.
- **Deterministic triage, SLA & spike detection (`scripts/triage_gate.py`)**: Automatically flags P0 outages, security/privacy complaints, billing/refund disputes, legal threats, SLA breaches, and week-over-week root-cause spikes with verbatim customer evidence.
- **Tamper-proof reply guard (`scripts/reply_guard.py`)**: Blocks unapproved escalated replies, duplicate replies within cooldown windows, unresolved template placeholders, local path/secret leaks, unauthorized refund promises, and post-approval draft tampering (`sha256` hash lock).
- **Interactive shadcn/ui Boards (`scripts/build_boards.py`)**: Projects `triage-sla-board` and `root-cause-board` one-way from the active data directory.

## License

Apache License 2.0. See [LICENSE](LICENSE).
