# Content Operations

> **Visual Interactive Overview**: Open [docs/index.html](docs/index.html) in any browser for an interactive bilingual (EN / 中文) overview of the loop, dual-track execution model, 14-platform capability matrix, and 5 Ducoro Board SDK dashboards.

A self-contained, zero-backend plugin for running a continuous, multi-platform content operations loop across 14 social platforms using **two legitimate execution channels only**:
- **Default zero-config path**: operate each platform's official web Creator Studio in the user's browser session (direct local file upload, draft staging, human Gate 2 confirmation, pause on login/CAPTCHA).
- **Optional advanced path**: call official platform OpenAPIs via zero-dependency Python 3 reference clients (`scripts/client.py`) using user-owned environment credentials (with 5-hour temporary public URL staging via `ducoro-cli media upload` for Meta/Pinterest URL-fetch APIs). Never extract cookies or call reverse-engineered private endpoints.

**Intake & Topic Research → Master Copy & Multimodal Production → Per-Platform Adaptation & Spec Validation → Scheduling & Publishing with Live Readback → Engagement Triage → Analytics Snapshots & Retrospectives → Interactive Boards**

## Architecture

One cohesive plugin covers the entire content operations domain so a single agent installs it once and can run either:
- **Single-workspace end-to-end mode** (one agent runs the whole loop in one workspace), or
- **Split-workspace relay mode** (multiple specialized workspaces—e.g. monitoring, drafting, publishing, analytics—each loading only the relevant skills while sharing the same file-backed workspace contract).

### Core Skills

| Skill | Responsibility |
| --- | --- |
| `content-ops-loop` | Orchestrator: local workspace schema, two human approval gates, recurring operating cadence, board templates, and routing index |
| `topic-research` | 5-channel topic sourcing, 4-dimension scoring card, deduplication cooldown, seasonal calendar, and brief authoring |
| `media-production` | Fact-checked master draft, multi-platform adaptation without fact drift, visual/video guidance, deterministic image edits, and automated spec checks |
| `engagement-and-analytics` | 4-tier comment intent triage, rate-limit safety guardrails, 24h/72h/7d metric snapshots, cross-platform attribution, and retro feedback into the topic pool |

### Per-Platform Vertical Skills (14 Platforms)

Each platform owns its own independent skill (`SKILL.md`), machine-readable spec limits (`references/specs.json` + `references/specs.md`), publishing/engagement/analytics protocol (`references/protocol.md`), and optional zero-dependency Python 3 reference client (`scripts/client.py`):

- **CN Platforms**: `platform-xiaohongshu`, `platform-douyin`, `platform-bilibili`, `platform-wechat-official`, `platform-wechat-channels`, `platform-kuaishou`
- **Global Platforms**: `platform-x-twitter`, `platform-youtube`, `platform-tiktok`, `platform-instagram`, `platform-facebook`, `platform-threads`, `platform-linkedin`, `platform-pinterest`

### Prebuilt Interactive Boards

Located in `skills/content-ops-loop/assets/boards/`:
1. `calendar-board/` — Monthly/weekly publishing schedule, holiday anchors, platform filters, and approval status
2. `pipeline-board/` — 4-stage Kanban from inbox/topics through drafts and spec compatibility alerts
3. `publish-ledger-board/` — Connected account matrix health and append-only publish log with live URLs
4. `engagement-inbox-board/` — 4-tier comment triage queue, drafted replies awaiting approval, and daily rate-limit bars
5. `analytics-retro-board/` — Multi-window KPI trends, cross-platform same-topic comparison, platform-specific metrics, and next-cycle retro actions

All boards run standalone as static HTML with local data and progressively enhance with `window.ducoro` when opened inside a Ducoro Board session (semantic location reporting, Composer draft staging, agent view commands, shared view storage, live file revalidation, and `board shot` / export-frame support).

## Quick Start

1. Load `content-ops-loop` and run `scripts/init_workspace.py <target-dir> [--timezone <IANA-tz>]` to scaffold a file-backed `content-ops/` workspace and assemble all 5 boards.
2. Fill in `brand-profile.md` and `accounts.json` (credentials stay in environment variables—never commit secrets).
3. Load `topic-research` plus only the `platform-<name>` skill(s) you are targeting in the current turn.
4. Refresh board data at any stage with `scripts/build_boards.py <workspace>` and verify integrity with `scripts/validate_workspace.py <workspace>`.

## References & Upstream Inspiration

This plugin is an independent, self-contained re-implementation with zero external backend or MCP dependencies. Its multi-platform specification matrix, publishing workflow taxonomy, and operational dashboard structure drew conceptual inspiration from the following open-source project snapshot:

- **Repository**: https://github.com/yikart/AiToEarn
- **Branch**: `main`
- **Commit**: [`11dd1957d0c69ae2b27a0b8a47acdf6675715558`](https://github.com/yikart/AiToEarn/commit/11dd1957d0c69ae2b27a0b8a47acdf6675715558) (`2026-11-16`)
- **Diff against latest upstream `main`**: https://github.com/yikart/AiToEarn/compare/11dd1957d0c69ae2b27a0b8a47acdf6675715558...main

> Note for maintainers: Keep upstream provenance references strictly in this `README.md`. Do not introduce upstream brand names, private endpoints, or local filesystem paths into any `SKILL.md`, `references/`, `scripts/`, or board assets.
