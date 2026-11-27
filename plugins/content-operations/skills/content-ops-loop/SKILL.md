---
name: content-ops-loop
description: Orchestrate a continuous multi-platform content operations loop (intake, topic selection, production, scheduling, publishing, engagement, analytics, retro, and interactive boards) using a file-backed data directory. Use as the entry point to start, inspect, schedule, or coordinate any content workflow.
---

# Content Operations Loop

Run multi-platform content operations as a durable, file-backed loop rather than isolated one-off posts.

## Operating Modes

One installed plugin supports two topologies over the chosen data directory (the human's existing folder, this Space's `files/`, or an optional cross-Space Local Folder):

1. **Single-Space end-to-end**: One agent runs all stages sequentially inside one Space using the human's folder or `files/`.
2. **Multi-Space relay**: Dedicated Spaces (monitoring, drafting, publishing, engagement) share canonical files (`inbox/`, `topics/`, `drafts/`, `calendar.json`, `publish-log.jsonl`, `engagement/`, `analytics/`) under single-writer ownership and hand off via `ducoro-cli space mail send <recipient> --subject "<subject>" --body "<body>"`.

## Skill Routing Table

Load **only** the skills needed for the current region, format, and target platform(s)—never load all 14 platform skills at once.

| Stage / Need | Load Skill |
| --- | --- |
| Sourcing CN-market topics (Connectors, Weibo/Toutiao/Baidu, Baidu/360 SEO, signal gate) | `../topic-research-cn/SKILL.md` |
| Sourcing Global/EN topics (Connectors, HN/Lobsters/GitHub/Polymarket/DEV.to/arXiv, signal gate) | `../topic-research-global/SKILL.md` |
| Long-form editorial writing (WeChat essays, blogs, newsletters, LinkedIn/X Articles) | `../longform-writing/SKILL.md` |
| Short-form posts, threads & exact-pixel cards (X, Xiaohongshu, Threads, IG, Pinterest, newspic) | `../shortform-social/SKILL.md` |
| Short/long video scripting, subtitles & clipping (Douyin, TikTok, YouTube, Bilibili, Channels, Kuaishou) | `../video-production/SKILL.md` |
| Comment triage, rate limits, 24h/72h/7d/30d snapshots & weekly retro | `../engagement-and-analytics/SKILL.md` |
| Platform radar, voice, specs, publish protocol & native retro metrics (14 indexed in `../../references/platforms.md`) | `../platform-<name>/SKILL.md` |

Shared deterministic scripts in `scripts/`: `init_workspace.py`, `validate_workspace.py`, `diagnose.py`, `signal_gate.py`, `score_topics.py`, `check_media_specs.py`, `image_ops.py`, `build_boards.py`.

## Native Orchestration, Channels & Deterministic Boundaries

- **Legitimate 3-tier channel priority** (`references/channel-access-matrix.md`; never extract cookies, call private APIs, or bypass login/CAPTCHA):
  1. **Ducoro Core Connectors (first)**: `ducoro-cli mcp catalog list` / `status <slug>` / `tools <slug>` / `call <slug> <tool> --args-file <path|-> --json`.
  2. **Official Platform OpenAPI (`scripts/client.py`, optional user-owned credentials, 12 platforms)**: when the user provides official developer tokens/API keys (plus `ducoro-cli media upload <path> --json` 5h relay for Meta/Pinterest).
  3. **Universal Fallback — Official Browser / Ducoro Computer Use (all platforms, zero API setup)**: whenever no Connector and no user API key exist—or a capability is web/Studio-only (e.g., X Articles, personalized feeds, CN Creator Studios)—operate inside the user's logged-in browser/desktop session via Computer Use, uploading directly from `drafts/<id>/assets/`, pausing for login/CAPTCHA and Gate 2, and reading back live URLs. Declared once centrally in `references/channel-access-matrix.md` for all platforms.
- **Ducoro orchestration primitives**:
  - **Space & identity**: `ducoro-cli space info <space-id> --json` (`<space-work-root>`, `files/`) and `ducoro-cli identity get --json` (`<human-id>`).
  - **Scheduling & Inbox sign-off**: `ducoro-cli task create --space <id> --at <iso>|--daily <HH:MM>|--cron "<expr>" --timezone <tz> --title "..." --instruction "..."` (Plan); immediate human sign-off via `--manual --human <human-id> --ask confirm --request-summary "..."` + `ducoro-cli task fire <task-id> --space <id> --json`; inspect/halt stale or failing tasks via `ducoro-cli task list|disable|rm`.
  - **Fan-out & isolated review**: `ducoro-cli space participant list <space-id> --json`, `ducoro-cli job dispatch [--space <id>] --agent <agent-id> --name "<name>" "<prompt>"` (or `job start`), collect via `ducoro-cli job status <job-id> --json` and `ducoro-cli job log <job-id>`.
  - **Boards & relay**: `ducoro-cli board list|new|link --space <id> [--board boards/<id>] --json` and `ducoro-cli space mail send <recipient> --subject "<subject>" --body "<body>"`.
