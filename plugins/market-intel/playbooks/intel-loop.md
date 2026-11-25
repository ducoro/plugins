# Intelligence Operating Loop

## 1. Workspace Discovery & Bootstrap

1. Inspect existing registrations first:
   ```sh
   ducoro-cli local-folder list --json
   ducoro-cli space resources get <space-id> --json
   ```
2. If slug `market-intel` already exists, reuse its resolved path.
3. If absent, ask the human for confirmation before creating `~/.ducoro/workspaces/market-intel` (or a human-chosen directory; never write inside `~/.ducoro/local-folders/`), then initialize and register it:
   ```sh
   python3 scripts/init_workspace.py ~/.ducoro/workspaces/market-intel
   ducoro-cli local-folder register market-intel ~/.ducoro/workspaces/market-intel \
     --name "Market Intel" --desc "Shared competitor, company, and sector intelligence workspace"
   ducoro-cli local-folder inspect market-intel
   ```
4. Outside Ducoro, fall back to `MARKET_INTEL_ROOT`.

## 2. Single-Writer Discipline (Multi-Space Safe)

| Space Role | Exclusive Write Ownership |
|---|---|
| Collector / Radar Space | `captures/*.json`, `snapshots/<entity>/*.json`, `seen-events.json` |
| Analyst / Battlecard Space | `entities/<slug>/profile.json`, `battlecards/<slug>.json`, `briefs/*.md`, `events.jsonl` (append-only) |
| Lead / Configuration | `watchlist.json` |

## 3. End-to-End Durable Sweep

1. **Collect real data** (see `playbooks/source-adapters.md`):
   - Check `ducoro-cli mcp catalog list --json` first for connected SaaS/social sources.
   - Run `python3 scripts/fetch_sources.py <workspace> --out <workspace>/captures/latest.json` for verified keyless public sources defined in `watchlist.json`.
2. **Run deterministic diff**:
   ```sh
   python3 scripts/snapshot_diff.py <workspace> --capture <workspace>/captures/latest.json --out <workspace>/captures/diff.json
   ```
   - If `outcome` is `"no_material_change"`, log a quiet run note and do **not** wake the human or invent filler bullets.
3. **Gate claims before publishing briefs or appending events**:
   ```sh
   python3 scripts/evidence_gate.py <workspace> \
     --capture <workspace>/captures/latest.json \
     --candidates <workspace>/captures/candidates.json \
     --commit-events
   ```
   - Every candidate claim must cite `evidenceUrls` present in the capture pool, a valid ISO `observedAt`, and a non-empty `quote`. Any fabricated or ungrounded item is rejected with exact error diagnostics.
4. **Refresh boards**:
   ```sh
   python3 scripts/build_boards.py <workspace> --board radar-board --board-dir <space-work-root>/boards/<id>
   ```
5. **Native orchestration**:
   - Daily/weekly sweeps: `ducoro-cli task create --space <id> --daily 08:30 --timezone <IANA-tz> --title "Market Intel Sweep" --instruction "..."`
   - Parallel entity sweeps: `ducoro-cli job dispatch --agent <agent-id> --name "intel-<slug>" "..."`
   - Material shifts requiring human judgment (e.g., competitor price cut, major launch, SEC 8-K): route via `--human <human-id> --ask confirm --request-summary "..."` into Inbox.
   - Cross-Space handoff: send grounded findings to a content or product Space via `ducoro-cli space send`.

## 4. Reporting Plugin or Source Breakage

If a script crashes or an upstream public API schema changes (not local network outages), show the human a redacted report first and, once approved, submit via:
```sh
ducoro-cli feedback send "[plugin:market-intel@1.0.0] [module:<module>] [location:<step>] <redacted details>"
```
