## Domain

Continuous competitor, company, and sector intelligence as a grounded loop—tracking real changes across pricing pages, changelogs, software releases, app stores, job boards, SEC filings, and community mentions, delivering verified diffs without filler reports. Works directly in the human's existing research folder or current Space `files/`, scaling to a shared directory only when multiple Spaces need to relay files.

## Activation & Boundaries

Activate for tracking competitors, target companies, pricing shifts, product releases, hiring signals, public filings, or maintaining intelligence watchlists and battlecards. Keep scope grounded in verifiable public or human-supplied sources and never fabricate unverified intelligence claims.

## Operating Loop

1. **Resolve working directory (no forced workspace)**: Inspect `ducoro-cli space resources get <space-id> --json` and `ducoro-cli local-folder list --json`. Use the human's existing research folder first; for single-Space monitoring, use this Space's own `files/` directly. Only propose a shared global Local Folder as a fallback when multiple Spaces must exchange files and no existing folder fits—scoped to the project, never duplicated per Bot.
2. **Use Ducoro platform shortcuts directly (skip manual hunting)**:
   - **Connected SaaS/social sources**: `ducoro-cli mcp catalog list --json` -> `status <slug> --json` -> `tools <slug> --json` -> `call <slug> <tool> --args-file <path|-> --json`.
   - **Recurring sweeps (auto-lands in Plan)**: `ducoro-cli task create --space <id> --daily <HH:MM>|--cron "<expr>" --timezone <IANA-tz> --title "Market Intel Sweep" --instruction "..."`.
   - **Material shift escalation into Inbox**: pair `--human <human-id> --ask confirm --request-summary "..."` on `task create`.
   - **Parallel entity sweeps**: `ducoro-cli job dispatch --agent <agent-id> --name "intel-<slug>" "<prompt>"`.
   - **Interactive boards & cross-Space handoff**: `ducoro-cli board new --space <id> --title "..." --json`, `ducoro-cli render check|shot --file <board>/index.html --json`, and `ducoro-cli space mail send` to relay verified shifts to product or content Spaces.
3. **Collect real data & enforce deterministic gates**: Prefer Connectors, then run keyless public fetchers (`scripts/fetch_sources.py`), then browser or local filings (`playbooks/source-adapters.md`). Diff via `scripts/snapshot_diff.py` (stay quiet on `no_material_change`), verify claim URLs/timestamps/quotes via `scripts/evidence_gate.py`, and refresh boards via `scripts/build_boards.py`.

## Needs a Yes

Require explicit human confirmation before:
- Modifying monitored entity scope or adding authenticated Connectors.
- Sharing briefs externally or sending redacted defect reports via `ducoro-cli feedback send`.
- Only if registering a new global Local Folder as a cross-Space sharing fallback.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

- `playbooks/intel-loop.md`: Directory resolution, optional cross-Space fallback, single-writer rules, native scheduling, and relay.
- `playbooks/methodology-and-triangulation.md`: 4-quadrant triangulation, intent decoding, adversarial battlecards, and So What/Now What briefs.
- `playbooks/source-adapters.md`: Real sources (Connectors, 11 keyless public APIs, browser/local fallbacks).
- `playbooks/battlecards-and-boards.md`: Battlecard upkeep and interactive Board SDK projection.
- `references/workspace-schema.md`: Data layout and `watchlist.json` / `events.jsonl` contracts.
