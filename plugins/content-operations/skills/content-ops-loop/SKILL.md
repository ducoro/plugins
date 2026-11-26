---
name: content-ops-loop
description: Orchestrate a continuous multi-platform content operations loop (intake, topic selection, production, scheduling, publishing, engagement, analytics, retro, and interactive boards) using a file-backed workspace. Use as the entry point to start, inspect, schedule, or coordinate any content workflow.
---

# Content Operations Loop

Run multi-platform content operations as a durable, file-backed loop rather than isolated one-off posts.

## Operating Modes

One installed plugin supports two topologies over the same `content-ops/` workspace directory:

1. **Single-workspace end-to-end**: One agent runs all stages sequentially in one workspace.
2. **Multi-workspace relay**: Dedicated workspaces (monitoring, drafting, publishing, engagement) share `content-ops/` files (`inbox/`, `topics/`, `drafts/`, `calendar.json`, `publish-log.jsonl`, `engagement/`, `analytics/`).

## Skill Routing Table

Load **only** the skills needed for the current region, format, and target platform(s)—never load all 14 platform skills at once.

| Stage / Need | Load Skill |
| --- | --- |
| Sourcing CN-market topics (Connectors, Weibo/Toutiao/Baidu, Baidu/360 SEO, hard signal gate) | `../topic-research-cn/SKILL.md` |
| Sourcing Global/EN topics (Connectors, HN/Lobsters/GitHub/Polymarket/DEV.to/arXiv, hard signal gate) | `../topic-research-global/SKILL.md` |
| Long-form editorial writing (WeChat essays, blogs, newsletters, LinkedIn/X long-form) | `../longform-writing/SKILL.md` |
| Short-form social posts, threads & exact-pixel visual cards (X, Xiaohongshu, Threads, IG, Pinterest, WeChat newspic) | `../shortform-social/SKILL.md` |
| Short/long video scripting, subtitles & code-driven video (Douyin, TikTok, YouTube, Bilibili, Channels, Kuaishou) | `../video-production/SKILL.md` |
| Cross-platform comment triage, rate limits, 24h/72h/7d/30d snapshots & weekly retro board | `../engagement-and-analytics/SKILL.md` |
| Platform-specific radar, voice, hard specs, publish protocol & platform-native retro metrics | `../platform-<name>/SKILL.md` |

Shared deterministic utilities in `scripts/` (reused across regions and formats): `init_workspace.py`, `validate_workspace.py`, `diagnose.py`, `signal_gate.py`, `score_topics.py`, `check_media_specs.py`, `image_ops.py`, `build_boards.py`.

## Native Orchestration & Deterministic Boundaries

