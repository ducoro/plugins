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
| `content-ops-loop` | Orchestrator: shared workspace schema, readiness diagnostics (`diagnose.py`), hard provenance & signal-floor gate (`signal_gate.py`), non-destructive repeat-annotating topic scorer (`score_topics.py`), shared media/image utilities (`check_media_specs.py`, `image_ops.py`), two human approval gates, 5 interactive boards, and routing index |
| `topic-research-cn` | Chinese-market trend radar (Connectors, Weibo/Toutiao/Baidu live hot boards, Baidu/360 autocomplete demand, subagent sharding for large feeds, hard provenance/signal gate, CN seasonal calendar, Gate 1 brief authoring) |
| `topic-research-global` | Global/English trend radar (Connectors, 6 keyless live sources: Hacker News, Lobsters, GitHub, Polymarket, DEV.to, arXiv; subagent sharding for large feeds, hard provenance/signal gate, global seasonal calendar, Gate 1 brief authoring) |
| `longform-writing` | Deep long-form editorial workshop (WeChat essays, blogs, newsletters, LinkedIn/X long-form): verifiable source ledger (`source_ledger.py`), 7 frameworks & 7 personas, 5-dimension editorial gate (`content_eval.py`), corpus style bootstrap (`build_playbook.py`), ownership-safe exemplar library (`extract_exemplar.py`), mechanical style-risk checks (`check_writing_quality.py`), and scoped time-decayed edit-learning flywheel (`learn_edits.py`) |
| `shortform-social` | Short-form posts, microblog threads & exact-pixel visual cards (X/Twitter, Xiaohongshu, Threads, Instagram, Pinterest, Facebook, WeChat `newspic`): native hooks, anti-clone rewrites, `image_generate`, and `ducoro-cli board shot` card deck template |
| `video-production` | Short & long video scripting, subtitles & code-driven video (Douyin, TikTok, YouTube, Bilibili, WeChat Channels, Kuaishou): 0–3s hooks, spoken/shot scripts, safe zones, Remotion/HyperFrames code-driven video & real footage packaging (no text-to-video APIs) |
| `engagement-and-analytics` | Cross-platform comment triage, anti-spam rate limits, 24h/72h/7d/30d metric snapshots (`aggregate_metrics.py`), and weekly retro feedback paired with each platform's own north-star metrics |

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

1. Load `content-ops-loop`. In **Ducoro**, check `ducoro-cli local-folder list --json` first; if no workspace is registered yet, confirm with the user to initialize the default internal path `~/.ducoro/workspaces/content-ops` (or an external folder if the user explicitly prefers one) via `scripts/init_workspace.py`, then register it globally with `ducoro-cli local-folder register content-ops <path>` so every Space shares the same source of truth. Outside Ducoro, run `scripts/init_workspace.py <target-dir> [--timezone <IANA-tz>]`.
2. Fill in `brand-profile.md` and `accounts.json` (credentials stay in environment variables—never commit secrets).
3. Load only the regional radar (`topic-research-cn` or `topic-research-global`), the matching format workshop (`longform-writing`, `shortform-social`, or `video-production`), and the target `platform-<name>` skill(s) for the current turn.
4. Refresh Space board snapshots from the Local Folder with `scripts/build_boards.py <workspace>` (or `--board <name> --board-dir <space-work-root>/boards/<board-id>`) and verify integrity with `scripts/validate_workspace.py <workspace>`.

## Problem Reporting

When a built-in script fails unexpectedly or an upstream platform API / Creator Studio layout changes, the agent follows `skills/content-ops-loop/references/issue-reporting.md`: drafts a redacted report tagged `[plugin:content-operations@<version>] [skill:<name>] [location:<file-or-step>]`, asks for user confirmation, and submits it through Ducoro's built-in `ducoro-cli feedback send` channel (no GitHub account required).
