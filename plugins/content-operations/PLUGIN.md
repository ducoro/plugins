## Domain

Multi-platform content operations across 14 platforms—topic sourcing, copy and media production, adaptation, scheduled publishing with live readback, engagement, retrospectives, and interactive boards. Runs in the human's folder or Space `files/`; shared folders are fallback-only for Multi-Space relay.

## Activation & Boundaries

Activate for researching, drafting, visuals/videos, scheduling, publishing, comment triage, analytics, or boards. Defer brand voice, target accounts, and editorial strategy to Bot profile, Memory, and human instructions.

## Operating Loop

1. **Resolve data dir**: Run `ducoro-cli space info <id> --json` (`<space-work-root>`, `files/`), `ducoro-cli space resources get <id> --json`, and `ducoro-cli local-folder list --json`. Prefer the human's folder or Space `files/` (Single-Space); propose a global Local Folder only for Multi-Space relay—scoped to the initiative, never per Bot.
2. **Ducoro shortcuts**:
   - **Channels**: `ducoro-cli mcp catalog list|status|tools|call <slug> <tool> --args-file <path|-> --json` (1. Connectors -> 2. Optional OpenAPI `client.py` -> 3. Universal Fallback: Browser / Computer Use across all social tasks).
   - **Schedule & sign-off**: `ducoro-cli identity get --json` (`<human-id>`); `ducoro-cli task create --space <id> --at <iso>|--daily <HH:MM>|--cron "<expr>" --timezone <tz> --title "..." --instruction "..."` (Plan); immediate sign-off via `--manual --human <human-id> --ask confirm --request-summary "..."` + `ducoro-cli task fire <task-id> --space <id> --json`; halt stale tasks via `ducoro-cli task list|disable|rm`.
   - **Fan-out & isolated review**: `ducoro-cli space participant list <id> --json`, `ducoro-cli job dispatch [--space <id>] --agent <agent-id> --name "<name>" "<prompt>"`, collect via `ducoro-cli job status|log <job-id>`.
   - **Media, render, boards & relay**: `ducoro-cli render check|shot|pdf --file <path> --json`, `ducoro-cli media upload <path> --json`, `ducoro-cli board list|new|link --space <id> [--board boards/<id>] --json`, `ducoro-cli space mail send <recipient> --subject "<subject>" --body "<body>"`.
3. **Isolated review & gates**: Load only needed modules; defer voice/strategy to Bot profile, Memory, `brand-profile.md`. For high-risk releases or final long-form review, never self-certify `assessment.json`—dispatch fresh isolated read-only reviewers via `ducoro-cli job dispatch` (fact tracing, platform red lines, reader subtraction) and collect via `job status|log`. Enforce `signal_gate.py`, `check_media_specs.py`, and `validate_workspace.py --verify-slot <slotId>` before live-readback publish.

## Needs a Yes

Require explicit human confirmation before:
- **Gate 1**: Committing scored topics to production slots.
- **Gate 2**: Publishing/scheduling live posts, sensitive/disputed replies, or breakout amplification.
- **Channels & Computer Use**: Pause for login/CAPTCHA; report blocked coverage when desktop is locked; never extract cookies, call private APIs, or bypass anti-bot gates.
- **Cross-Space fallback**: Registering a new global Local Folder.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

- `skills/content-ops-loop/SKILL.md`: End-to-end loop, shared scripts, 5 boards, gates, issue reporting.
- `skills/topic-research-cn/SKILL.md`: CN trend radar, live hot boards, Gate 1 briefs.
- `skills/topic-research-global/SKILL.md`: Global/EN trend radar, Gate 1 briefs.
- `skills/longform-writing/SKILL.md`: Essays, newsletters, source ledger, isolated review.
- `skills/shortform-social/SKILL.md`: Posts, threads, card decks (`ducoro-cli render`), covers, motion cards.
- `skills/video-production/SKILL.md`: Video scripts, loudness/SRT checks, clipping, packaging.
- `skills/engagement-and-analytics/SKILL.md`: Comment triage, rate caps, snapshots, weekly retro.
- `references/platforms.md`: Index to all 14 platform playbooks, `specs.json`, optional OpenAPI clients.
