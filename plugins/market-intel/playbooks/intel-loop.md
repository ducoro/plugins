# Intelligence Operating Loop

Rule precedence at every step: **Human live instructions > Bot `PROFILE.md` / private skills & memory > plugin defaults**.

## 1. Directory Resolution (Workspace Is Fallback-Only)

1. Inspect the current Space work root, attached resources, and existing Local Folders first:
   ```sh
   ducoro-cli space info <space-id> --json
   ducoro-cli space resources get <space-id> --json
   ducoro-cli local-folder list --json
   ```
2. Resolve `<data-dir>` in strict priority order:
   - **Existing folder first**: If the human already keeps a research/intelligence folder (or this Space already mounts one), use it directly—never create a second workspace.
   - **Single-Space default**: If tracking runs inside one Space without cross-Space file sharing, store files directly inside this Space's own `files/` (from `space info`, e.g., `<space-work-root>/files/market-intel`). Run `python3 scripts/init_workspace.py <data-dir>` only when initializing the directory schema for the first time (it initializes data directories only and never creates `boards/` inside `<data-dir>`).
   - **Cross-Space fallback only**: Only when multiple Spaces must share the same files and no existing folder exists yet, ask the human for confirmation before creating a shared directory scoped to that initiative (e.g., `~/.ducoro/workspaces/<initiative-slug>`, never inside `~/.ducoro/local-folders/`) and registering it as a global Local Folder:
     ```sh
     python3 scripts/init_workspace.py ~/.ducoro/workspaces/<initiative-slug>
     ducoro-cli local-folder register <initiative-slug> <resolved-absolute-path> \
       --name "<Initiative Intel>" --desc "Shared competitor and sector intelligence folder for this initiative"
     ducoro-cli local-folder inspect <initiative-slug>
     ```
     Multiple Bots working on the same initiative share that one directory—never create one workspace per Bot, and never merge unrelated initiatives into one hardcoded slug.
3. Outside Ducoro, fall back to `MARKET_INTEL_ROOT`.

## 2. Single-Writer Discipline & Parallel Collection Safety

| Owner | Exclusive Write Ownership |
|---|---|
| Parallel Collector Child Job (`--entity <slug>`) | `<data-dir>/captures/<slug>.json` only (strictly isolated per-entity shard) |
| Main Collector / Radar Space (Single Writer) | `captures/latest.json`, `captures/diff.json`, `snapshots/<entity>/*.json`, `seen-events.json` |
| Analyst / Battlecard Space | `entities/<slug>/profile.json`, `battlecards/<slug>.json`, `briefs/*.md`, `events.jsonl` (append-only via `evidence_gate.py`) |
| Lead / Configuration | `watchlist.json` |

### Parallel Sweep Protocol (No Shared-File Contention)

1. Discover real seated Agent IDs first:
   ```sh
   ducoro-cli space participant list <space-id> --json
   ```
2. Dispatch one child job per entity shard so each job writes only its own file and never touches shared baselines:
   ```sh
   ducoro-cli job dispatch --space <space-id> --agent <agent-id> --name "intel-<slug>" \
     "Run python3 scripts/fetch_sources.py <data-dir> --entity <slug> --out <data-dir>/captures/<slug>.json and do not modify snapshots or shared ledgers."
   ```
3. Monitor child jobs until completion:
   ```sh
   ducoro-cli job status <job-id> --json
   ducoro-cli job log <job-id>
   ```
4. Merge all completed entity shards (and any Connector/browser capture files) on the single writer into `captures/latest.json`, then run `snapshot_diff.py` and `evidence_gate.py` once:
   ```sh
   python3 scripts/fetch_sources.py <data-dir> \
     --merge <data-dir>/captures/<slug-a>.json <data-dir>/captures/<slug-b>.json \
     --out <data-dir>/captures/latest.json
   ```

## 3. End-to-End Durable Sweep

1. **Collect real data** (see `playbooks/source-adapters.md`):
   - Check `ducoro-cli mcp catalog list --json` first for connected SaaS/social sources.
   - For sequential runs, pull keyless public sources directly:
     ```sh
     python3 scripts/fetch_sources.py <data-dir> --out <data-dir>/captures/latest.json
     ```
   - Append Priority 1 Connector or Priority 3 browser/web_fetch/local-doc observations in `market-intel-signal/1` record format (or merge via `--merge`) so `evidence_gate.py` verifies all three tiers uniformly.
