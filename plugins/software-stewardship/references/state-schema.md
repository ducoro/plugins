# Space-Local Rebuildable State Schema

The target Git repository and its remote host are the sole canonical source of truth. All files below are lightweight, rebuildable runtime artifacts stored inside `<space-work-root>/files/stewardship/` (locate `<space-work-root>` via `ducoro-cli space info <space-id> --json`; never commit these files into the target repository unless the team explicitly asks to archive a decision trail):

```text
<space-work-root>/files/stewardship/
├── audit.json             # Latest output of repo_audit.py (blastRadius, netLines, newFiles, dependencyManifestTouches, sensitivePaths, signalFlags, architectureSignals.shotgunCommits, largeFiles, churnHotspots, worktrees)
├── supply-chain.json      # Latest output of supply_chain_check.py (root lockfiles, live OSV CVEs, copyleft license flags, osvStatus)
├── gate-state.json        # Typed execution evidence (verification, fault-injection-red, formal-check, independent-review), diff checks, and headSha + diffHash approval locks
├── pulse.json             # Latest quiet monitoring snapshot from repo_monitor.py (PRs, CI, reverts, delta outcome)
├── pulse-history.jsonl    # Append-only log of material repository pulse changes (quiet no_material_change runs stay silent)
└── decisions.tsv          # Optional append-only decision trail for long or multi-phase runs (ts, phase, decision, why, evidence, result)
```

## Optional Remote Input Contract (`repo_monitor.py --github-json`)

When feeding PR and CI state exported from a connected GitHub Connector into `repo_monitor.py --github-json <path>`, write a JSON object with:

```json
{
  "pullRequests": [
    {"number": 42, "title": "Fix token refresh", "author": "dev1", "draft": false, "url": "https://...", "updatedAt": "2026-11-27T01:00:00Z"}
  ],
  "ciRuns": [
    {"id": 901, "name": "CI", "status": "completed", "conclusion": "failure", "branch": "main", "url": "https://...", "updatedAt": "2026-11-27T01:05:00Z"}
  ]
}
```

## Key Invariants

- **Clean target repo**: None of the scripts write into `--repo`; deleting `<space-work-root>/files/stewardship/` loses zero repository truth and can be regenerated from Git, lockfiles, and connected remote APIs.
- **Objective signals only (`audit.json`)**: `signalFlags` reports factual physical indicators (`sensitive_paths_touched`, `wide_diff`, `dependency_manifest_touched`, `shotgun_history_present`, `large_files_present`, `churn_hotspots_present`) without hard-coding a risk verdict from line counts.
- **Typed evidence & honest fault-injection red (`gate-state.json`)**: `verification`, `formal-check`, and `independent-review` pass on exit code `0`; `fault-injection-red` passes **only** on non-zero exit code and is logged after restoring the production file.
- **Drift-proof risk-aware approval lock (`gate-state.json`)**: Each approval entry binds `action` (`merge|release|migrate`), `risk` (`low|medium|high`), `allowAssertionPruning` (`bool`), `reviewWaiverReason` (`string`), `summary` (`string`), `headSha`, `diffHash` (16-char `sha256` prefix of net diff from merge-base + working tree state including nested untracked files), `approvedBy`, and `approvedAt`. Changing 1 byte invalidates the lock automatically; `medium`/`high` releases require either matching `independent-review` clearance or an exact-matching `--waive-review "<reason>"` at both `approve` and `verify-release`.
- **Honest offline/failure state (`supply-chain.json`, `pulse.json`)**: `supply_chain_check.py --offline` records `"osvStatus": "skipped_offline"`; network failure without `--offline` records `"osvStatus": "query_failed"` and exits `2`. `repo_monitor.py` evaluates only the latest completed run per `(workflow, branch)` for active CI failures, preserves last-known remote IDs on fetch errors (`"remote.status": "query_failed"`), and exits `2`.
