# Software Stewardship Loop

## Why This Environment Exists

Applying heavy ceremony to a typo fix encourages bypassing safeguards; skipping verification on high-risk changes lets silent regressions ship. This loop anchors work in the real repository, separates free local iteration from gated external actions, matches verification environments to risk, and keeps routine sweeps silent unless something materially changes.

## 1. Repository First, Zero Pollution

- **Locate paths cleanly**:
  - Target repo: `ducoro-cli local-folder list --json` and `ducoro-cli space resources get <space-id> --json` (or an explicit `--repo` path).
  - Current Space working root (`files/` and `boards/`): `ducoro-cli space info <space-id> --json`.
- **Respect precedence**: Human live instructions > Bot `PROFILE.md` > target repo's `AGENTS.md`, CI, and lint rules > this plugin's defaults. Read the repo's `AGENTS.md`, `README.md`, CI workflows, and package scripts before proposing changes.
- **Keep plugin state out of the repo**: Store rebuildable state (`audit.json`, `supply-chain.json`, `gate-state.json`, `pulse.json`, `decisions.tsv`) in `<space-work-root>/files/stewardship/` (`<state-dir>`). Never pollute the repo's git tree, and never create `~/.ducoro/workspaces/` unless multiple Spaces must share non-repo operational state and no folder exists. Invoke bundled scripts from `<plugin-root>/scripts/` so the working directory stays on the target repo.

## 2. Local Freedom vs. Gated External Actions & Risk Tiers

Local exploration, prototyping, and local commits are free unless the repo's own rules say otherwise. Hard `change_gate.py` approval locks apply before **pushing, merging into protected branches, tagging releases, running production migrations, or shipping externally**.

Classify every change by semantic impact (not raw line counts; when uncertain, round up one tier; passing tests never downgrade a high-risk change):

| Risk Tier | When It Applies | Verification Environment |
|---|---|---|
| **Low** | Single clear owner, easily reversible, touches no contract, schema, auth, crypto, billing, concurrency, or external deploy (e.g., copy, docs, styling, isolated patch) | Independent expectation + real surface check + `change_gate.py check-diff`. For protected-branch merges, tags, or public releases, also record passing verification (`record-evidence`) and run `approve --risk low` + `verify-release --risk low`; for ordinary routine pushes with explicit human go-ahead, `check-diff` + real check suffices. |
| **Medium** | Reversible behavioral change inside one subsystem with clear boundaries, where bloat, side effects, sibling paths, or test drift could slip through | Low checks + isolated Subtraction Pass + fault-injection red check for new/edited guards + **1 fresh read-only reviewer session** covering all 6 lenses + `record-evidence` + `approve --risk medium` + `verify-release --risk medium`. |
| **High** | Touches API/CLI/wire contracts, storage schema/migrations, auth/permissions/secrets, billing/accounting, concurrency/retries/recovery, public routes/deploys, or cross-subsystem refactors | Medium checks + multi-shape design comparison + Class A/B formal verification where state/order matters + **6-lens blind review** (1 fresh reviewer session for localized high-risk diffs; parallel split + independent adversarial finding re-check when spanning multiple subsystems) + `record-evidence` + `approve --risk high` + `verify-release --risk high`. |

## 3. Continuous Operating Cadence

1. **Before pushing, merging, or shipping**:
   - Align requirement boundaries and minimal layering (`playbooks/requirement-and-design.md`).
   - Run real surface checks, isolated Subtraction Pass, fault-injection red / formal checks, and risk-matched blind review (`playbooks/verification-and-review.md`).
   - Run objective audit, diff guard, typed evidence, and drift-proof approval lock (`playbooks/prevention-and-repo-memory.md`). Omit `--base` to auto-resolve the tracking upstream (`@{u}` / `origin/main`) or `HEAD~1` on local trunk-only `main`, or pass `--base <ref>` explicitly:
     ```sh
     python3 <plugin-root>/scripts/repo_audit.py --repo <repo-path> [--base <base-ref>] --out <state-dir>/audit.json
     python3 <plugin-root>/scripts/change_gate.py --repo <repo-path> --state-dir <state-dir> check-diff [--base <base-ref>]
     ```
2. **Scheduled quiet pulse sweeps & Boards**:
   - Feed remote PR/CI data into `repo_monitor.py` either via `--github-json <path>` (exported from a connected GitHub Connector via `ducoro-cli mcp catalog call <slug> <tool> --args-file <path|-> --json`; schema in `references/state-schema.md`) or `--github-repo <owner/repo>` (read-only GitHub REST API, using `GITHUB_TOKEN` if private):
     ```sh
     python3 <plugin-root>/scripts/supply_chain_check.py --repo <repo-path> --out <state-dir>/supply-chain.json
     python3 <plugin-root>/scripts/repo_monitor.py --repo <repo-path> --state-dir <state-dir> [--github-json <path> | --github-repo <owner/repo>]
     ```
   - When `repo_monitor.py` returns `"outcome": "no_material_change"`, stay quiet—do not wake the human with filler status reports. If a remote query fails, it preserves the last-known remote IDs, marks `"remote.status": "query_failed"`, and exits with code `2`—never treat a failed query as cleared CI.
   - **Formal Space Boards**: Find existing boards with `ducoro-cli board list --space <id> --json` or create once with `ducoro-cli board new --space <id> --title "Delivery & Gate" --json` (and `"Repo Health"`). Project one-way into `<space-work-root>/boards/<board-id>` and surface via `ducoro-cli board link`:
     ```sh
     python3 <plugin-root>/scripts/build_boards.py --state-dir <state-dir> --board delivery-board --board-dir <space-work-root>/boards/<delivery-id>
     python3 <plugin-root>/scripts/build_boards.py --state-dir <state-dir> --board health-board --board-dir <space-work-root>/boards/<health-id>
     ducoro-cli board link --space <id> --board boards/<delivery-id> --json
     ```
     (`--all` writes to `<state-dir>/boards/` for standalone local preview only—it does not mount as a Space Board.)
   - Schedule recurring sweeps natively:
     ```sh
     ducoro-cli task create --space <id> --daily 09:00 --timezone <IANA-tz> \
       --title "Repo Health Sweep" --instruction "Run supply-chain and pulse checks; alert only on material regressions."
     ```
3. **Human sign-off & cross-Space mail**:
   - In live conversation, ask the human directly for confirmation. For async or scheduled escalations into Inbox, fetch `<human-id>` via `ducoro-cli identity get --json`, create a manual escalation task with `--human <human-id> --ask confirm --request-summary "..." --manual --instruction "..."`, and trigger it immediately via `ducoro-cli task fire <task-id> --space <id> --json` (inspect delivery via `ducoro-cli task history <task-id> --space <id> --json` and `ducoro-cli inbox list --session <id> --json`).
   - Discover target Spaces via `ducoro-cli space list --json` and send durable cross-Space updates via:
     ```sh
     ducoro-cli space mail send <target-space-id> --subject "<subject>" --body "<verified summary>"
     ```
     (Confirm with the human first if the mail triggers an external announcement.)

## 4. Reporting Plugin Defects

If a bundled script fails on a valid repository or an upstream public API schema (such as OSV.dev) changes, show the human a redacted summary first, read `<version>` from `<plugin-root>/plugin.json`, and submit via:
```sh
ducoro-cli feedback send "[plugin:software-stewardship@<version>] [module:<module>] [location:<step>] <redacted details>"
```