- **Semantic judgment, scheduling & fan-out belong to strong models and native Ducoro primitives**: check Ducoro Core Connectors first for any external platform interaction—intake, publish, engagement, or analytics (`ducoro-cli mcp catalog list` / `status <slug>` / `tools <slug>` / `call <slug> <tool> --args-file <path|->`)—schedule exact single- or multi-platform releases directly with `ducoro-cli task create --space <id> --at <iso-time> --timezone <tz>` (automatically projected onto Ducoro's top-level **Plan** calendar) and recurring rhythms with `--daily`/`--cron`, fan out parallel channel runs or heavy work via `ducoro-cli job dispatch` / `job start`, route human sign-offs into **Inbox** via `--human <id> --ask confirm --request-summary "..."`, and delegate cross-role handoffs via `ducoro-cli space send`.
- **Hard invariants belong to deterministic scripts**: `scripts/signal_gate.py` enforces grounded `http(s)://` URLs, ISO timestamps, keep-richest URL dedupe, incremental `seen-signals.json` deltas, anti-hallucination URL verification, and honest `nothing_solid` empty states; `scripts/score_topics.py` adds `--import-gated` merging and annotate-only fuzzy repeat detection; `scripts/check_media_specs.py` checks objective platform limits (`--channel browser|api`) and unfinished placeholders; `scripts/validate_workspace.py --verify-slot <slotId>` enforces Gate 2 tamper-proof `variantHash` pinning and publish idempotency.

Available platform guides (14) are indexed in `../../references/platforms.md`:
- **CN**: `platform-xiaohongshu`, `platform-douyin`, `platform-bilibili`, `platform-wechat-official`, `platform-wechat-channels`, `platform-kuaishou`
- **Global**: `platform-x-twitter`, `platform-youtube`, `platform-tiktok`, `platform-instagram`, `platform-facebook`, `platform-threads`, `platform-linkedin`, `platform-pinterest`

## Core References

Read on demand—do not recite from memory:
- `references/workspace-schema.md`: canonical directory layout and JSON/JSONL contracts.
- `references/approval-gates.md`: what runs autonomously vs. what requires explicit human approval (Gate 1: topic commitment, Gate 2: publish & sensitive replies).
- `references/operating-cadence.md`: daily/weekly loop schedule, retry/stop rules, and failure handling.
- `references/board-schemas.md`: unified data contract for all 5 interactive boards plus per-platform metric slots.
- `references/board-sdk-integration.md`: File-Backed Executable Document (FBED) conventions and progressive `window.ducoro` integration for all boards.
- `references/channel-access-matrix.md`: legitimate 3-tier access guide (connected Ducoro Core Connectors first, default official browser Creator Studio fallback, and optional user-owned official OpenAPI) across all 14 platforms.
- `references/issue-reporting.md`: when and how to offer a redacted plugin problem report via `ducoro-cli feedback send` with `[plugin:content-operations@<version>]` tags (always ask human first).

## Legitimate Execution Channels (Connector-First, Official Paths Only)

Never extract cookies, call reverse-engineered private APIs, or bypass login/CAPTCHA. Priority order across publishing, engagement, and analytics (`references/channel-access-matrix.md`):

1. **Connected Ducoro Core Connectors (First)**: check `ducoro-cli mcp catalog list` / `status <slug>` / `tools <slug>`; invoke active Connector tools when available (still enforcing Gate 2 & `engagement_guard.py`).
2. **Official Browser Creator Studio (Default fallback, all 14 platforms)**: upload local files from `drafts/<id>/assets/`, pause for login/CAPTCHA and Gate 2, then read back the live URL.
3. **Official Platform OpenAPI (`scripts/client.py`, optional, 12 platforms)**: use user-owned env vars (plus `ducoro-cli media upload <path> --json` 5h relay for Meta/Pinterest URL-fetch APIs).

## Workflow

1. **Resolve the working directory (existing folder or Space `files/` first; global Workspace is fallback-only).**
   - First inspect what the human and Space already have:
     ```sh
     ducoro-cli space resources get <space-id> --json
     ducoro-cli local-folder list --json
     ```
   - Follow this strict priority based on the human's actual setup:
     1. **Human's existing folder (first choice)**: If the human already keeps a marketing/content folder (or this Space already mounts one), use it directly—never create a second workspace.
     2. **Current Space `files/` (default for single-Space work)**: If this initiative runs inside one Space and does not need cross-Space file sharing, store operational files directly inside this Space's own `files/` (for example `files/content-ops/`). Run `python3 scripts/init_workspace.py <data-dir> --timezone <IANA-tz>` only when scaffolding the standard subfolders for the first time.
     3. **Cross-Space fallback only**: Only when the human explicitly wants multiple Spaces to share the same files and has no existing folder yet, ask for confirmation before creating a shared folder scoped to that initiative/brand (e.g., `~/.ducoro/workspaces/<initiative-slug>`, never inside `~/.ducoro/local-folders/`) and registering it as a global Local Folder:
        ```sh
        python3 scripts/init_workspace.py ~/.ducoro/workspaces/<initiative-slug> --timezone <IANA-tz>
        ducoro-cli local-folder register <initiative-slug> <resolved-absolute-path> --name "<Initiative Name>" --desc "Shared content operations folder for this initiative"
        ducoro-cli local-folder inspect <initiative-slug>
        ```
        Multiple Bots working on the same initiative share that one directory—never create one workspace per Bot, and never merge unrelated brands into one hardcoded slug.
   - Read `brand-profile.md` and `accounts.json` if present. Never hardcode credentials; `accounts.json` stores only environment variable names (e.g., `X_ACCESS_TOKEN`), never raw tokens.
2. **Execute the requested stage(s).**
   - **Intake & topics**: collect regional signals via Connectors (`ducoro-cli mcp catalog`), `topic-research-cn`, or `topic-research-global`, run `scripts/signal_gate.py ingest` + `gate --strict` (sharding large feeds across subagents), score and annotate fuzzy repeats via `scripts/score_topics.py`, and pause at **Approval Gate 1** (or stop honestly on `nothing_solid`).
   - **Production & adaptation**: load only the matching format workshop (`longform-writing`, `shortform-social`, or `video-production`) plus the target `platform-<name>` skill(s) to produce native `variants/<platform>.md` and media assets; validate every variant with `scripts/check_media_specs.py`.
   - **Schedule & publish**: record slot metadata and tamper-proof `approvedVariantHash` in `calendar.json`, schedule exact release wake-ups (1 platform or N platforms alike) natively via `ducoro-cli task create --space <id> --at <iso-time> --timezone <tz>` (visible in Ducoro's top-level **Plan** calendar; use `ducoro-cli job dispatch` when fanning out parallel platforms), verify approval and live `variantHash` via `python3 scripts/validate_workspace.py <content-ops-path> --verify-slot <slotId>` at **Approval Gate 2**, execute via Connector / API client / browser workflow, and **read back** the live public URL and work ID into `publish-log.jsonl`. Never mark a post `published` without live verification.
   - **Engagement & analytics**: pull comments and metrics per `engagement-and-analytics`, triage comments into 4 tiers, respect rate limits, record 24h/72h/7d snapshots in `analytics/snapshots.jsonl`, and feed high-signal questions and retro findings back into `inbox/` and `topics/`.
3. **Validate, diagnose, and refresh boards.**
   ```sh
   python3 scripts/validate_workspace.py <content-ops-path>
   python3 scripts/diagnose.py --workspace <content-ops-path> --json
   python3 scripts/build_boards.py <content-ops-path>
   ```
   - Canonical data stays in the chosen data directory (the human's existing folder, this Space's `files/`, or an optional cross-Space Local Folder), while each Space Board lives under that Space's `boards/<board-id>/`. Create each Board with `ducoro-cli board new --space <space-id> --title "<Board Title>" --json`, then project data into the Board's `assets/data.json` via `python3 scripts/build_boards.py <data-dir> --board <board-name> --board-dir <space-work-root>/boards/<board-id>` (add `--overwrite-templates` on first assembly) and verify layout/snapshots with `ducoro-cli render check --file <board-dir>/index.html --json` / `ducoro-cli render shot --file <board-dir>/index.html --json` before sharing links.

## Hard Guardrails

- **Silence is not approval.** Never publish externally, spend paid budget, or send commitment/dispute replies without explicit human confirmation unless a written standing rule in `brand-profile.md` authorizes that exact slot.
- **No fabricated execution.** Missing credentials or login/CAPTCHA gates must fall back cleanly to the official browser path or pause and report exact prerequisites.
- **Report real plugin defects (with consent).** Follow `references/issue-reporting.md` and submit via `ducoro-cli feedback send` with `[plugin:content-operations@<version>]`.
- **Single source of truth.** Files in `content-ops/` are canonical state; boards are read-only live projections of those files.

## Done When

- Workspace files pass `validate_workspace.py` with zero errors.
- Any external publish has a verified public URL (or explicit `draft_saved` / `failed` record) in `publish-log.jsonl`.
- Affected boards are rebuilt via `build_boards.py` and the next human decision (if any) is stated clearly with exact file paths.
