---
name: content-ops-loop
description: Orchestrate a continuous multi-platform content operations loop (intake, topic selection, production, scheduling, publishing, engagement, analytics, retro, and interactive boards) using a file-backed workspace. Use as the entry point to start, inspect, schedule, or coordinate any content workflow.
---

# Content Operations Loop

Run multi-platform content operations as a durable, file-backed loop rather than isolated one-off posts.

## Operating Modes

One installed plugin supports two topologies over the same `content-ops/` workspace directory:

1. **Single-workspace end-to-end**: One agent runs all stages sequentially in one workspace.
2. **Multi-workspace relay**: Dedicated workspaces (for example: trend monitoring, drafting, publishing, engagement) each load only the skills they need and hand off work through the shared `content-ops/` files (`inbox/`, `topics/`, `drafts/`, `calendar.json`, `publish-log.jsonl`, `engagement/`, `analytics/`).

Load only the skills relevant to the current stage and target platform(s). Never load all 14 platform skills at once.

## Skill Routing Table

| Stage / Need | Load Skill |
| --- | --- |
| Sourcing signals, scoring topics, writing briefs | `../topic-research/SKILL.md` |
| Writing master copy, adapting variants, image edits, spec validation | `../media-production/SKILL.md` |
| Comment triage, rate-limited replies, 24h/72h/7d metrics, weekly retros | `../engagement-and-analytics/SKILL.md` |
| Platform-specific topics, copy style, specs, API or browser publish protocol | `../platform-<name>/SKILL.md` |

Available platform skills (14):
- **CN**: `platform-xiaohongshu`, `platform-douyin`, `platform-bilibili`, `platform-wechat-official`, `platform-wechat-channels`, `platform-kuaishou`
- **Global**: `platform-x-twitter`, `platform-youtube`, `platform-tiktok`, `platform-instagram`, `platform-facebook`, `platform-threads`, `platform-linkedin`, `platform-pinterest`

## Core References

Read on demand—do not recite from memory:
- `references/workspace-schema.md`: canonical directory layout and JSON/JSONL contracts.
- `references/approval-gates.md`: what runs autonomously vs. what requires explicit human approval (Gate 1: topic commitment, Gate 2: publish & sensitive replies).
- `references/operating-cadence.md`: daily/weekly loop schedule, retry/stop rules, and failure handling.
- `references/board-schemas.md`: unified data contract for all 5 interactive boards plus per-platform metric slots.
- `references/board-sdk-integration.md`: File-Backed Executable Document (FBED) conventions and progressive `window.ducoro` integration for all boards.
- `references/channel-access-matrix.md`: legitimate dual-track access guide (default official browser Creator Studio vs. optional official OpenAPI, token lifecycles, and media upload routes) across all 14 platforms.
- `references/issue-reporting.md`: when and how to offer a redacted plugin problem report via `ducoro-cli feedback send` with `[plugin:content-operations@<version>]` tags (always ask human first).

## Legitimate Execution Channels (Two Official Tracks Only)

Every platform supports **only two legitimate execution paths**—never extract session cookies, call reverse-engineered private web APIs, or bypass login/CAPTCHA challenges:

1. **Default zero-config path — Official Creator Studio / Web App via Browser** (supported on **all 14 platforms**):
   - Open the platform's official web publishing studio in the user's browser session. If login, QR scan, 2FA, or CAPTCHA appears, pause immediately and hand control to the human.
   - Upload local media files directly from `drafts/<id>/assets/`, fill title/body/tags/cover, save as draft (`draft_saved`) or pause before the final Publish button until **Gate 2** is approved, then read back the verified live URL.
2. **Optional advanced path — Official Platform OpenAPI** (available on **12 platforms** when the user already holds official developer credentials in environment variables):
   - Call the platform's documented `scripts/client.py [--dry-run] <cmd>` using user-owned env vars (no third-party OAuth hosting). For Meta/Pinterest APIs that fetch from a public HTTPS URL, upload local files right before publish via `ducoro-cli media upload <path> --json` (5-hour temporary relay) or user-owned HTTPS storage.

## Workflow

