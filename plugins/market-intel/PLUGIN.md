## Domain

Continuous competitor, company, and sector intelligence as a durable, file-backed loop—tracking real changes across pricing pages, changelogs, software releases, app stores, job boards, SEC filings, and community mentions, delivering grounded diffs without filler reports.

## Activation & Boundaries

Activate for tracking competitors, target companies, pricing shifts, product releases, hiring signals, filings, or maintaining intelligence watchlists and battlecards. Stay inactive for content publishing (`content-operations`), customer support (`customer-support-ops`), financial bookkeeping (`business-finance-ops`), sales CRM, and recruiting workflows.

## Operating Loop

1. **Locate or bootstrap workspace**: Check `ducoro-cli local-folder list --json` and `ducoro-cli space resources get <space-id> --json`. Reuse `market-intel`; if absent, ask the human before initializing `~/.ducoro/workspaces/market-intel` via `playbooks/intel-loop.md`.
2. **Collect real data**: Check Ducoro Core Connectors (`ducoro-cli mcp catalog list --json`) first, then run keyless public fetchers (`scripts/fetch_sources.py`), then fallback to browser or human-provided local filings (`playbooks/source-adapters.md`).
3. **Run deterministic gates & boards**: Diff snapshots via `scripts/snapshot_diff.py` (emit `no_material_change` when unchanged), verify claim URLs/timestamps/quotes via `scripts/evidence_gate.py`, and project boards via `scripts/build_boards.py`.
4. **Orchestrate natively**: Schedule sweeps with `ducoro-cli task create`, parallelize via `ducoro-cli job dispatch`, escalate material shifts to Inbox, and relay findings via `ducoro-cli space send`.

## Needs a Yes

Require explicit human confirmation before:
- Initializing and registering a new global `market-intel` Local Folder.
- Modifying monitored entity scope or adding authenticated Connectors.
- Sharing briefs externally or sending redacted defect reports via `ducoro-cli feedback send`.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

- `playbooks/intel-loop.md`: Bootstrap, single-writer rules, native scheduling, and cross-Space relay.
- `playbooks/methodology-and-triangulation.md`: 4-quadrant triangulation, intent decoding, adversarial battlecards, and So What/Now What briefs.
- `playbooks/source-adapters.md`: Real sources (Connectors, 11 keyless public APIs, browser/local fallbacks).
- `playbooks/battlecards-and-boards.md`: Battlecard upkeep and interactive Board SDK projection.
- `references/workspace-schema.md`: Shared workspace file contracts.
