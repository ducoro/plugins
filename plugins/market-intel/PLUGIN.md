## Domain

Continuous competitor, company, and sector intelligence as a grounded loop—tracking shifts across pricing, changelogs, releases, app stores, job boards, SEC filings, Connectors, and local docs, delivering verified diffs without filler reports. Works in the human's folder or Space `files/`, scaling to a shared directory only when multiple Spaces exchange files.

## Activation & Boundaries

Activate for tracking competitors, target companies, pricing shifts, releases, hiring signals, filings, watchlists, or battlecards. Precedence: `Human live instructions > Bot PROFILE.md / private skills & memory > plugin defaults`. Stay grounded in verifiable public, connected, or human-supplied sources and never fabricate claims.

## Operating Loop

1. **Resolve `<data-dir>`**: Inspect `ducoro-cli space info <space-id> --json`, `ducoro-cli space resources get <space-id> --json`, and `ducoro-cli local-folder list --json`. Prefer the human's folder, then Space `files/`. Only propose a global Local Folder as a cross-Space fallback—scoped to the initiative, never per Bot.
2. **Use Ducoro platform facilities directly**:
   - **Connectors (Priority 1)**: `ducoro-cli mcp catalog list|status|tools|call` before public fetchers.
   - **Sweeps & Inbox escalation**: Schedule via `ducoro-cli task create --space <id> --daily <HH:MM>|--cron "<expr>" --timezone <tz> --title "..." --instruction "..."`. For immediate Inbox approval, fetch `<human-id>` via `ducoro-cli identity get --json`, run `ducoro-cli task create --space <id> --manual --title "..." --instruction "..." --human <human-id> --ask confirm --request-summary "..." --json`, then `ducoro-cli task fire <task-id> --space <id> --json`.
   - **Parallel sweeps & red-team review**: List agents via `ducoro-cli space participant list <space-id> --json`, dispatch via `ducoro-cli job dispatch --space <id> --agent <agent-id> --name "<name>" "<prompt>"`, and check `ducoro-cli job status|log <job-id>`. Collector shards write only `--entity <slug> --out <data-dir>/captures/<slug>.json`; the main Space merges and owns shared writes.
   - **Boards & relay**: Use `ducoro-cli board list|new|link`, `ducoro-cli render check|shot`, and `ducoro-cli space mail send <recipient> --subject "..." --body "..."`.
3. **Collect, diff, red-team, gate, project**: Combine Connectors, keyless fetchers (`scripts/fetch_sources.py`), and browser/local-docs (`playbooks/source-adapters.md`). Diff via `scripts/snapshot_diff.py`: alert on `capture_failed`; on `no_material_change`, stay quiet during scheduled sweeps, but answer concisely with checked scope when a human asks directly. Before high-severity calls or major battlecard edits, run an isolated read-only red-team review (`playbooks/methodology-and-triangulation.md`). Gate claims via `scripts/evidence_gate.py`, then project boards via `scripts/build_boards.py`.

## Needs a Yes

Require explicit human confirmation before:
- Modifying monitored entities or connecting new authenticated Connectors.
- Registering a new global Local Folder as a cross-Space fallback.
- Sharing briefs externally or sending redacted defect reports via `ducoro-cli feedback send`.
- Defer to stricter rules in live human instructions or the Bot's `PROFILE.md`.

## Resources & Tools

- `playbooks/intel-loop.md`: Directory resolution, parallel single-writer protocol, failure alerts, and CLI orchestration.
- `playbooks/methodology-and-triangulation.md`: Triangulation, isolated read-only red-team review, and optional templates.
- `playbooks/source-adapters.md`: 3-tier sources (Connectors, 11 keyless APIs, browser/local-docs) and evidence grounding.
- `playbooks/battlecards-and-boards.md`: Battlecards, board provisioning/linking, and Board SDK commands.
- `references/workspace-schema.md`: `<data-dir>` schema, 11 adapter keys, `candidates.json`, `events.jsonl`, `profile.json`, and battlecards.
