# Intelligence Operating Loop

## 1. Directory Resolution (Workspace Is Fallback-Only)

1. Inspect existing Space resources and folders first:
   ```sh
   ducoro-cli space resources get <space-id> --json
   ducoro-cli local-folder list --json
   ```
2. Follow this strict priority based on the human's actual setup:
   - **Existing folder first**: If the human already keeps a research/intelligence folder (or this Space already mounts one), use it directly—never create a second workspace.
   - **Single-Space default**: If tracking runs inside one Space without cross-Space file sharing, store files directly inside this Space's own `files/` (for example `files/market-intel/`). Run `python3 scripts/init_workspace.py <data-dir>` only when initializing the directory schema for the first time.
   - **Cross-Space fallback only**: Only when multiple Spaces must share the same files and no existing folder exists yet, ask the human for confirmation before creating a shared directory scoped to that initiative (e.g., `~/.ducoro/workspaces/<initiative-slug>`, never inside `~/.ducoro/local-folders/`) and registering it as a global Local Folder:
     ```sh
     python3 scripts/init_workspace.py ~/.ducoro/workspaces/<initiative-slug>
     ducoro-cli local-folder register <initiative-slug> <resolved-absolute-path> \
       --name "<Initiative Intel>" --desc "Shared competitor and sector intelligence folder for this initiative"
     ducoro-cli local-folder inspect <initiative-slug>
     ```
     Multiple Bots working on the same initiative share that one directory—never create one workspace per Bot, and never merge unrelated initiatives into one hardcoded slug.
3. Outside Ducoro, fall back to `MARKET_INTEL_ROOT`.

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
   - Cross-Space handoff: send grounded findings to a content or product Space via `ducoro-cli space mail send`.

## 4. Reporting Plugin or Source Breakage

If a script crashes or an upstream public API schema changes (not local network outages), show the human a redacted report first and, once approved, submit via:
```sh
ducoro-cli feedback send "[plugin:market-intel@<version>] [module:<module>] [location:<step>] <redacted details>"
# Read <version> from <plugin-root>/plugin.json
```