2. **Run deterministic diff & branch on outcome**:
   ```sh
   python3 scripts/snapshot_diff.py <data-dir> \
     --capture <data-dir>/captures/latest.json \
     --out <data-dir>/captures/diff.json
   ```
   - **`outcome == "capture_failed"` (`failedCount > 0` and `okCount == 0`)**: **Never stay silent.** Alert the human immediately with the failed source IDs and error reasons, check network reachability / URL changes / rate limits / upstream schema drift, fall back to a Connector or visible browser check if appropriate, and propose a redacted `ducoro-cli feedback send` report only if an adapter schema broke upstream.
   - **`partialFailure == true`**: Continue diffing and gating all healthy sources, but explicitly list failed sources and blind spots in the run note or brief so partial outages are never hidden.
   - **`outcome == "no_material_change"`**:
     - **Scheduled sweep**: Log a brief quiet run note and do **not** wake the human or pad filler reports.
     - **Direct human query**: Always reply concisely—state which entities and sources were checked, the check timestamp, and confirm that no material changes were observed.
   - **`outcome == "baseline_initialized"` / `"material_change"`**: Proceed to synthesis and gating.
3. **Independent Red-Team Review for High-Impact Calls**:
   - Before publishing `high`-severity shifts, pricing/positioning strategy calls, or major battlecard rewrites, dispatch an isolated read-only reviewer via `ducoro-cli job dispatch` giving only raw `captures/diff.json`, `captures/latest.json` (plus relevant `local-docs/`), and the draft conclusion—without the drafting conversation history. See `playbooks/methodology-and-triangulation.md` for the orthogonal review checklist.
4. **Gate claims before publishing briefs or appending events**:
   ```sh
   python3 scripts/evidence_gate.py <data-dir> \
     --capture <data-dir>/captures/latest.json \
     --candidates <data-dir>/captures/candidates.json \
     --commit-events
   ```
   - `evidence_gate.py` enforces non-empty `watchlist.json`, per-entity URL isolation (entity A cannot borrow entity B's URL), verified `evidenceUrls` and/or existing `<data-dir>` `localRef`, valid ISO `observedAt`, and normalized `quote` presence inside the referenced capture record or `localRef` file. Exit code `0` means all candidates passed; exit code `2` means one or more candidates were rejected.
5. **Refresh Space boards**:
   ```sh
   ducoro-cli board list --space <space-id> --json
   python3 scripts/build_boards.py <data-dir> --board radar-board --board-dir <space-work-root>/boards/<board-id>
   ```
   If no board exists yet in the target Space, provision via `ducoro-cli board new --space <space-id> --title "Market Intel Radar" --json` (and share across Spaces with `ducoro-cli board link --space <other-space-id> --board boards/<board-id> --json`).

## 4. Native Ducoro Scheduling, Inbox Escalation & Cross-Space Relay

- **Recurring sweeps (auto-lands in Plan)**:
  ```sh
  ducoro-cli task create --space <space-id> --daily 08:30 --timezone <IANA-tz> \
    --title "Market Intel Sweep" \
    --instruction "Run fetch_sources.py, snapshot_diff.py, and evidence_gate.py on <data-dir>; stay quiet on no_material_change, alert immediately on capture_failed."
  ```
- **Immediate Inbox escalation for material shifts requiring human judgment**:
  ```sh
  ducoro-cli identity get --json
  ducoro-cli task create --space <space-id> --manual \
    --title "Review High-Severity Competitor Shift" \
    --instruction "Present verified pricing/positioning diff and response options for human decision." \
    --human <human-id> --ask confirm \
    --request-summary "High-severity competitor pricing shift detected; review options." --json
  ducoro-cli task fire <task-id> --space <space-id> --json
  ```
- **Cross-Space handoff**:
  ```sh
  ducoro-cli space mail send <recipient> \
    --subject "Verified Market Intel Shift: <entity>" \
    --body "<concise grounded summary with eventId, confidence, and evidence URLs>"
  ```

## 5. Reporting Plugin or Source Breakage

If a script crashes or an upstream public API schema changes (not transient local network outages), show the human a redacted report first and, once approved, submit via:
```sh
ducoro-cli feedback send "[plugin:market-intel@<version>] [module:<module>] [location:<step>] <redacted details>"
# Read <version> from <plugin-root>/plugin.json
```
