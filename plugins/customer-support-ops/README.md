# Customer Support Ops

Continuous customer feedback, ticket triage, SLA tracking, root-cause spike detection, and guarded outbound reply operations for Ducoro.

## What It Solves

- **Real multi-channel ingestion (`scripts/ingest_feedback.py`)**: Prioritizes Ducoro Core Connectors (Intercom, Zendesk, GitHub, Gmail, Linear, Slack) and bundles zero-dependency importers for GitHub Issues (`--state`, `--limit`, truncation warnings), `.eml`/`.mbox` email archives, and CSV/JSONL ticket exports.
- **Monotonic triage, SLA & real trend detection (`scripts/triage_gate.py`)**: Preserves human/model high-risk assessments without downgrading, evaluates structured risk flags (`vip`, `labels`, `riskFlags`, ratings, SLA breaches), derives replied status from `reply-log.jsonl`, and computes real 7-day vs prior-7-day `clusterMetrics` with anti-false-consensus unique-customer thresholds.
- **Tamper-proof reply guard (`scripts/reply_guard.py`)**: Enforces hash-pinned human approval for high-risk or commitment-bearing replies, stages clean routine replies as `ready_to_send` (or `awaiting_approval` when configured), blocks leaks/placeholders/duplicate hashes, unlocks cooldowns on legitimate customer follow-ups or post-send human approvals, and preserves single-writer ownership.
- **Interactive shadcn/ui Boards (`scripts/build_boards.py`)**: Projects `triage-sla-board` and `root-cause-board` one-way from the active `<data-dir>` into each Space's own `boards/<board-id>/`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
