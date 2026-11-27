## Domain

Continuous competitor, company, and sector intelligence as a grounded loop—tracking pricing, changelogs, releases, GitHub repo activity/files/trending, Product Hunt, app stores, job boards, SEC filings, Connectors, Computer Use fallback, and local docs, delivering verified diffs without filler reports. Works in the human's folder or Space `files/`, scaling to a shared directory only for multi-Space relay.

## Activation & Boundaries

Activate for tracking competitors, companies, open-source projects, discovery radars, pricing, releases, hiring, filings, watchlists, or battlecards. Precedence: `Human live instructions > Bot PROFILE.md / private skills & memory > plugin defaults`. Stay grounded in verifiable sources; never fabricate claims.

## Operating Loop

1. **Resolve `<data-dir>`**: Inspect `ducoro-cli space info <space-id> --json`, `ducoro-cli space resources get <space-id> --json`, and `ducoro-cli local-folder list --json`. Prefer the human's folder, then Space `files/`. Only propose a global Local Folder for cross-Space relay—scoped to the initiative, never per Bot.
2. **Use Ducoro facilities**:
   - **Connectors (Priority 1)**: `ducoro-cli mcp catalog list|status|tools|call` (Reddit, X, GitHub, etc.) before public fetchers.
   - **Sweeps & approvals**: Schedule automated sweeps via `ducoro-cli task create --space <id> --daily <HH:MM>|--cron "<expr>" --timezone <tz> --title "..." --instruction "..."`; run Computer Use checks on unlocked windows. For immediate approval, run `ducoro-cli identity get --json`, create `--manual --human <human-id> --ask confirm --request-summary "..."`, then `ducoro-cli task fire <task-id> --space <id> --json`.
   - **Parallel sweeps & red-team**: `ducoro-cli space participant list <space-id> --json`, `ducoro-cli job dispatch --space <id> --agent <agent-id> --name "<name>" "<prompt>"`, `ducoro-cli job status|log <job-id>`. Shards write only `--entity <slug> --out <data-dir>/captures/<slug>.json`; the main Space merges and owns shared writes.
   - **Boards & relay**: `ducoro-cli board list|new|link`, `ducoro-cli render check|shot`, `ducoro-cli space mail send <recipient> --subject "..." --body "..."`.
3. **Collect, diff, red-team, gate, project**: Combine Connectors, 15 public fetchers (`scripts/fetch_sources.py`), and Computer Use / browser / local-docs fallback (`playbooks/source-adapters.md`). Diff via `scripts/snapshot_diff.py` (`errorKind` + `changeKind`); stay quiet on `no_material_change` in scheduled sweeps and explicitly report skipped Computer Use coverage when locked. Register discovery boards as `category: "sector-radar"`, run isolated red-team review for high-impact calls, gate claims via `scripts/evidence_gate.py`, and project boards via `scripts/build_boards.py`.

## Needs a Yes

Require explicit human confirmation before:
- Modifying monitored entities, promoting a `sector-radar` discovery, or connecting new Connectors.
- Registering a new global Local Folder for cross-Space sharing.
- Sharing briefs externally or sending redacted defects via `ducoro-cli feedback send`.
- Defer to stricter rules in live instructions or `PROFILE.md`.

## Resources & Tools

- `playbooks/intel-loop.md`: Directory resolution, single-writer sweeps, `errorKind`/`changeKind`, radar promotion, CLI loop.
- `playbooks/methodology-and-triangulation.md`: Triangulation, OSS substantiveness, ranking neutrality, red-team review, templates.
- `playbooks/source-adapters.md`: 3-tier sources (Connectors, 15 fetchers, Computer Use / browser / local-docs) and grounding.
- `playbooks/battlecards-and-boards.md`: Battlecards, `sector-radar` filtering, board setup, and Board SDK commands.
- `references/workspace-schema.md`: `<data-dir>` schema, 15 adapters, `sector-radar`, `errorKind`/`changeKind`, `events.jsonl`, battlecards.