- **Hard invariants in code**: `signal_gate.py` (provenance URLs, ISO timestamps, keep-richest dedupe, incremental `seen-signals.json`, honest `nothing_solid`), `score_topics.py` (`--import-gated`, annotate-only fuzzy repeats), `check_media_specs.py` (`--channel browser|api`, placeholder scan), `validate_workspace.py --verify-slot <slotId>` (Gate 2 `variantHash` lock & idempotency).

## Core References (Load on Demand)

- `references/workspace-schema.md`: canonical directory layout and JSON/JSONL contracts.
- `references/approval-gates.md`: Gate 1 / Gate 2 boundaries, immediate Inbox wake-up, stale task halt.
- `references/operating-cadence.md`: native schedules, circuit-breaker recovery, Multi-Space relay ownership.
- `references/board-schemas.md` & `references/board-sdk-integration.md`: 5-board payloads, `window.ducoro` SDK, FBED & `ducoro-cli render`.
- `references/channel-access-matrix.md`: 14-platform 3-tier access matrix.
- `references/issue-reporting.md`: redacted plugin bug reports via `ducoro-cli feedback send` (ask human first).

## Workflow

1. **Resolve working directory (existing folder or Space `files/` first; global Workspace is fallback-only).**
   - Inspect `ducoro-cli space info <space-id> --json`, `ducoro-cli space resources get <space-id> --json`, and `ducoro-cli local-folder list --json`.
   - Priority: (1) human's existing folder; (2) current Space `files/` for Single-Space work (run `python3 scripts/init_workspace.py <data-dir> --timezone <IANA-tz>` only when scaffolding first time); (3) **cross-Space fallback only** when Multi-Space relay needs a shared folder and none exists—confirm first, scaffold `~/.ducoro/workspaces/<initiative-slug>` (never `~/.ducoro/local-folders/`), and register via `ducoro-cli local-folder register <slug> <abs-path> --name "..." --desc "..."` + `inspect <slug>`. Never create one folder per Bot.
   - Read `brand-profile.md` and `accounts.json` (env var names only—never raw secrets).
2. **Execute requested stage(s).**
   - **Intake & topics**: collect via Connectors or regional radar, run `signal_gate.py ingest` + `gate --strict`, score with `score_topics.py`, pause at **Gate 1** (or stop on `nothing_solid`).
   - **Production, isolated review & adaptation**: load only the matching format workshop + target `platform-<name>`. For high-risk external releases or final long-form review, **never self-certify `assessment.json` in the drafting context**—dispatch isolated fresh read-only reviewers via `ducoro-cli space participant list <space-id> --json` + `ducoro-cli job dispatch` across orthogonal lenses (fact/provenance tracing, platform red lines/compliance, reader subtraction) and collect verdicts via `ducoro-cli job status|log <job-id>`. Run `check_media_specs.py` on every variant.
   - **Schedule & publish**: record slot + `approvedVariantHash` in `calendar.json`, schedule via `ducoro-cli task create` (or immediate `--manual` + `task fire` sign-off), verify Gate 2 with `validate_workspace.py <data-dir> --verify-slot <slotId>`, publish via 3-tier channel priority, and read back verified `publicUrl` + `workId` into `publish-log.jsonl`.
   - **Engagement & analytics**: follow `engagement-and-analytics` (4-tier triage, `engagement_guard.py`, 24h/72h/7d/30d snapshots, weekly retro recycled to `inbox/`).
3. **Validate, diagnose, and refresh Space Boards.**
   ```sh
   python3 scripts/validate_workspace.py <data-dir>
   python3 scripts/diagnose.py --workspace <data-dir> --json
   python3 scripts/build_boards.py <data-dir>
   ```
   Check boards via `ducoro-cli board list --space <space-id> --json`, create missing ones with `board new`, project via `build_boards.py <data-dir> --board <name> --board-dir <space-work-root>/boards/<board-id>` (`--overwrite-templates` on first build), verify via `ducoro-cli render check|shot --file <board-dir>/index.html --json`, and share via `ducoro-cli board link --space <space-id> --board boards/<board-id> --json`.

## Hard Guardrails

- **Silence is not approval.** Never publish externally, spend budget, or send commitment/dispute replies without explicit human confirmation or a written standing rule in `brand-profile.md`.
- **No fabricated execution.** Missing credentials or login/CAPTCHA must fall back cleanly to official browser flow or pause and report prerequisites.
- **Single source of truth.** Files in `<data-dir>` are canonical state; boards are read-only projections.

## Done When

- Data directory passes `validate_workspace.py` with zero errors.
- Any external publish has a verified `publicUrl` (or explicit `draft_saved`/`failed` record) in `publish-log.jsonl`.
- Affected boards are rebuilt via `build_boards.py` and the next human decision (if any) is stated clearly.