1. **Locate or bootstrap the shared workspace (Ducoro Local Folder first).**
   - **Inside Ducoro (required shared storage pattern)**:
     1. First check whether a content-operations Local Folder is already registered and reuse it:
        ```sh
        ducoro-cli local-folder list --json
        ducoro-cli space resources get <space-id> --json
        ```
     2. If none exists yet, **ask the user before creating and registering it**:
        - **Default & recommended location**: `~/.ducoro/workspaces/content-ops` (kept cleanly inside `~/.ducoro/workspaces/`, never inside `~/.ducoro/local-folders/` which stores folder registration metadata).
        - **User-chosen external location**: only place the workspace outside `~/.ducoro/` if the user explicitly asks for another host directory (for example, a folder they prefer to browse directly in Finder).
        - Explain that registering the directory as a global Local Folder (`content-ops`) makes it visible to every Space on this machine so single-Space and multi-Space relay workflows share the exact same source of truth.
     3. After the user confirms the path, initialize and register it:
        ```sh
        python3 scripts/init_workspace.py ~/.ducoro/workspaces/content-ops --timezone <IANA-tz>
        ducoro-cli local-folder register content-ops <resolved-absolute-path> --name "Content Operations" --desc "Shared multi-platform content operations workspace (topics, drafts, calendar, publish log, analytics)"
        ducoro-cli local-folder inspect content-ops
        ```
        (Replace `~/.ducoro/workspaces/content-ops` with the user's chosen path only if they requested an external folder.)
   - **Outside Ducoro** (when `ducoro-cli` is unavailable, e.g. Claude Code / Codex): run `python3 scripts/init_workspace.py <workspace-root> --timezone <IANA-tz>` (e.g., `Asia/Shanghai`, `America/New_York`, default `UTC`) and point collaborating sessions to the same path via `CONTENT_OPS_ROOT`.
   - Read `brand-profile.md` and `accounts.json`. Never hardcode credentials; `accounts.json` stores only environment variable names (e.g., `X_ACCESS_TOKEN`), never raw tokens.
2. **Execute the requested stage(s).**
   - **Intake & topics**: collect signals into `inbox/`, score and deduplicate via `topic-research`, pause at **Approval Gate 1** before investing production effort.
   - **Production & adaptation**: draft fact-checked `master.md` first, then load each target `platform-<name>` skill to produce native `variants/<platform>.md` and media assets; validate every variant with `media-production/scripts/check_media_specs.py`.
   - **Schedule & publish**: add entries to `calendar.json`, verify facts + version + authorization at **Approval Gate 2**, execute via the platform's API client or browser workflow, and **read back** the live public URL and work ID into `publish-log.jsonl`. Never mark a post `published` without live verification.
   - **Engagement & analytics**: pull comments and metrics per `engagement-and-analytics`, triage comments into 4 tiers, respect rate limits, record 24h/72h/7d snapshots in `analytics/snapshots.jsonl`, and feed high-signal questions and retro findings back into `inbox/` and `topics/`.
3. **Validate and refresh boards.**
   ```sh
   python3 scripts/validate_workspace.py <content-ops-path>
   python3 scripts/build_boards.py <content-ops-path>
   ```
   - Inside Ducoro, canonical data stays in the registered Local Folder (default `~/.ducoro/workspaces/content-ops`), while each Space Board lives under that Space's `boards/<board-id>/`. Create each Board with `ducoro-cli board new --space <space-id> --title "<Board Title>" --json`, then project data from the Local Folder into the Board's `assets/data.json` via `python3 scripts/build_boards.py <local-folder-path> --board <board-name> --board-dir <space-work-root>/boards/<board-id>` (add `--overwrite-templates` on first assembly) and run `ducoro-cli board check` / `ducoro-cli board shot` before sharing links.

## Hard Guardrails

- **Silence is not approval.** Never publish externally, spend paid budget, or send commitment/dispute replies without explicit human confirmation unless a written standing rule in `brand-profile.md` authorizes that exact recurring slot.
- **Legitimate channels only.** Use either the platform's official web Creator Studio in a real browser (default, zero API setup) or official OpenAPI endpoints with user-owned credentials. Never harvest cookies, call undocumented private endpoints, or bypass CAPTCHAs.
- **No fabricated execution.** If a credential env var is missing or a platform requires browser login, fall back cleanly to the official browser Creator Studio path or pause at the verified draft/checklist state and report the exact prerequisite.
- **Report real plugin defects (with consent).** When a built-in script crashes, a platform API/Studio layout changes, or spec rules drift from reality, follow `references/issue-reporting.md`: draft a redacted report tagged `[plugin:content-operations@<version>] [skill:<name>] [location:<where>]`, ask the user for approval, and send via `ducoro-cli feedback send`.
- **Single source of truth.** Files in `content-ops/` are canonical state; boards are live projections of those files, never a second editable database.

## Done When

- Workspace files pass `validate_workspace.py` with zero errors.
- Any external publish has a verified public URL (or explicit `draft_saved` / `failed` record) in `publish-log.jsonl`.
- Affected boards are rebuilt via `build_boards.py` and the next human decision (if any) is stated clearly with exact file paths.
