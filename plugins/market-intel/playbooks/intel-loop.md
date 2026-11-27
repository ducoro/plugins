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
4. Merge all completed entity shards (and any Connector/Computer Use/browser capture files) on the single writer into `captures/latest.json`, then run `snapshot_diff.py` and `evidence_gate.py` once:
   ```sh
   python3 scripts/fetch_sources.py <data-dir> \
     --merge <data-dir>/captures/<slug-a>.json <data-dir>/captures/<slug-b>.json \
     --out <data-dir>/captures/latest.json
   ```

## 3. End-to-End Durable Sweep

1. **Collect real data** (see `playbooks/source-adapters.md`):
   - Check `ducoro-cli mcp catalog list --json` first for connected SaaS/social sources (e.g., Reddit, X, GitHub).
   - Pull public sources directly:
     ```sh
     python3 scripts/fetch_sources.py <data-dir> --out <data-dir>/captures/latest.json
     ```
   - Append Priority 1 Connector or Priority 3 Computer Use / browser / web_fetch observations in `market-intel-signal/1` record format (or merge via `--merge`) so `evidence_gate.py` verifies all three tiers uniformly.
2. **Run deterministic diff & branch on `outcome`, `errorKind`, and `changeKind`**:
   ```sh
   python3 scripts/snapshot_diff.py <data-dir> \
     --capture <data-dir>/captures/latest.json \
     --out <data-dir>/captures/diff.json
   ```
   - **`outcome == "capture_failed"` (`failedCount > 0` and `okCount == 0`)**: **Never stay silent.** Alert the human immediately with failed source IDs and their structured `errorKind`.
   - **`partialFailure == true`**: Continue diffing healthy sources (failed sources never erase existing snapshots), and list every failed or skipped Computer Use source explicitly in the brief so blind spots are never hidden.
   - **Actionable `errorKind` recovery table**:

     | `errorKind` | Meaning (Do Not Over-Claim) | Correct Action |
     |---|---|---|
     | `rate_limited` | HTTP 429 or API quota exhaustion | Stop hitting that endpoint immediately; respect cooldown; use optional token (`GITHUB_TOKEN`) or Connector on next window |
     | `auth_required` | HTTP 401 unauthenticated / expired token | Pause that source; check credential or Connector status; ask human before re-authenticating |
     | `access_denied` | HTTP 403 of unknown cause (not proven account ban) | Stop blind retries; do not rotate accounts; switch to Connector or Computer Use fallback when appropriate |
     | `challenge` | CAPTCHA, Cloudflare, or anti-bot gate | Stop immediately; never bypass; fall back to Computer Use with human verification or pause |
     | `network_timeout` | Transient DNS/TLS/socket timeout | Keep prior baseline intact; retry on next scheduled window |
     | `parse_error` | Upstream HTML/JSON schema changed or incomplete parse (e.g., partial Trending page) | Keep prior baseline intact (never emit fake drops); inspect raw page and propose `ducoro-cli feedback send` if upstream changed |

   - **Actionable `changeKind` handling**:
     - `content_changed` (in `materialChanges`): Substantive content/release/commit/issue/ranking shift → synthesize, red-team if high impact, gate via `evidence_gate.py`.
     - `discussion_active` (in `discussionUpdates`): Existing thread/issue gained comments without changing the core item → revisit when tracking user sentiment; never report an old thread as brand-new.
     - `engagement_only` (in `engagementOnly`): Only votes/stars/points jittered → stay quiet during scheduled sweeps (`no_material_change`).
     - `coverage_expanded` (in `coverageExpanded`): Wider fetch limit exposed older trailing items while the prefix stayed identical → update baseline silently; never frame older items as today's news.
   - **`outcome == "no_material_change"`**:
     - **Scheduled sweep**: Log a brief quiet run note and do **not** wake the human or pad filler reports (unless `partialFailure` or skipped Computer Use coverage must be reported).
     - **Direct human query**: Always reply concisely—state which entities and sources were checked, the check timestamp, and confirm no material changes were observed.
3. **Sector-Radar Discovery → Entity Promotion**:
   - Register broad discovery boards (such as GitHub Trending daily/weekly/monthly or Product Hunt daily) as `watchlist.json` entries with `"category": "sector-radar"`.
   - Gate discovery highlights with `"category": "discovery"`; `radar-board` surfaces them while `battlecard-board` automatically excludes `sector-radar` entries so competitor battlecards stay clean.
   - When a newly discovered project merits ongoing tracking, propose promoting it to a dedicated entity in `watchlist.json` and wait for human confirmation.
4. **Independent Red-Team Review for High-Impact Calls**:
   - Before publishing `high`-severity shifts, pricing/positioning strategy calls, or major battlecard rewrites, dispatch an isolated read-only reviewer via `ducoro-cli job dispatch` giving only raw `captures/diff.json`, `captures/latest.json` (plus relevant `local-docs/`), and the draft conclusion—without the drafting conversation history. See `playbooks/methodology-and-triangulation.md`.
5. **Gate claims before publishing briefs or appending events**:
   ```sh
   python3 scripts/evidence_gate.py <data-dir> \
     --capture <data-dir>/captures/latest.json \
     --candidates <data-dir>/captures/candidates.json \
     --commit-events
   ```
6. **Refresh Space boards**:
   ```sh
   ducoro-cli board list --space <space-id> --json
   python3 scripts/build_boards.py <data-dir> --board radar-board --board-dir <space-work-root>/boards/<board-id>
   ```
   If no board exists yet in the target Space, provision via `ducoro-cli board new --space <space-id> --title "Market Intel Radar" --json` (and share across Spaces with `ducoro-cli board link --space <other-space-id> --board boards/<board-id> --json`).

## 4. Native Ducoro Scheduling, Inbox Escalation & Cross-Space Relay

- **Automated Priority 1/2 sweeps (auto-lands in Plan)**:
  ```sh
  ducoro-cli task create --space <space-id> --daily 08:30 --timezone <IANA-tz> \
    --title "Market Intel Sweep" \
    --instruction "Run fetch_sources.py, snapshot_diff.py, and evidence_gate.py on <data-dir>; stay quiet on no_material_change, alert immediately on capture_failed."
  ```
- **Computer Use fallback sweeps (interactive / unlocked-desktop windows)**:
  Schedule gated-site checks (e.g., paywalled Medium, login-only communities, Product Hunt deep reviews) separately during active desktop hours or run on demand. If the desktop is locked or Computer Use is disabled, report the exact uncovered sources rather than reporting `no_material_change`.
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
    --body "<concise grounded summary with eventId, confidence, evidence URLs, and recommended next action>"
  ```

## 5. Reporting Plugin or Source Breakage

If a script crashes or an upstream public API/HTML schema changes (such as `parse_error` on a previously healthy endpoint, not transient local network outages), show the human a redacted report first and, once approved, submit via:
```sh
ducoro-cli feedback send "[plugin:market-intel@<version>] [module:<module>] [location:<step>] <redacted details>"
# Read <version> from <plugin-root>/plugin.json
```
